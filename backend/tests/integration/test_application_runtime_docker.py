"""Opt-in Docker acceptance for app-to-database secret-file connectivity."""

import asyncio
import json
import os
import traceback
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import docker
import pytest
from cryptography.fernet import Fernet
from developer_platform.application.application_delivery.shared.ports import (
    ApplicationDeliveryFailure,
)
from developer_platform.application.resource_lifecycle.ports import (
    DatabaseCredentials,
    ProvisioningJob,
)
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from test_foundation_postgres import async_engine_for

from developer_platform.infra.persistence.application_bindings import (
    SQLAlchemyApplicationDatabaseBindings,
)
from developer_platform.infra.persistence.delivery import ApplicationRow
from developer_platform.infra.persistence.models import (
    ProjectEnvironmentRow,
    ProjectRegistrationRow,
    Resource,
    ResourceSecret,
)
from developer_platform.infra.providers.application_runtime import (
    managed_resource_container_name,
)
from developer_platform.infra.providers.docker_application import DockerApplicationAdapter
from developer_platform.infra.providers.docker_postgres import DockerPostgresProvider
from developer_platform.infra.security.credentials import FernetResourceCredentialCipher
from identity.infra.persistence.models import InternalUserRow, ProjectRow, TeamRow

pytestmark = pytest.mark.postgres


def test_owned_application_reads_private_database_file_and_runtime_cleanup_leaves_database(
    postgres_engine,
) -> None:
    socket = os.environ.get("PLATFORM_TEST_DOCKER_URL")
    if not socket:
        pytest.skip("Set PLATFORM_TEST_DOCKER_URL to an isolated permitted local Docker socket")
    image_reference = os.environ.get(
        "PLATFORM_TEST_APPLICATION_IMAGE", "devops-hub/generated-fastapi:acceptance"
    )
    installation_id, resource_id, application_id = uuid4(), uuid4(), uuid4()
    project_id, team_id, user_id, environment_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    project_name = f"runtime-{project_id}"
    credentials = DatabaseCredentials(
        user="appuser_" + resource_id.hex[:12],
        database="appdb_" + resource_id.hex[:12],
        password="runtime-private-" + uuid4().hex,
        administrator_password="admin-private-" + uuid4().hex,
    )
    key = Fernet.generate_key().decode()
    cipher = FernetResourceCredentialCipher(key, "runtime-acceptance")
    with Session(postgres_engine) as session, session.begin():
        session.add_all(
            [
                InternalUserRow(id=user_id, name=f"runtime-user-{user_id}"),
                ProjectRow(id=project_id, name=project_name),
                TeamRow(id=team_id, name=f"runtime-team-{team_id}"),
            ]
        )
        session.flush()
        session.add(
            ProjectRegistrationRow(
                project_id=project_id,
                name=project_name,
                owning_team_id=team_id,
                owning_team_name="runtime-acceptance",
                repository="company/runtime-acceptance",
                configured=True,
            )
        )
        session.flush()
        session.add(ProjectEnvironmentRow(id=environment_id, project_id=project_id, name="dev"))

    daemon = docker.DockerClient(base_url=socket, timeout=10)
    try:
        try:
            application_image = daemon.images.get(image_reference)
            daemon.images.get("postgres:16")
        except docker.errors.ImageNotFound:
            pytest.skip("The acceptance application and postgres:16 images must already be local")
        application_image_id = str(application_image.id)
        resource_name = managed_resource_container_name(installation_id, resource_id)
        job = ProvisioningJob(
            operation_id=uuid4(),
            resource_id=resource_id,
            installation_id=installation_id,
            generation=1,
            claim_token=uuid4(),
            action="provision",
            cpu_millis=500,
            memory_bytes=512 * 1024 * 1024,
            credentials=credentials,
        )
        provider = DockerPostgresProvider(socket, "postgres:16")
        database_engine = async_engine_for(postgres_engine)
        sessions = async_sessionmaker(database_engine, expire_on_commit=False)
        adapter = DockerApplicationAdapter(
            frozenset({application_image_id}),
            socket,
            "postgres:16",
            installation_id,
            SQLAlchemyApplicationDatabaseBindings(sessions, installation_id, cipher),
            health_timeout_seconds=90,
        )

        async def diagnostic_threaded(operation, *args):
            task = asyncio.create_task(asyncio.to_thread(operation, *args))
            try:
                return await asyncio.shield(task)
            except ApplicationDeliveryFailure as error:
                raise AssertionError(error.code) from None
            except Exception as error:
                frames = [
                    f"{frame.name}:{frame.lineno}"
                    for frame in traceback.extract_tb(error.__traceback__)
                ]
                raise AssertionError(f"{type(error).__name__}: {frames}") from None

        adapter._threaded = diagnostic_threaded
        database_attempted = False
        application_attempted = False
        try:
            database_attempted = True
            endpoint = asyncio.run(provider.provision(job))
            dsn = URL.create(
                "postgresql",
                username=credentials.user,
                password=credentials.password,
                host=resource_name,
                port=5432,
                database=credentials.database,
            ).render_as_string(hide_password=False)
            with Session(postgres_engine) as session, session.begin():
                session.add(
                    Resource(
                        id=resource_id,
                        environment_id=environment_id,
                        owner_id=user_id,
                        project_id=project_id,
                        display_name="runtime-db",
                        template_id="postgres",
                        target_id="local",
                        size_id="small",
                        configuration={},
                        work_reference=None,
                        desired_state="running",
                        status="ready",
                        revision=1,
                        generation=1,
                        installation_id=installation_id,
                        provider_id=resource_name,
                        endpoint={"host": endpoint.host, "port": endpoint.port},
                        created_at=now,
                        expires_at=now + timedelta(hours=1),
                    )
                )
                session.add(
                    ResourceSecret(
                        resource_id=resource_id,
                        key_id=cipher.key_id,
                        ciphertext=cipher.encrypt(resource_id, credentials),
                    )
                )
                session.flush()
                session.add(
                    ApplicationRow(
                        id=application_id,
                        project_id=project_id,
                        environment_id=environment_id,
                        owner_id=user_id,
                        name="runtime-app",
                        template_id="python-fastapi",
                        template_version="1.0.0",
                        repository_url="https://github.com/company/runtime-app",
                        resource_id=resource_id,
                        status="pending",
                        is_preview=False,
                        created_at=now,
                        updated_at=now,
                    )
                )
            application_attempted = True
            url, reference = asyncio.run(
                adapter.deploy(
                    project_id=project_id,
                    application_id=application_id,
                    deployment_id=uuid4(),
                    image_digest=application_image_id,
                    target_id="local",
                    resource_id=resource_id,
                    idempotency_key="runtime-acceptance",
                )
            )
            assert reference.startswith("devhub-")
            with urllib.request.urlopen(url + "/healthz", timeout=10) as response:
                assert response.status == 200
                assert json.load(response) == {"status": "ok"}
            assert credentials.password not in url
            app_container = daemon.containers.get(reference)
            app_container.reload()
            environment = app_container.attrs["Config"].get("Env", [])
            assert any(
                value == "DATABASE_URL_FILE=/run/devops-hub/database-url" for value in environment
            )
            assert all(not value.startswith("DATABASE_URL=") for value in environment)
            assert credentials.password not in "\n".join(environment)
            mount = next(
                item
                for item in app_container.attrs.get("Mounts", [])
                if item.get("Destination") == "/run/devops-hub"
            )
            assert mount.get("Type") == "volume" and mount.get("RW") is False
            assert credentials.password not in app_container.logs().decode(errors="replace")
            assert dsn not in app_container.logs().decode(errors="replace")
            network_name = adapter._network_name(application_id)
            network = daemon.networks.get(network_name)
            member_names = {
                member.get("Name") for member in network.attrs.get("Containers", {}).values()
            }
            assert {reference, resource_name} <= member_names

            asyncio.run(adapter.remove(project_id, application_id, "runtime-cleanup"))
            application_attempted = False
            assert daemon.containers.get(resource_name).status == "running"
            assert (
                len(
                    daemon.volumes.list(
                        filters={"label": f"devops-hub.application={application_id}"}
                    )
                )
                == 0
            )
            with pytest.raises(docker.errors.NotFound):
                daemon.networks.get(network_name)
        finally:
            cleanup_failed = False
            if application_attempted:
                try:
                    asyncio.run(adapter.remove(project_id, application_id, "runtime-final-cleanup"))
                except Exception:
                    cleanup_failed = True
            try:
                if database_attempted:
                    asyncio.run(provider.delete(job))
                if cleanup_failed:
                    asyncio.run(
                        adapter.remove(project_id, application_id, "runtime-network-cleanup")
                    )
            finally:
                asyncio.run(database_engine.dispose())
                provider._client.close()
    finally:
        daemon.close()
