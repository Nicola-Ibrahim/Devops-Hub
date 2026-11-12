"""Owned local Docker implementation of the PostgreSQL resource provider."""

from __future__ import annotations

import asyncio
import io
import tarfile
import time
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

import docker  # type: ignore[import-untyped]
from docker.errors import ImageNotFound, NotFound  # type: ignore[import-untyped]
from docker.models.containers import Container  # type: ignore[import-untyped]
from docker.models.images import Image  # type: ignore[import-untyped]
from docker.models.volumes import Volume  # type: ignore[import-untyped]
from psycopg import sql

from devops_platform.application.database_lifecycle.ports import (
    DatabaseEndpoint,
    DeletionObservation,
    LocalDatabaseProvider,
    ProviderFailure,
    ProvisioningJob,
)

_T = TypeVar("_T")
_MANAGED = "devops-hub.managed"
_INSTALLATION = "devops-hub.installation"
_RESOURCE = "devops-hub.resource"
_GENERATION = "devops-hub.generation"
_POSTGRES_PORT = "5432/tcp"
_INIT_PASSWORD_FILE = "admin_password"
_INIT_SQL_FILE = "00-init.sql"


class DockerPostgresProvider(LocalDatabaseProvider):
    """Provision one isolated PostgreSQL container per resource using Docker.

    All names and labels derive from control-plane IDs. The API accepts no image,
    Docker name, mount, command, or port input from a developer.
    """

    def __init__(
        self,
        docker_url: str,
        image: str,
        advertised_host: str = "127.0.0.1",
    ) -> None:
        if not docker_url or not image or not advertised_host:
            raise ValueError("Docker URL, approved image, and advertised host are required")
        self._client = docker.DockerClient(base_url=docker_url, timeout=10)
        self._approved_image = image
        self._advertised_host = advertised_host

    async def provision(self, job: ProvisioningJob) -> DatabaseEndpoint:
        return await self._threaded(self._provision, job)

    async def delete(self, job: ProvisioningJob) -> DeletionObservation:
        return await self._threaded(self._delete, job)

    async def inspect(self, job: ProvisioningJob) -> DatabaseEndpoint | None:
        return await self._threaded(self._inspect, job)

    async def discover(self, installation_id: UUID) -> tuple[UUID, ...]:
        return await self._threaded(self._discover, installation_id)

    async def _threaded(self, operation: Callable[..., _T], *args: object) -> _T:
        try:
            # Cancellation must not let the enclosing effect guard go while the SDK
            # thread can still mutate Docker. Shield, drain, then propagate cancellation.
            task = asyncio.create_task(asyncio.to_thread(operation, *args))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                while not task.done():
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                # Retrieve exceptions without leaking daemon details on cancellation.
                if not task.cancelled():
                    task.exception()
                raise
        except ProviderFailure:
            raise
        except Exception:
            # Docker errors can include request, environment, or daemon details.
            # Keep the provider's public failure contract deliberately generic.
            raise ProviderFailure("provider_unavailable", True) from None

    @staticmethod
    def _labels(job: ProvisioningJob) -> dict[str, str]:
        return {
            _MANAGED: "true",
            _INSTALLATION: str(job.installation_id),
            _RESOURCE: str(job.resource_id),
            _GENERATION: str(job.generation),
        }

    @staticmethod
    def _root_name(job: ProvisioningJob) -> str:
        return f"dh-{job.installation_id.hex[:8]}-{job.resource_id.hex}"

    @staticmethod
    def _object_labels(item: Any) -> dict[str, str]:
        labels = getattr(item, "labels", None)
        if labels is not None:
            return dict(labels)
        attrs = getattr(item, "attrs", {})
        config = attrs.get("Config", {}) if isinstance(attrs, dict) else {}
        return dict(attrs.get("Labels") or config.get("Labels") or {})

    @classmethod
    def _require_labels(cls, item: Any, expected: dict[str, str]) -> None:
        labels = cls._object_labels(item)
        if any(labels.get(key) != value for key, value in expected.items()):
            raise ProviderFailure("ownership_conflict", False)

    @staticmethod
    def _validate_job(job: ProvisioningJob) -> None:
        if job.generation < 1 or job.cpu_millis < 1 or job.memory_bytes < 1:
            raise ProviderFailure("resource_limits_invalid", False)
        if not job.credentials.user or not job.credentials.database or not job.credentials.password:
            raise ProviderFailure("credentials_invalid", False)
        if not job.credentials.administrator_password:
            raise ProviderFailure("credentials_invalid", False)

    def _resolve_image(self) -> Image:
        try:
            return self._client.images.get(self._approved_image)
        except ImageNotFound:
            return self._client.images.pull(self._approved_image)

    def _local_image(self) -> Image:
        try:
            return self._client.images.get(self._approved_image)
        except ImageNotFound:
            raise ProviderFailure("provider_drift", False) from None

    def _container(self, name: str) -> Container | None:
        try:
            return self._client.containers.get(name)
        except NotFound:
            return None

    def _volume(self, name: str) -> Volume | None:
        try:
            return self._client.volumes.get(name)
        except NotFound:
            return None

    def _ensure_volume(self, name: str, labels: dict[str, str]) -> Volume:
        volume = self._volume(name)
        if volume is None:
            volume = self._client.volumes.create(name=name, labels=labels)
        self._require_labels(volume, labels)
        return volume

    def _required_volume(self, name: str, labels: dict[str, str]) -> Volume:
        volume = self._volume(name)
        if volume is None:
            raise ProviderFailure("provider_drift", False)
        self._require_labels(volume, labels)
        return volume

    @staticmethod
    def _sql_init_script(user: str, database: str, password: str) -> bytes:
        role = sql.Identifier(user).as_string()
        db = sql.Identifier(database).as_string()
        literal = sql.Literal(password).as_string()
        statement = (
            f"CREATE ROLE {role} LOGIN PASSWORD {literal} NOSUPERUSER NOCREATEDB NOCREATEROLE;\n"
            f"CREATE DATABASE {db} OWNER {role};\n"
            "REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;\n"
            "REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;\n"
            f"REVOKE CONNECT ON DATABASE {db} FROM PUBLIC;\n"
            f"GRANT CONNECT ON DATABASE {db} TO {role};\n"
        )
        return statement.encode("utf-8")

    @staticmethod
    def _configuration_archive(job: ProvisioningJob) -> bytes:
        contents = (
            (_INIT_PASSWORD_FILE, job.credentials.administrator_password.encode("utf-8")),
            (
                _INIT_SQL_FILE,
                DockerPostgresProvider._sql_init_script(
                    job.credentials.user, job.credentials.database, job.credentials.password
                ),
            ),
        )
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as archive:
            for name, data in contents:
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mode = 0o600
                entry.uid = 999
                entry.gid = 999
                entry.uname = ""
                entry.gname = ""
                archive.addfile(entry, io.BytesIO(data))
        return output.getvalue()

    def _run_helper(
        self,
        *,
        job: ProvisioningJob,
        image_id: str,
        config_volume: str,
        labels: dict[str, str],
        seed: bool,
    ) -> None:
        helper_name = f"{self._root_name(job)}-init"
        previous = self._container(helper_name)
        if previous is not None:
            self._verify_helper(previous, job, image_id, config_volume, labels)
            previous.remove(force=True)

        helper = self._client.containers.run(
            image_id,
            command=["sleep", "60"],
            name=helper_name,
            user="0:0",
            detach=True,
            labels=labels,
            volumes={config_volume: {"bind": "/config", "mode": "rw"}},
            network_mode="none",
            tmpfs={"/var/lib/postgresql/data": "rw,noexec,nosuid,size=1m"},
            auto_remove=False,
        )
        self._verify_helper(helper, job, image_id, config_volume, labels)
        try:
            if seed:
                accepted = helper.put_archive("/config", self._configuration_archive(job))
                if not accepted:
                    raise ProviderFailure("configuration_write_failed", True)
            else:
                result = helper.exec_run(["rm", "-f", f"/config/{_INIT_SQL_FILE}"])
                if result.exit_code != 0:
                    raise ProviderFailure("configuration_cleanup_failed", True)
        finally:
            helper.remove(force=True)

    def _verify_helper(
        self,
        helper: Container,
        job: ProvisioningJob,
        image_id: str,
        config_volume: str,
        labels: dict[str, str],
    ) -> None:
        self._require_labels(helper, labels)
        helper.reload()
        attrs = helper.attrs
        if attrs.get("Image") != image_id:
            raise ProviderFailure("provider_drift", False)
        config = attrs.get("Config", {})
        host = attrs.get("HostConfig", {})
        mounts = {
            mount.get("Destination"): mount
            for mount in attrs.get("Mounts", [])
            if not (
                mount.get("Type") == "tmpfs"
                and mount.get("Destination") == "/var/lib/postgresql/data"
            )
        }
        mount = mounts.get("/config")
        if (
            config.get("User") != "0:0"
            or config.get("Cmd") != ["sleep", "60"]
            or host.get("NetworkMode") != "none"
            or bool(host.get("PortBindings"))
            or host.get("AutoRemove") is not False
            or len(mounts) != 1
            or mount is None
            or mount.get("Type") != "volume"
            or mount.get("Name") != config_volume
            or mount.get("RW") is not True
        ):
            raise ProviderFailure("provider_drift", False)

    @staticmethod
    def _port(container: Container) -> int:
        ports = container.attrs.get("NetworkSettings", {}).get("Ports") or {}
        bindings = ports.get(_POSTGRES_PORT) or []
        if len(bindings) != 1:
            raise ProviderFailure("provider_drift", False)
        binding = bindings[0]
        if binding.get("HostIp") != "127.0.0.1":
            raise ProviderFailure("provider_drift", False)
        try:
            port = int(binding.get("HostPort", ""))
        except (TypeError, ValueError):
            raise ProviderFailure("provider_drift", False) from None
        if not 1 <= port <= 65535:
            raise ProviderFailure("provider_drift", False)
        return port

    def _verify_container(
        self,
        container: Container,
        job: ProvisioningJob,
        labels: dict[str, str],
        image_id: str,
        data_volume: str,
        config_volume: str,
    ) -> int:
        self._require_labels(container, labels)
        container.reload()
        attrs = container.attrs
        if attrs.get("Image") != image_id:
            raise ProviderFailure("provider_drift", False)
        host = attrs.get("HostConfig", {})
        config = attrs.get("Config", {})
        if host.get("NanoCpus") != job.cpu_millis * 1_000_000:
            raise ProviderFailure("provider_drift", False)
        if host.get("Memory") != job.memory_bytes:
            raise ProviderFailure("provider_drift", False)
        if (host.get("RestartPolicy") or {}).get("Name") != "unless-stopped":
            raise ProviderFailure("provider_drift", False)
        bindings = host.get("PortBindings") or {}
        postgres_bindings = bindings.get(_POSTGRES_PORT) or []
        if (
            set(bindings) != {_POSTGRES_PORT}
            or len(postgres_bindings) != 1
            or postgres_bindings[0].get("HostIp") != "127.0.0.1"
        ):
            raise ProviderFailure("provider_drift", False)
        env = set(config.get("Env") or [])
        if "POSTGRES_PASSWORD_FILE=/docker-entrypoint-initdb.d/admin_password" not in env:
            raise ProviderFailure("provider_drift", False)
        if "POSTGRES_HOST_AUTH_METHOD=scram-sha-256" not in env:
            raise ProviderFailure("provider_drift", False)
        if any(item.startswith("POSTGRES_PASSWORD=") for item in env):
            raise ProviderFailure("provider_drift", False)
        if config.get("User", "") != "":
            raise ProviderFailure("provider_drift", False)

        mounts = {mount.get("Destination"): mount for mount in attrs.get("Mounts", [])}
        data_mount = mounts.get("/var/lib/postgresql/data")
        config_mount = mounts.get("/docker-entrypoint-initdb.d")
        if (
            data_mount is None
            or data_mount.get("Type") != "volume"
            or data_mount.get("Name") != data_volume
            or data_mount.get("RW") is not True
            or config_mount is None
            or config_mount.get("Type") != "volume"
            or config_mount.get("Name") != config_volume
            or config_mount.get("RW") is not False
            or len(mounts) != 2
        ):
            raise ProviderFailure("provider_drift", False)
        return self._port(container)

    def _seed_and_start(
        self,
        job: ProvisioningJob,
        image: Image,
        labels: dict[str, str],
        data_name: str,
        config_name: str,
    ) -> Container:
        existing_data = self._volume(data_name)
        existing_config = self._volume(config_name)
        if existing_data is not None:
            self._require_labels(existing_data, labels)
        if existing_config is not None:
            self._require_labels(existing_config, labels)
        if existing_data is not None:
            if self._data_directory_initialized(job, image.id, data_name, labels):
                raise ProviderFailure("provider_drift", False)
        self._ensure_volume(data_name, labels)
        self._ensure_volume(config_name, labels)
        self._run_helper(
            job=job, image_id=image.id, config_volume=config_name, labels=labels, seed=True
        )
        container = self._client.containers.run(
            image.id,
            name=self._root_name(job),
            detach=True,
            labels=labels,
            environment={
                "POSTGRES_PASSWORD_FILE": "/docker-entrypoint-initdb.d/admin_password",
                "POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
            },
            ports={_POSTGRES_PORT: ("127.0.0.1", None)},
            volumes={
                data_name: {"bind": "/var/lib/postgresql/data", "mode": "rw"},
                config_name: {"bind": "/docker-entrypoint-initdb.d", "mode": "ro"},
            },
            nano_cpus=job.cpu_millis * 1_000_000,
            mem_limit=job.memory_bytes,
            restart_policy={"Name": "unless-stopped"},
            auto_remove=False,
        )
        return container

    def _data_directory_initialized(
        self,
        job: ProvisioningJob,
        image_id: str,
        data_volume: str,
        labels: dict[str, str],
    ) -> bool:
        helper_name = f"{self._root_name(job)}-init"
        previous = self._container(helper_name)
        if previous is not None:
            self._require_labels(previous, labels)
            try:
                self._verify_helper(
                    previous, job, image_id, f"{self._root_name(job)}-config", labels
                )
            except ProviderFailure:
                self._verify_data_probe_helper(previous, image_id, data_volume, labels)
            previous.remove(force=True)
        helper = self._client.containers.run(
            image_id,
            command=["sleep", "60"],
            name=helper_name,
            user="0:0",
            detach=True,
            labels=labels,
            volumes={data_volume: {"bind": "/data", "mode": "ro"}},
            network_mode="none",
            tmpfs={"/var/lib/postgresql/data": "rw,noexec,nosuid,size=1m"},
            auto_remove=False,
        )
        self._verify_data_probe_helper(helper, image_id, data_volume, labels)
        try:
            result = helper.exec_run(["test", "-f", "/data/PG_VERSION"])
            if result.exit_code not in (0, 1):
                raise ProviderFailure("provider_unavailable", True)
            exit_code: int = int(result.exit_code)
            return exit_code == 0
        finally:
            helper.remove(force=True)

    def _verify_data_probe_helper(
        self,
        helper: Container,
        image_id: str,
        data_volume: str,
        labels: dict[str, str],
    ) -> None:
        self._require_labels(helper, labels)
        helper.reload()
        attrs = helper.attrs
        mounts = {
            mount.get("Destination"): mount
            for mount in attrs.get("Mounts", [])
            if not (
                mount.get("Type") == "tmpfs"
                and mount.get("Destination") == "/var/lib/postgresql/data"
            )
        }
        mount = mounts.get("/data")
        if (
            attrs.get("Image") != image_id
            or attrs.get("Config", {}).get("User") != "0:0"
            or attrs.get("Config", {}).get("Cmd") != ["sleep", "60"]
            or attrs.get("HostConfig", {}).get("NetworkMode") != "none"
            or bool(attrs.get("HostConfig", {}).get("PortBindings"))
            or attrs.get("HostConfig", {}).get("AutoRemove") is not False
            or mount is None
            or mount.get("Type") != "volume"
            or mount.get("Name") != data_volume
            or mount.get("RW") is not False
            or len(mounts) != 1
        ):
            raise ProviderFailure("provider_drift", False)

    @staticmethod
    def _ready(container: Container, job: ProvisioningJob) -> bool:
        result = container.exec_run(
            [
                "psql",
                "-h",
                "127.0.0.1",
                "-U",
                job.credentials.user,
                "-d",
                job.credentials.database,
                "-tAc",
                "SELECT 1",
            ],
            environment={"PGPASSWORD": job.credentials.password},
        )
        return result.exit_code == 0 and bytes(result.output).strip() == b"1"

    def _wait_until_ready(self, container: Container, job: ProvisioningJob) -> None:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            container.reload()
            if container.status == "dead":
                raise ProviderFailure("provider_drift", False)
            if container.status == "running":
                try:
                    if self._ready(container, job):
                        return
                except ProviderFailure:
                    raise
                except Exception:
                    # Startup/authentication errors are retried only until the
                    # fixed readiness deadline; raw command output is discarded.
                    pass
            time.sleep(0.25)
        raise ProviderFailure("readiness_timeout", True)

    def _provision(self, job: ProvisioningJob) -> DatabaseEndpoint:
        self._validate_job(job)
        labels = self._labels(job)
        root = self._root_name(job)
        data_name = f"{root}-data"
        config_name = f"{root}-config"
        image = self._resolve_image()
        container = self._container(root)
        if container is None:
            container = self._seed_and_start(job, image, labels, data_name, config_name)
        else:
            self._required_volume(data_name, labels)
            self._required_volume(config_name, labels)
            self._verify_container(container, job, labels, image.id, data_name, config_name)
            container.reload()
            if container.status == "dead":
                raise ProviderFailure("provider_drift", False)
            if container.status == "paused":
                container.unpause()
            elif container.status != "running":
                container.start()

        port = self._verify_container(container, job, labels, image.id, data_name, config_name)
        self._wait_until_ready(container, job)
        self._run_helper(
            job=job, image_id=image.id, config_volume=config_name, labels=labels, seed=False
        )
        return DatabaseEndpoint(self._advertised_host, port)

    def _inspect(self, job: ProvisioningJob) -> DatabaseEndpoint | None:
        labels = self._labels(job)
        root = self._root_name(job)
        container = self._container(root)
        if container is None:
            return None
        data_name = f"{root}-data"
        config_name = f"{root}-config"
        self._required_volume(data_name, labels)
        self._required_volume(config_name, labels)
        image = self._local_image()
        port = self._verify_container(container, job, labels, image.id, data_name, config_name)
        if container.status != "running":
            return None
        try:
            if not self._ready(container, job):
                return None
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure("provider_unavailable", True) from None
        return DatabaseEndpoint(self._advertised_host, port)

    def _delete(self, job: ProvisioningJob) -> DeletionObservation:
        root = self._root_name(job)
        objects: list[tuple[str, Any]] = []
        for name in (root, f"{root}-init"):
            item = self._container(name)
            if item is not None:
                self._require_delete_labels(item, job)
                objects.append(("container", item))
        for name in (f"{root}-data", f"{root}-config"):
            item = self._volume(name)
            if item is not None:
                self._require_delete_labels(item, job)
                objects.append(("volume", item))

        observed = bool(objects)
        # Verify every object's ownership before making any deletion, so a name
        # collision never causes partial cleanup of somebody else's data.
        for kind, item in objects:
            if kind == "container":
                self._remove_if_present(item, force=True)
        for kind, item in objects:
            if kind == "volume":
                self._remove_if_present(item, force=True)
        return DeletionObservation(absent=True, observed_owned_object=observed)

    @staticmethod
    def _remove_if_present(item: Any, *, force: bool) -> None:
        try:
            item.remove(force=force)
        except NotFound:
            # A concurrent retry has already removed this exact object.
            return

    @classmethod
    def _require_delete_labels(cls, item: Any, job: ProvisioningJob) -> None:
        labels = cls._object_labels(item)
        if (
            labels.get(_MANAGED) != "true"
            or labels.get(_INSTALLATION) != str(job.installation_id)
            or labels.get(_RESOURCE) != str(job.resource_id)
        ):
            raise ProviderFailure("ownership_conflict", False)
        try:
            generation = int(labels.get(_GENERATION, ""))
        except ValueError:
            raise ProviderFailure("ownership_conflict", False) from None
        if generation < 1 or generation > job.generation:
            raise ProviderFailure("ownership_conflict", False)

    @staticmethod
    def _discovered_resource(item: Any, installation_id: UUID) -> UUID | None:
        labels = DockerPostgresProvider._object_labels(item)
        if labels.get(_MANAGED) != "true" or labels.get(_INSTALLATION) != str(installation_id):
            return None
        try:
            generation = int(labels[_GENERATION])
            resource_id = UUID(labels[_RESOURCE])
        except (KeyError, ValueError, TypeError):
            return None
        return resource_id if generation > 0 else None

    def _discover(self, installation_id: UUID) -> tuple[UUID, ...]:
        label = f"{_INSTALLATION}={installation_id}"
        found: set[UUID] = set()
        containers = self._client.containers.list(all=True, filters={"label": label})
        volumes = self._client.volumes.list(filters={"label": label})
        for item in (*containers, *volumes):
            resource_id = self._discovered_resource(item, installation_id)
            if resource_id is not None:
                found.add(resource_id)
        return tuple(sorted(found, key=str))
