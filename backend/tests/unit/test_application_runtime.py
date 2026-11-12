"""Focused safety checks for the owned local application runtime."""

import asyncio
import io
import sys
import tarfile
import types
from uuid import uuid4

import pytest
from developer_platform.application.application_delivery.shared.ports import (
    ApplicationDeliveryFailure,
)
from psycopg.conninfo import conninfo_to_dict

from developer_platform.application.workload_delivery.shared.database_binding import (
    ApplicationDatabaseBinding,
)
from developer_platform.infra.providers.docker_application import DockerApplicationAdapter

#


class FakeNotFound(Exception):
    pass


class FakeObject:
    def __init__(self, name: str, labels: dict[str, str], object_id: str) -> None:
        self.name = name
        self.labels = labels
        self.id = object_id
        self.status = "running"
        self.attrs = {
            "State": {"Health": {"Status": "healthy"}},
            "NetworkSettings": {"Ports": {"8080/tcp": [{"HostPort": "49123"}]}},
            "Image": "image-sha",
            "Config": {},
            "Mounts": [],
        }
        self.removed = False
        self.archive: bytes | None = None

    def reload(self) -> None:
        return

    def remove(self, force: bool = False) -> None:
        self.removed = True

    def put_archive(self, path: str, archive: bytes) -> bool:
        self.archive = archive
        return True


class FakeNetwork(FakeObject):
    def __init__(self, name: str, labels: dict[str, str], object_id: str) -> None:
        super().__init__(name, labels, object_id)
        self.attrs["Containers"] = {}
        self.attrs["Driver"] = "bridge"
        self.attrs["Internal"] = True
        self.connect_calls: list[tuple[FakeObject, list[str]]] = []

    def connect(self, container: FakeObject, aliases: list[str]) -> None:
        self.connect_calls.append((container, aliases))
        self.attrs["Containers"][container.id] = {"Name": container.name}

    def disconnect(self, container: FakeObject) -> None:
        self.attrs["Containers"].pop(container.id, None)

    def remove(self, force: bool = False) -> None:
        self.attrs["Containers"].clear()
        super().remove(force)


class FakeClient:
    def __init__(self, database: FakeObject) -> None:
        self.database = database
        self.containers_by_name = {database.name: database}
        self.volumes_by_name: dict[str, FakeObject] = {}
        self.networks_by_name: dict[str, FakeNetwork] = {}
        self.run_calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

        class Collection:
            pass

        self.containers = Collection()
        self.volumes = Collection()
        self.networks = Collection()
        self.images = Collection()
        self.containers.get = self._container_get
        self.containers.run = self._container_run
        self.containers.list = lambda **kwargs: self._filter(
            self.containers_by_name.values(), kwargs
        )
        self.volumes.get = self._volume_get
        self.volumes.create = self._volume_create
        self.volumes.list = lambda **kwargs: self._filter(self.volumes_by_name.values(), kwargs)
        self.networks.get = self._network_get
        self.networks.create = self._network_create
        self.networks.list = lambda **kwargs: self._filter(self.networks_by_name.values(), kwargs)
        self.images.get = lambda name: types.SimpleNamespace(
            id="image-sha", attrs={"Config": {"Volumes": {}}}
        )

    def _container_get(self, name: str) -> FakeObject:
        if name in self.containers_by_name:
            return self.containers_by_name[name]
        for item in self.containers_by_name.values():
            if item.id == name:
                return item
        raise FakeNotFound(name)

    @staticmethod
    def _filter(values: object, kwargs: dict[str, object]) -> list[FakeObject]:
        items = list(values)
        filters = kwargs.get("filters", {})
        labels = filters.get("label", []) if isinstance(filters, dict) else []
        for label in labels:
            key, _, value = label.partition("=")
            items = [item for item in items if item.labels.get(key) == value]
        return items

    def _container_run(self, image: str, **kwargs: object) -> FakeObject:
        self.run_calls.append((image, kwargs))
        obj = FakeObject(str(kwargs["name"]), dict(kwargs["labels"]), f"id-{kwargs['name']}")
        mounts = [
            {
                "Type": "volume",
                "Name": name,
                "Destination": options["bind"],
                "RW": options["mode"] == "rw",
            }
            for name, options in kwargs.get("volumes", {}).items()
        ]
        host_port = {"HostIp": "127.0.0.1", "HostPort": "49123"}
        network_name = kwargs.get("network", "bridge")
        obj.attrs.update(
            {
                "Config": {
                    "Labels": kwargs["labels"],
                    "Cmd": kwargs.get("command"),
                    "User": kwargs.get("user", "10001:10001"),
                    "Env": [
                        f"{key}={value}" for key, value in kwargs.get("environment", {}).items()
                    ],
                },
                "HostConfig": {
                    "NetworkMode": kwargs.get("network_mode", network_name),
                    "PortBindings": {"8080/tcp": [host_port]} if kwargs.get("ports") else {},
                    "Privileged": False,
                    "ReadonlyRootfs": kwargs.get("read_only", False),
                    "Binds": None,
                    "NanoCpus": kwargs.get("nano_cpus", 0),
                    "Memory": 512 * 1024 * 1024,
                    "PidsLimit": kwargs.get("pids_limit", 0),
                    "CapDrop": kwargs.get("cap_drop", []),
                    "SecurityOpt": ["no-new-privileges:true"] if kwargs.get("security_opt") else [],
                    "Tmpfs": kwargs.get("tmpfs", {}),
                    "AutoRemove": kwargs.get("auto_remove", False),
                },
                "Mounts": mounts,
                "NetworkSettings": {
                    "Networks": {network_name: {}},
                    "Ports": {"8080/tcp": [host_port]} if kwargs.get("ports") else {},
                },
            }
        )
        obj.attrs["Image"] = image
        self.containers_by_name[obj.name] = obj
        return obj

    def _volume_get(self, name: str) -> FakeObject:
        if name not in self.volumes_by_name:
            raise FakeNotFound(name)
        return self.volumes_by_name[name]

    def _volume_create(self, name: str, labels: dict[str, str]) -> FakeObject:
        obj = FakeObject(name, labels, f"volume-{name}")
        self.volumes_by_name[name] = obj
        return obj

    def _network_get(self, name: str) -> FakeNetwork:
        if name not in self.networks_by_name:
            raise FakeNotFound(name)
        return self.networks_by_name[name]

    def _network_create(self, name: str, **kwargs: object) -> FakeNetwork:
        obj = FakeNetwork(name, dict(kwargs["labels"]), f"network-{name}")
        self.networks_by_name[name] = obj
        return obj

    def close(self) -> None:
        self.closed = True


def _install_docker(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    errors = types.ModuleType("docker.errors")
    errors.NotFound = FakeNotFound
    docker_module = types.ModuleType("docker")
    docker_module.DockerClient = lambda **kwargs: client
    docker_module.errors = errors
    monkeypatch.setitem(sys.modules, "docker", docker_module)
    monkeypatch.setitem(sys.modules, "docker.errors", errors)


def test_database_dsn_is_private_and_archive_uses_read_only_file_permissions() -> None:
    binding = ApplicationDatabaseBinding(
        installation_id=uuid4(),
        project_id=uuid4(),
        application_id=uuid4(),
        resource_id=uuid4(),
        container_name="dh-private-db",
        dsn="postgresql://private:password@db:5432/app",
    )
    assert "password" not in repr(binding)
    assert conninfo_to_dict(binding.dsn)["host"] == "db"
    archive = tarfile.open(fileobj=io.BytesIO(DockerApplicationAdapter._archive(binding.dsn)))
    entry = archive.getmember("database-url")
    assert entry.mode & 0o777 == 0o400
    assert entry.uid == entry.gid == 10001
    assert archive.extractfile(entry).read() == binding.dsn.encode()


def test_deploy_mounts_database_url_file_read_only_and_joins_only_owned_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_id, project_id, app_id, deployment_id, resource_id = (uuid4() for _ in range(5))
    db_name = f"dh-{install_id.hex[:8]}-{resource_id.hex}"
    db_labels = {
        "devops-hub.managed": "true",
        "devops-hub.installation": str(install_id),
        "devops-hub.resource": str(resource_id),
    }
    database = FakeObject(db_name, db_labels, "database-id")
    client = FakeClient(database)
    _install_docker(monkeypatch, client)
    binding = ApplicationDatabaseBinding(
        install_id,
        project_id,
        app_id,
        resource_id,
        db_name,
        "postgresql://user:secret@db:5432/app",
    )

    class BindingResolver:
        async def resolve(self, requested_project, requested_application, requested_resource):
            assert (requested_project, requested_application, requested_resource) == (
                project_id,
                app_id,
                resource_id,
            )
            return binding

    runtime = DockerApplicationAdapter(
        frozenset({"approved@sha256:" + "a" * 64}),
        "unix:///var/run/docker.sock",
        "postgres:16",
        install_id,
        BindingResolver(),  # type: ignore[arg-type]
        1,
    )

    asyncio.run(
        runtime.deploy(
            project_id=project_id,
            application_id=app_id,
            deployment_id=deployment_id,
            image_digest="approved@sha256:" + "a" * 64,
            target_id="local",
            resource_id=resource_id,
            idempotency_key="deploy",
        )
    )

    helper_call = next(call for call in client.run_calls if call[1]["network_mode"] == "none")
    app_call = next(call for call in client.run_calls if "network" in call[1])
    assert helper_call[1]["volumes"]
    assert helper_call[1]["tmpfs"]
    assert app_call[1]["environment"] == {"DATABASE_URL_FILE": "/run/devops-hub/database-url"}
    assert "secret" not in repr(app_call[1]["environment"])
    assert next(iter(app_call[1]["volumes"].values()))["mode"] == "ro"
    network = next(iter(client.networks_by_name.values()))
    assert network.connect_calls == [(database, [db_name])]
    assert not database.removed
    volumes = list(client.volumes_by_name.values())
    app_container = next(
        item for item in client.containers_by_name.values() if item.name.startswith("devhub-")
    )
    asyncio.run(
        runtime.remove(
            project_id=project_id,
            application_id=app_id,
            idempotency_key="remove",
        )
    )
    assert app_container.removed
    assert all(volume.removed for volume in volumes)
    assert network.removed
    assert network.attrs["Containers"] == {}
    assert not database.removed
    assert client.closed


def test_remove_validates_every_candidate_before_removing_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installation_id, project_id, application_id = uuid4(), uuid4(), uuid4()
    labels = {
        "devops-hub.managed": "true",
        "devops-hub.installation": str(installation_id),
        "devops-hub.project": str(project_id),
        "devops-hub.application": str(application_id),
    }
    owned = FakeObject("owned", labels, "owned-id")
    conflict = FakeObject("conflict", {**labels, "devops-hub.project": str(uuid4())}, "bad-id")
    client = FakeClient(FakeObject("db", {}, "db-id"))
    client.containers_by_name.update({owned.name: owned, conflict.name: conflict})
    _install_docker(monkeypatch, client)
    runtime = DockerApplicationAdapter(
        frozenset(), "unix:///var/run/docker.sock", "postgres:16", installation_id, None
    )

    with pytest.raises(ApplicationDeliveryFailure, match="container_ownership_conflict"):
        asyncio.run(
            runtime.remove(
                project_id=project_id,
                application_id=application_id,
                idempotency_key="remove",
            )
        )
    assert not owned.removed
    assert not conflict.removed
    assert not client.containers_by_name["db"].removed


def test_application_adapter_resolves_database_binding_and_preserves_deployer_contract() -> None:
    installation_id, project_id, application_id, deployment_id, resource_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    binding = ApplicationDatabaseBinding(
        installation_id,
        project_id,
        application_id,
        resource_id,
        "owned-db",
        "postgresql://user:private@owned-db/app",
    )

    class Resolver:
        async def resolve(self, received_project, received_app, received_resource):
            assert (received_project, received_app, received_resource) == (
                project_id,
                application_id,
                resource_id,
            )
            return binding

    adapter = DockerApplicationAdapter(
        frozenset({"approved@sha256:" + "a" * 64}),
        "unix:///var/run/docker.sock",
        "postgres:16",
        installation_id,
        Resolver(),  # type: ignore[arg-type]
    )

    def fake_deploy(*args):
        return ("http://127.0.0.1:49123", "deployment-container")

    adapter._deploy_runtime = fake_deploy  # type: ignore[method-assign]
    url, reference = asyncio.run(
        adapter.deploy(
            project_id=project_id,
            application_id=application_id,
            deployment_id=deployment_id,
            image_digest="approved@sha256:" + "a" * 64,
            target_id="local",
            resource_id=resource_id,
            idempotency_key="deployment-key",
        )
    )
    assert url == "http://127.0.0.1:49123"
    assert reference == "deployment-container"


def test_application_adapter_fails_closed_without_database_binding_resolver() -> None:
    adapter = DockerApplicationAdapter(
        frozenset({"approved@sha256:" + "a" * 64}),
        "unix:///var/run/docker.sock",
        "postgres:16",
        uuid4(),
        None,
    )
    with pytest.raises(ApplicationDeliveryFailure, match="resource_configuration_not_configured"):
        asyncio.run(
            adapter.deploy(
                project_id=uuid4(),
                application_id=uuid4(),
                deployment_id=uuid4(),
                image_digest="approved@sha256:" + "a" * 64,
                target_id="local",
                resource_id=uuid4(),
                idempotency_key="deployment-key",
            )
        )


def test_cancelled_docker_thread_is_drained_before_cancellation_returns() -> None:
    started = asyncio.Event()

    async def run() -> None:
        runtime = DockerApplicationAdapter(
            frozenset(), "unix:///var/run/docker.sock", "postgres:16", uuid4(), None
        )

        started_loop = asyncio.get_running_loop()
        import threading

        release = threading.Event()

        def effect() -> None:
            started_loop.call_soon_threadsafe(started.set)
            release.wait()

        task = asyncio.create_task(runtime._threaded(effect))
        await started.wait()
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
