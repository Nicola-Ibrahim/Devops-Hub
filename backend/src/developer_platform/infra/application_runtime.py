"""Owned Docker runtime for approved local application deployments."""

from __future__ import annotations

import asyncio
import io
import tarfile
import time
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

from developer_platform.application.workload_delivery.shared.database_binding import (
    ApplicationDatabaseBinding as ApplicationDatabaseBinding,
)
from developer_platform.application.workload_delivery.shared.database_binding import (
    ApplicationDatabaseBindingResolver as ApplicationDatabaseBindingResolver,
)
from developer_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
)

_T = TypeVar("_T")
_MANAGED = "devops-hub.managed"
_INSTALLATION = "devops-hub.installation"
_PROJECT = "devops-hub.project"
_APPLICATION = "devops-hub.application"
_DEPLOYMENT = "devops-hub.deployment"
_RESOURCE = "devops-hub.resource"
_DATABASE_URL_FILE = "/run/devops-hub/database-url"


def managed_resource_container_name(installation_id: UUID, resource_id: UUID) -> str:
    return f"dh-{installation_id.hex[:8]}-{resource_id.hex}"


class DockerApplicationRuntime:
    """Runs application containers with resource credentials in a private file volume."""

    def __init__(
        self,
        docker_url: str,
        operator_image: str,
        health_timeout_seconds: int = 60,
    ) -> None:
        if not docker_url.startswith("unix://") or not operator_image:
            raise ValueError("A configured Unix Docker socket and operator image are required")
        self.docker_url = docker_url
        self.operator_image = operator_image
        self.health_timeout_seconds = health_timeout_seconds

    async def deploy(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        deployment_id: UUID,
        installation_id: UUID,
        image_digest: str,
        binding: ApplicationDatabaseBinding | None,
    ) -> tuple[str, str]:
        return await self._threaded(
            self._deploy,
            project_id,
            application_id,
            deployment_id,
            installation_id,
            image_digest,
            binding,
        )

    async def remove(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        installation_id: UUID,
    ) -> None:
        await self._threaded(self._remove, project_id, application_id, installation_id)

    async def _threaded(self, operation: Callable[..., _T], *args: object) -> _T:
        try:
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
                if not task.cancelled():
                    task.exception()
                raise
        except ApplicationDeliveryFailure:
            raise
        except Exception:
            # Docker exceptions can contain daemon addresses and configuration.
            raise ApplicationDeliveryFailure("deployment_provider_failure") from None

    @staticmethod
    def _labels(
        installation_id: UUID,
        project_id: UUID,
        application_id: UUID,
        deployment_id: UUID | None = None,
    ) -> dict[str, str]:
        labels = {
            _MANAGED: "true",
            _INSTALLATION: str(installation_id),
            _PROJECT: str(project_id),
            _APPLICATION: str(application_id),
        }
        if deployment_id is not None:
            labels[_DEPLOYMENT] = str(deployment_id)
        return labels

    @staticmethod
    def _object_labels(item: Any) -> dict[str, str]:
        labels = getattr(item, "labels", None)
        if labels is not None:
            return dict(labels)
        attrs = getattr(item, "attrs", {})
        if isinstance(attrs, dict):
            config = attrs.get("Config", {})
            return dict(attrs.get("Labels") or config.get("Labels") or {})
        return {}

    @classmethod
    def _require_labels(cls, item: Any, expected: dict[str, str], code: str) -> None:
        labels = cls._object_labels(item)
        if any(labels.get(key) != value for key, value in expected.items()):
            raise ApplicationDeliveryFailure(code, retryable=False)

    @staticmethod
    def _resource_labels(binding: ApplicationDatabaseBinding) -> dict[str, str]:
        return {
            _MANAGED: "true",
            _INSTALLATION: str(binding.installation_id),
            _RESOURCE: str(binding.resource_id),
        }

    @staticmethod
    def _name(application_id: UUID, deployment_id: UUID) -> str:
        return f"devhub-{application_id.hex[:16]}-{deployment_id.hex[:12]}"

    @staticmethod
    def _network_name(application_id: UUID) -> str:
        return f"devhub-app-{application_id.hex}"

    @staticmethod
    def _volume_name(deployment_id: UUID) -> str:
        return f"devhub-deploy-{deployment_id.hex}-config"

    @staticmethod
    def _archive(dsn: str) -> bytes:
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as archive:
            entry = tarfile.TarInfo("database-url")
            entry.size = len(dsn.encode("utf-8"))
            entry.mode = 0o400
            entry.uid = 10001
            entry.gid = 10001
            entry.uname = ""
            entry.gname = ""
            archive.addfile(entry, io.BytesIO(dsn.encode("utf-8")))
        return output.getvalue()

    def _deploy(
        self,
        project_id: UUID,
        application_id: UUID,
        deployment_id: UUID,
        installation_id: UUID,
        image_digest: str,
        binding: ApplicationDatabaseBinding | None,
    ) -> tuple[str, str]:
        import docker  # type: ignore[import-untyped]
        from docker.errors import NotFound  # type: ignore[import-untyped]

        client = docker.DockerClient(base_url=self.docker_url, timeout=10)
        name = self._name(application_id, deployment_id)
        if binding is not None and binding.installation_id != installation_id:
            raise ApplicationDeliveryFailure("resource_installation_mismatch", retryable=False)
        if binding is not None and (
            binding.project_id != project_id or binding.application_id != application_id
        ):
            raise ApplicationDeliveryFailure("resource_ownership_conflict", retryable=False)
        labels = self._labels(installation_id, project_id, application_id, deployment_id)
        volume = None
        network = None
        database = None
        existing_container = None
        try:
            app_image = client.images.get(image_digest)
            image_id = str(app_image.id)
            image_config = app_image.attrs.get("Config", {})
            if image_config.get("Volumes"):
                raise ApplicationDeliveryFailure(
                    "application_image_volumes_unsupported", retryable=False
                )
            try:
                existing_container = client.containers.get(name)
            except NotFound:
                pass
            else:
                self._verify_application_container(
                    existing_container,
                    image_id,
                    labels,
                    deployment_id,
                    application_id,
                    binding,
                )
            if binding is not None:
                volume_name = self._volume_name(deployment_id)
                try:
                    volume = client.volumes.get(volume_name)
                    self._require_labels(
                        volume,
                        {**labels, _DEPLOYMENT: str(deployment_id)},
                        "deployment_volume_ownership_conflict",
                    )
                except NotFound:
                    volume = client.volumes.create(
                        name=volume_name,
                        labels={**labels, _DEPLOYMENT: str(deployment_id)},
                    )
                database = client.containers.get(binding.container_name)
                self._require_labels(
                    database,
                    self._resource_labels(binding),
                    "database_container_ownership_conflict",
                )
                database.reload()
                if database.status != "running":
                    raise ApplicationDeliveryFailure("resource_not_ready")
                network_name = self._network_name(application_id)
                network_labels = {
                    **self._labels(installation_id, project_id, application_id),
                    _RESOURCE: str(binding.resource_id),
                }
                try:
                    network = client.networks.get(network_name)
                    self._require_labels(
                        network, network_labels, "deployment_network_ownership_conflict"
                    )
                except NotFound:
                    network = client.networks.create(
                        network_name, driver="bridge", labels=network_labels, internal=True
                    )
                network.reload()
                network_attrs = network.attrs
                if (
                    network_attrs.get("Driver") != "bridge"
                    or network_attrs.get("Internal") is not True
                ):
                    raise ApplicationDeliveryFailure(
                        "deployment_network_configuration_conflict", retryable=False
                    )
                self._validate_network_members(
                    client, network, project_id, application_id, installation_id, binding
                )
                self._ensure_network_member(network, database, binding.container_name)
                self._write_database_url(client, volume, deployment_id, labels, binding.dsn)

            if existing_container is not None:
                container = existing_container
            else:
                kwargs: dict[str, Any] = {
                    "name": name,
                    "detach": True,
                    "labels": labels,
                    "ports": {"8080/tcp": ("127.0.0.1", None)},
                    "read_only": True,
                    "security_opt": ["no-new-privileges"],
                    "cap_drop": ["ALL"],
                    "user": "10001:10001",
                    "mem_limit": "512m",
                    "nano_cpus": 500_000_000,
                    "pids_limit": 128,
                }
                if network is not None:
                    kwargs["network"] = network.name
                if volume is not None:
                    kwargs["volumes"] = {volume.name: {"bind": "/run/devops-hub", "mode": "ro"}}
                    kwargs["environment"] = {"DATABASE_URL_FILE": _DATABASE_URL_FILE}
                container = client.containers.run(image_id, **kwargs)

            self._verify_application_container(
                container,
                image_id,
                labels,
                deployment_id,
                application_id,
                binding,
            )

            port = self._wait_healthy(container)
            self._remove_previous_deployments(
                client, project_id, application_id, deployment_id, labels
            )
            return f"http://127.0.0.1:{port}", name
        except ApplicationDeliveryFailure:
            raise
        finally:
            client.close()

    def _write_database_url(
        self,
        client: Any,
        volume: Any,
        deployment_id: UUID,
        labels: dict[str, str],
        dsn: str,
    ) -> None:
        import docker

        helper_name = f"devhub-config-{deployment_id.hex[:16]}"
        helper_labels = {**labels, "devops-hub.helper": "configuration"}
        image = client.images.get(self.operator_image)
        image_id = str(image.id)
        try:
            helper = client.containers.get(helper_name)
            self._verify_configuration_helper(helper, image_id, helper_labels, volume.name)
            helper.remove(force=True)
        except docker.errors.NotFound:
            pass
        helper = client.containers.run(
            image_id,
            command=["sleep", "60"],
            name=helper_name,
            detach=True,
            labels=helper_labels,
            user="0:0",
            volumes={volume.name: {"bind": "/config", "mode": "rw"}},
            network_mode="none",
            tmpfs={"/var/lib/postgresql/data": "rw,noexec,nosuid,size=1m"},
            auto_remove=False,
        )
        try:
            self._verify_configuration_helper(helper, image_id, helper_labels, volume.name)
            if not helper.put_archive("/config", self._archive(dsn)):
                raise ApplicationDeliveryFailure("configuration_write_failed")
        finally:
            helper.remove(force=True)

    @classmethod
    def _verify_configuration_helper(
        cls, helper: Any, image_id: str, labels: dict[str, str], volume_name: str
    ) -> None:
        cls._require_labels(helper, labels, "deployment_helper_ownership_conflict")
        helper.reload()
        attrs = helper.attrs
        config = attrs.get("Config", {})
        host = attrs.get("HostConfig", {})
        mounts = [mount for mount in attrs.get("Mounts", []) if mount.get("Type") != "tmpfs"]
        config_mount = mounts[0] if len(mounts) == 1 else None
        tmpfs = host.get("Tmpfs", {})
        if (
            attrs.get("Image") != image_id
            or config.get("Cmd") != ["sleep", "60"]
            or config.get("User") != "0:0"
            or host.get("NetworkMode") != "none"
            or bool(host.get("PortBindings"))
            or host.get("Privileged") is not False
            or host.get("AutoRemove") is not False
            or set(tmpfs) != {"/var/lib/postgresql/data"}
            or config_mount is None
            or config_mount.get("Type") != "volume"
            or config_mount.get("Name") != volume_name
            or config_mount.get("Destination") != "/config"
            or config_mount.get("RW") is not True
            or helper.status != "running"
        ):
            raise ApplicationDeliveryFailure(
                "deployment_helper_configuration_conflict", retryable=False
            )

    def _verify_application_container(
        self,
        container: Any,
        image_id: str,
        labels: dict[str, str],
        deployment_id: UUID,
        application_id: UUID,
        binding: ApplicationDatabaseBinding | None,
    ) -> None:
        self._require_labels(container, labels, "container_ownership_conflict")
        container.reload()
        attrs = container.attrs
        config = attrs.get("Config", {})
        host = attrs.get("HostConfig", {})
        ports = host.get("PortBindings", {}).get("8080/tcp", [])
        mounts = attrs.get("Mounts", [])
        expected_volume_name = self._volume_name(deployment_id)
        if binding is None:
            expected_mounts: list[Any] = []
            expected_database_file = None
        else:
            expected_mounts = [
                {
                    "Type": "volume",
                    "Name": expected_volume_name,
                    "Destination": "/run/devops-hub",
                    "RW": False,
                }
            ]
            expected_database_file = f"DATABASE_URL_FILE={_DATABASE_URL_FILE}"
        environment = config.get("Env") or []
        volume_mounts = [mount for mount in mounts if mount.get("Type") != "tmpfs"]
        try:
            port = ports[0]
        except (IndexError, TypeError):
            port = {}
        network_name = self._network_name(application_id)
        networks = attrs.get("NetworkSettings", {}).get("Networks", {})
        expected_network = network_name if binding is not None else "bridge"
        database_file_values = [
            value for value in environment if value.startswith("DATABASE_URL_FILE=")
        ]
        unsafe_connection_values = any(value.startswith("DATABASE_URL=") for value in environment)
        if (
            attrs.get("Image") != image_id
            or config.get("User") != "10001:10001"
            or host.get("Privileged") is not False
            or host.get("ReadonlyRootfs") is not True
            or host.get("Binds") not in (None, [])
            or host.get("NanoCpus") != 500_000_000
            or host.get("Memory") != 512 * 1024 * 1024
            or host.get("PidsLimit") != 128
            or "ALL" not in (host.get("CapDrop") or [])
            or not any("no-new-privileges" in item for item in host.get("SecurityOpt") or [])
            or len(ports) != 1
            or port.get("HostIp") != "127.0.0.1"
            or not port.get("HostPort")
            or len(volume_mounts) != len(expected_mounts)
            or any(
                not any(
                    all(mount.get(key) == value for key, value in expected.items())
                    for mount in volume_mounts
                )
                for expected in expected_mounts
            )
            or (expected_database_file is None and database_file_values)
            or (
                expected_database_file is not None
                and database_file_values != [expected_database_file]
            )
            or unsafe_connection_values
            or config.get("Cmd") is not None
            and binding is not None
            and binding.dsn in config.get("Cmd", [])
            or expected_network not in networks
        ):
            raise ApplicationDeliveryFailure("container_configuration_conflict", retryable=False)

    @staticmethod
    def _validate_network_members(
        client: Any,
        network: Any,
        project_id: UUID,
        application_id: UUID,
        installation_id: UUID,
        binding: ApplicationDatabaseBinding,
    ) -> None:
        containers = network.attrs.get("Containers", {})
        for container_id, member in containers.items():
            try:
                attached = client.containers.get(container_id)
            except Exception:
                attached = client.containers.get(member.get("Name", ""))
            labels = DockerApplicationRuntime._object_labels(attached)
            own_database = (
                labels.get(_MANAGED) == "true"
                and labels.get(_INSTALLATION) == str(installation_id)
                and labels.get(_RESOURCE) == str(binding.resource_id)
            )
            own_application = (
                labels.get(_MANAGED) == "true"
                and labels.get(_INSTALLATION) == str(installation_id)
                and labels.get(_PROJECT) == str(project_id)
                and labels.get(_APPLICATION) == str(application_id)
            )
            if not (own_database or own_application):
                raise ApplicationDeliveryFailure(
                    "deployment_network_ownership_conflict", retryable=False
                )

    @staticmethod
    def _ensure_network_member(network: Any, container: Any, alias: str) -> None:
        network.reload()
        members = network.attrs.get("Containers", {})
        if container.id not in members:
            network.connect(container, aliases=[alias])

    def _wait_healthy(self, container: Any) -> str:
        deadline = time.monotonic() + self.health_timeout_seconds
        while time.monotonic() < deadline:
            container.reload()
            state = container.attrs.get("State", {})
            if container.status != "running":
                raise ApplicationDeliveryFailure("deployment_not_ready")
            health = state.get("Health", {}).get("Status")
            if health == "healthy":
                port = (
                    container.attrs.get("NetworkSettings", {})
                    .get("Ports", {})
                    .get("8080/tcp", [{}])[0]
                    .get("HostPort")
                )
                if not port:
                    raise ApplicationDeliveryFailure("deployment_not_ready")
                return str(port)
            if health == "unhealthy":
                raise ApplicationDeliveryFailure("deployment_not_ready")
            time.sleep(0.5)
        raise ApplicationDeliveryFailure("deployment_not_ready")

    def _remove_previous_deployments(
        self,
        client: Any,
        project_id: UUID,
        application_id: UUID,
        deployment_id: UUID,
        expected: dict[str, str],
    ) -> None:
        containers = client.containers.list(
            all=True,
            filters={
                "label": [
                    f"{_MANAGED}=true",
                    f"{_APPLICATION}={application_id}",
                ]
            },
        )
        volumes = client.volumes.list(
            filters={
                "label": [
                    f"{_MANAGED}=true",
                    f"{_APPLICATION}={application_id}",
                ]
            }
        )
        expected_owner = {
            _MANAGED: "true",
            _PROJECT: str(project_id),
            _APPLICATION: str(application_id),
            _INSTALLATION: expected[_INSTALLATION],
        }
        old_deployment_ids: set[str] = set()
        for previous in containers:
            self._require_labels(previous, expected_owner, "container_ownership_conflict")
            old_id = self._object_labels(previous).get(_DEPLOYMENT)
            if old_id is None:
                raise ApplicationDeliveryFailure("container_ownership_conflict", retryable=False)
            if old_id != str(deployment_id):
                old_deployment_ids.add(old_id)
        for volume in volumes:
            volume_labels = self._object_labels(volume)
            self._require_labels(volume, expected_owner, "deployment_volume_ownership_conflict")
            deployment_label = volume_labels.get(_DEPLOYMENT)
            if deployment_label is None:
                raise ApplicationDeliveryFailure(
                    "deployment_volume_ownership_conflict", retryable=False
                )
            if deployment_label != str(deployment_id):
                old_deployment_ids.add(deployment_label)
        for previous in containers:
            if previous.labels.get(_DEPLOYMENT) != str(deployment_id):
                previous.remove(force=True)
        for volume in volumes:
            if self._object_labels(volume).get(_DEPLOYMENT) in old_deployment_ids:
                volume.remove(force=True)

    def _remove(self, project_id: UUID, application_id: UUID, installation_id: UUID) -> None:
        import docker
        from docker.errors import NotFound

        client = docker.DockerClient(base_url=self.docker_url, timeout=10)
        expected = self._labels(installation_id, project_id, application_id)
        try:
            containers = client.containers.list(
                all=True,
                filters={"label": [f"{_MANAGED}=true", f"{_APPLICATION}={application_id}"]},
            )
            volumes = client.volumes.list(
                filters={"label": [f"{_MANAGED}=true", f"{_APPLICATION}={application_id}"]}
            )
            networks = client.networks.list(
                filters={"label": [f"{_MANAGED}=true", f"{_APPLICATION}={application_id}"]}
            )
            # Validate every candidate, including connected network members, before
            # removing any container or volume.
            for container in containers:
                self._require_labels(container, expected, "container_ownership_conflict")
            for volume in volumes:
                self._require_labels(volume, expected, "deployment_volume_ownership_conflict")
            for network in networks:
                network.reload()
                self._require_labels(network, expected, "deployment_network_ownership_conflict")
                network_resource_id = self._object_labels(network).get(_RESOURCE)
                if (
                    network_resource_id is None
                    or network.attrs.get("Driver") != "bridge"
                    or network.attrs.get("Internal") is not True
                ):
                    raise ApplicationDeliveryFailure(
                        "deployment_network_ownership_conflict", retryable=False
                    )
                for container_id in tuple(network.attrs.get("Containers", {})):
                    try:
                        attached = client.containers.get(container_id)
                    except NotFound:
                        continue
                    member_labels = self._object_labels(attached)
                    if not (
                        member_labels.get(_MANAGED) == "true"
                        and member_labels.get(_INSTALLATION) == str(installation_id)
                        and member_labels.get(_PROJECT) == str(project_id)
                        and member_labels.get(_APPLICATION) == str(application_id)
                    ) and not (
                        member_labels.get(_MANAGED) == "true"
                        and member_labels.get(_INSTALLATION) == str(installation_id)
                        and member_labels.get(_RESOURCE) == network_resource_id
                    ):
                        raise ApplicationDeliveryFailure(
                            "deployment_network_ownership_conflict", retryable=False
                        )
            for container in containers:
                container.remove(force=True)
            for volume in volumes:
                volume.remove(force=True)
            for network in networks:
                network.reload()
                for container_id in tuple(network.attrs.get("Containers", {})):
                    try:
                        attached = client.containers.get(container_id)
                    except NotFound:
                        continue
                    if self._object_labels(attached).get(_RESOURCE) == self._object_labels(
                        network
                    ).get(_RESOURCE):
                        network.disconnect(attached)
                try:
                    network.remove()
                except NotFound:
                    continue
        finally:
            client.close()
