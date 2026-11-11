from __future__ import annotations

import asyncio
import io
import tarfile
from types import SimpleNamespace
from uuid import UUID, uuid4

import docker
import pytest
from developer_platform.application.resource_lifecycle.ports import (
    DatabaseCredentials,
    DatabaseEndpoint,
    ProviderFailure,
    ProvisioningJob,
)

import developer_platform.infra.docker_provider as docker_provider
from developer_platform.infra.docker_provider import DockerPostgresProvider


class FakeImage:
    id = "sha256:approved-image"


class FakeImages:
    def __init__(self) -> None:
        self.pulls = 0

    def get(self, _image: str) -> FakeImage:
        return FakeImage()

    def pull(self, _image: str) -> FakeImage:
        self.pulls += 1
        return FakeImage()


class FakeVolume:
    def __init__(self, name: str, labels: dict[str, str]) -> None:
        self.name = name
        self.labels = labels
        self.remove_calls = 0

    def remove(self, force: bool = False) -> None:
        assert force
        self.remove_calls += 1


class FakeVolumes:
    def __init__(self) -> None:
        self.items: dict[str, FakeVolume] = {}
        self.created: list[str] = []
        self.listed: list[FakeVolume] = []

    def get(self, name: str) -> FakeVolume:
        if name not in self.items:
            raise docker.errors.NotFound("missing volume")
        return self.items[name]

    def create(self, name: str, labels: dict[str, str]) -> FakeVolume:
        self.created.append(name)
        volume = FakeVolume(name, labels)
        self.items[name] = volume
        return volume

    def list(self, filters: dict[str, str]) -> list[FakeVolume]:
        return self.listed


class FakeContainer:
    def __init__(
        self,
        name: str,
        labels: dict[str, str],
        attrs: dict[str, object],
        status: str = "running",
        ready: bool = True,
    ) -> None:
        self.name = name
        self.labels = labels
        self.attrs = attrs
        self.status = status
        self.ready = ready
        self.pg_version_exists = False
        self.started = 0
        self.unpaused = 0
        self.remove_calls = 0
        self.commands: list[tuple[list[str], dict[str, str] | None]] = []
        self.archives: list[bytes] = []

    def reload(self) -> None:
        return None

    def start(self) -> None:
        self.started += 1
        self.status = "running"

    def unpause(self) -> None:
        self.unpaused += 1
        self.status = "running"

    def remove(self, force: bool = False) -> None:
        assert force
        self.remove_calls += 1

    def exec_run(self, command: list[str], environment: dict[str, str] | None = None):
        self.commands.append((command, environment))
        if command[:2] == ["test", "-f"]:
            return SimpleNamespace(exit_code=0 if self.pg_version_exists else 1, output=b"")
        return SimpleNamespace(
            exit_code=0 if self.ready else 1, output=b"1\n" if self.ready else b""
        )

    def put_archive(self, _path: str, archive: bytes) -> bool:
        self.archives.append(archive)
        return True


class FakeContainers:
    def __init__(self) -> None:
        self.items: dict[str, FakeContainer] = {}
        self.created: list[str] = []
        self.run_calls: list[tuple[str, dict[str, object]]] = []
        self.listed: list[FakeContainer] = []

    def get(self, name: str) -> FakeContainer:
        if name not in self.items:
            raise docker.errors.NotFound("missing container")
        return self.items[name]

    def run(self, image: str, **kwargs) -> FakeContainer:
        name = kwargs["name"]
        self.created.append(name)
        self.run_calls.append((image, kwargs))
        attrs = _container_attrs(image, kwargs)
        helper = FakeContainer(name, kwargs["labels"], attrs)
        self.items[name] = helper
        return helper

    def list(self, all: bool, filters: dict[str, str]) -> list[FakeContainer]:
        return self.listed


class FakeClient:
    def __init__(self) -> None:
        self.images = FakeImages()
        self.containers = FakeContainers()
        self.volumes = FakeVolumes()


def _container_attrs(image_id: str, kwargs: dict[str, object]) -> dict[str, object]:
    mounts = []
    for name, options in (kwargs.get("volumes") or {}).items():
        options = options  # keep the SDK-shaped object readable to type checkers
        mounts.append(
            {
                "Type": "volume",
                "Name": name,
                "Destination": options["bind"],
                "RW": options["mode"] == "rw",
            }
        )
    port_config = kwargs.get("ports") or {}
    runtime_ports = (
        {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "15432"}]} if port_config else {}
    )
    return {
        "Image": image_id,
        "Config": {
            "Labels": kwargs.get("labels", {}),
            "Env": [f"{key}={value}" for key, value in (kwargs.get("environment") or {}).items()],
            "User": kwargs.get("user", ""),
            "Cmd": kwargs.get("command", []),
        },
        "HostConfig": {
            "NanoCpus": kwargs.get("nano_cpus", 2_000_000_000),
            "Memory": kwargs.get("mem_limit", 1024 * 1024 * 1024),
            "RestartPolicy": kwargs.get("restart_policy", {"Name": "unless-stopped"}),
            "PortBindings": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]}
            if port_config
            else {},
            "NetworkMode": kwargs.get("network_mode", "default"),
            "AutoRemove": kwargs.get("auto_remove", False),
        },
        "Mounts": mounts,
        "NetworkSettings": {"Ports": runtime_ports},
    }


def _job() -> ProvisioningJob:
    return ProvisioningJob(
        operation_id=uuid4(),
        resource_id=UUID("2a5ebd3b-7505-49b7-ae67-09b16ef6e256"),
        installation_id=UUID("ca8253f3-2a6a-4f0e-a9b4-e79e9040d91c"),
        generation=3,
        claim_token=uuid4(),
        action="provision",
        cpu_millis=2000,
        memory_bytes=1024 * 1024 * 1024,
        credentials=DatabaseCredentials(
            user='db"user',
            database="feature_db",
            password="p'assword\\withquote",
            administrator_password="admin-private-value",
        ),
    )


def _owned_objects(
    job: ProvisioningJob, *, memory: int | None = None
) -> tuple[FakeClient, FakeContainer, dict[str, str]]:
    client = FakeClient()
    provider = DockerPostgresProvider.__new__(DockerPostgresProvider)
    provider._client = client
    provider._approved_image = "postgres:approved"
    provider._advertised_host = "127.0.0.1"
    labels = DockerPostgresProvider._labels(job)
    root = DockerPostgresProvider._root_name(job)
    data_name, config_name = f"{root}-data", f"{root}-config"
    client.volumes.items[data_name] = FakeVolume(data_name, labels.copy())
    client.volumes.items[config_name] = FakeVolume(config_name, labels.copy())
    attrs = {
        "Image": FakeImage.id,
        "Config": {
            "Env": [
                "POSTGRES_PASSWORD_FILE=/docker-entrypoint-initdb.d/admin_password",
                "POSTGRES_HOST_AUTH_METHOD=scram-sha-256",
            ],
            "Labels": labels,
        },
        "HostConfig": {
            "NanoCpus": job.cpu_millis * 1_000_000,
            "Memory": memory if memory is not None else job.memory_bytes,
            "RestartPolicy": {"Name": "unless-stopped"},
            "PortBindings": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]},
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": data_name,
                "Destination": "/var/lib/postgresql/data",
                "RW": True,
            },
            {
                "Type": "volume",
                "Name": config_name,
                "Destination": "/docker-entrypoint-initdb.d",
                "RW": False,
            },
        ],
        "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "15432"}]}},
    }
    main = FakeContainer(root, labels.copy(), attrs)
    client.containers.items[root] = main
    return client, main, labels


def _provider(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> DockerPostgresProvider:
    def create_client(*, base_url: str, timeout: int) -> FakeClient:
        assert base_url == "unix:///unused.sock"
        assert timeout == 10
        return client

    monkeypatch.setattr(docker_provider.docker, "DockerClient", create_client)
    return DockerPostgresProvider("unix:///unused.sock", "postgres:approved")


def test_provision_adopts_owned_ready_container_and_only_cleans_init_files(monkeypatch):
    job = _job()
    client, main, _labels = _owned_objects(job)
    provider = _provider(monkeypatch, client)

    endpoint = asyncio.run(provider.provision(job))

    assert endpoint == DatabaseEndpoint("127.0.0.1", 15432)
    assert main.started == 0
    assert client.containers.created == [f"{provider._root_name(job)}-init"]
    assert main.remove_calls == 0


def test_provision_creates_isolated_container_with_private_init_archive(monkeypatch):
    job = _job()
    client = FakeClient()
    provider = _provider(monkeypatch, client)

    endpoint = asyncio.run(provider.provision(job))

    assert endpoint == DatabaseEndpoint("127.0.0.1", 15432)
    root = provider._root_name(job)
    assert client.containers.created == [f"{root}-init", root, f"{root}-init"]
    assert set(client.volumes.created) == {f"{root}-data", f"{root}-config"}
    main_call = next(
        kwargs for _image, kwargs in client.containers.run_calls if kwargs["name"] == root
    )
    assert main_call["nano_cpus"] == job.cpu_millis * 1_000_000
    assert main_call["mem_limit"] == job.memory_bytes
    assert main_call["ports"] == {"5432/tcp": ("127.0.0.1", None)}
    assert main_call["environment"] == {
        "POSTGRES_PASSWORD_FILE": "/docker-entrypoint-initdb.d/admin_password",
        "POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
    }
    assert job.credentials.administrator_password not in repr(main_call)
    init_archive = client.containers.run_calls[0][1]
    # The helper uses a path only; credential values are transferred through
    # the tar archive rather than its command, args, or environment.
    assert init_archive["command"] == ["sleep", "60"]
    assert "environment" not in init_archive


def test_inspect_is_observational_and_checks_authenticated_readiness(monkeypatch):
    job = _job()
    client, main, _labels = _owned_objects(job)
    provider = _provider(monkeypatch, client)

    endpoint = asyncio.run(provider.inspect(job))

    assert endpoint == DatabaseEndpoint("127.0.0.1", 15432)
    assert main.commands[0][0][-1] == "SELECT 1"
    assert main.commands[0][1] == {"PGPASSWORD": job.credentials.password}
    assert client.containers.created == []
    assert client.images.pulls == 0


def test_delete_ownership_conflict_leaves_all_objects_untouched(monkeypatch):
    job = _job()
    client, _main, _labels = _owned_objects(job)
    provider = _provider(monkeypatch, client)
    root = provider._root_name(job)
    collision = client.containers.items[root]
    collision.labels["devops-hub.resource"] = str(uuid4())
    volumes = tuple(client.volumes.items.values())

    with pytest.raises(ProviderFailure) as raised:
        asyncio.run(provider.delete(job))

    assert (raised.value.code, raised.value.uncertain) == ("ownership_conflict", False)
    assert collision.remove_calls == 0
    assert all(volume.remove_calls == 0 for volume in volumes)


def test_delete_removes_only_owned_objects_and_accepts_older_generation(monkeypatch):
    job = _job()
    client, main, labels = _owned_objects(job)
    provider = _provider(monkeypatch, client)
    old_labels = dict(labels, **{"devops-hub.generation": "1"})
    main.labels = old_labels
    client.volumes.items = {
        name: FakeVolume(name, old_labels.copy()) for name in client.volumes.items
    }
    helper_name = f"{provider._root_name(job)}-init"
    client.containers.items[helper_name] = FakeContainer(helper_name, old_labels.copy(), {})

    result = asyncio.run(provider.delete(job))

    assert result.absent is True
    assert result.observed_owned_object is True
    assert main.remove_calls == 1
    assert client.containers.items[helper_name].remove_calls == 1
    assert all(volume.remove_calls == 1 for volume in client.volumes.items.values())


def test_provision_drift_fails_without_starting_or_replacing_container(monkeypatch):
    job = _job()
    client, main, _labels = _owned_objects(job, memory=job.memory_bytes * 2)
    provider = _provider(monkeypatch, client)

    with pytest.raises(ProviderFailure) as raised:
        asyncio.run(provider.provision(job))

    assert (raised.value.code, raised.value.uncertain) == ("provider_drift", False)
    assert main.started == 0
    assert client.containers.created == []
    assert main.remove_calls == 0


def test_provision_does_not_recreate_container_over_initialized_volume(monkeypatch):
    job = _job()
    client = FakeClient()
    provider = _provider(monkeypatch, client)
    labels = DockerPostgresProvider._labels(job)
    root = provider._root_name(job)
    data = FakeVolume(f"{root}-data", labels)
    client.volumes.items[data.name] = data

    def run_data_probe(image: str, **kwargs) -> FakeContainer:
        container = FakeContainers.run(client.containers, image, **kwargs)
        if kwargs["name"] == f"{root}-init":
            container.pg_version_exists = True
        return container

    client.containers.run = run_data_probe

    with pytest.raises(ProviderFailure) as raised:
        asyncio.run(provider.provision(job))

    assert (raised.value.code, raised.value.uncertain) == ("provider_drift", False)
    assert root not in client.containers.created
    assert data.remove_calls == 0


def test_readiness_timeout_is_bounded_and_reports_no_command_output(monkeypatch):
    job = _job()
    client, main, _labels = _owned_objects(job)
    main.ready = False
    provider = _provider(monkeypatch, client)
    clock = iter((0.0, 1.0, 46.0))
    monkeypatch.setattr(docker_provider.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(docker_provider.time, "sleep", lambda _seconds: None)

    with pytest.raises(ProviderFailure) as raised:
        provider._wait_until_ready(main, job)

    assert (raised.value.code, raised.value.uncertain) == ("readiness_timeout", True)
    assert raised.value.args == ("readiness_timeout",)


def test_discover_includes_only_verified_container_or_volume_resource_labels(monkeypatch):
    job = _job()
    client = FakeClient()
    provider = _provider(monkeypatch, client)
    labels = DockerPostgresProvider._labels(job)
    orphan_id = uuid4()
    orphan_labels = {
        "devops-hub.managed": "true",
        "devops-hub.installation": str(job.installation_id),
        "devops-hub.resource": str(orphan_id),
        "devops-hub.generation": "1",
    }
    bad_labels = dict(orphan_labels, **{"devops-hub.managed": "false"})
    client.containers.listed.append(FakeContainer("untrusted-name", labels, {}))
    client.volumes.listed.extend(
        [FakeVolume("not-a-resource-prefix", orphan_labels), FakeVolume("bad", bad_labels)]
    )

    found = asyncio.run(provider.discover(job.installation_id))

    assert set(found) == {orphan_id, job.resource_id}


def test_bootstrap_archive_has_private_files_and_sql_escapes_identifiers_and_password():
    job = _job()
    archive_bytes = DockerPostgresProvider._configuration_archive(job)

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r") as archive:
        password_file = archive.getmember("admin_password")
        sql_file = archive.getmember("00-init.sql")
        script = archive.extractfile(sql_file).read().decode()
        assert password_file.mode == 0o600
        assert sql_file.mode == 0o600
        assert archive.extractfile(password_file).read() == b"admin-private-value"
    assert 'CREATE ROLE "db""user" LOGIN PASSWORD ' in script
    assert "p''assword" in script
    assert "REVOKE CONNECT ON DATABASE template1 FROM PUBLIC" in script


def test_graceful_cancellation_waits_for_sdk_thread(monkeypatch):
    import threading

    async def scenario():
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        provider = _provider(monkeypatch, FakeClient())

        def effect():
            started.set()
            release.wait(timeout=3)
            finished.set()

        task = asyncio.create_task(provider._threaded(effect))
        await asyncio.to_thread(started.wait, 1)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(scenario())


def test_volume_labels_follow_real_sdk_top_level_attrs():
    volume = SimpleNamespace(attrs={"Labels": {"devops-hub.managed": "true"}})
    assert DockerPostgresProvider._object_labels(volume) == {"devops-hub.managed": "true"}
