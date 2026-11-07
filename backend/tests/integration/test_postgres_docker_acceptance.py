"""Opt-in real HTTP/PostgreSQL/Docker acceptance; owns only its UUID-labeled objects."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import docker
import psycopg
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from test_foundation_postgres import (
    PEPPER,
    async_engine_for,
    client_for,
    issue,
)

from developer_platform.application.resource_worker.handler import ResourceWorkerHandler
from developer_platform.containers.worker_queue import (
    PostgresResourceEffectGuard,
    SqlAlchemyProvisioningQueue,
)
from developer_platform.infra.credentials import FernetResourceCredentialCipher
from developer_platform.infra.docker_provider import DockerPostgresProvider
from developer_platform.infra.persistence.models import (
    Operation,
    QuotaBudget,
    Reservation,
    Resource,
    ResourceSecret,
)
from shared.infra.settings import Settings

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("cleanup_reason", ["explicit", "expiry"])
def test_request_connect_restart_extend_delete(postgres_engine, tmp_path, cleanup_reason):
    socket = os.environ.get("PLATFORM_TEST_DOCKER_URL")
    if not socket:
        pytest.skip("Set PLATFORM_TEST_DOCKER_URL to an isolated permitted local Docker socket")
    assert socket.startswith("unix://")
    installation = uuid4()
    key = Fernet.generate_key().decode()
    config = Settings(
        database_url=postgres_engine.url.render_as_string(hide_password=False),
        token_pepper=PEPPER,
        installation_id=installation,
        resource_key=key,
        resource_key_id="acceptance",
        local_provider_enabled=True,
        docker_url=socket,
    )
    _, token = issue(postgres_engine, tmp_path / "credential")
    _, foreign_token = issue(
        postgres_engine, tmp_path / "foreign", user="foreign", project="foreign"
    )
    with Session(postgres_engine) as session, session.begin():
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=2,
                max_cpu_millis=2000,
                max_memory_bytes=2**31,
                max_storage_bytes=2**32,
            )
        )
    database = async_engine_for(postgres_engine)
    cipher = FernetResourceCredentialCipher(key, "acceptance")
    provider = DockerPostgresProvider(socket, "postgres:16")
    daemon = docker.DockerClient(base_url=socket)
    queue = SqlAlchemyProvisioningQueue(
        async_sessionmaker(database, expire_on_commit=False), installation, cipher, "acceptance"
    )
    job = None
    try:
        with client_for(postgres_engine, config) as client:
            headers = {"Authorization": "Bearer " + token, "Idempotency-Key": "acceptance"}
            project = client.get("/api/v1/projects", headers=headers).json()[0]
            body = {
                "project_id": project["project_id"],
                "environment_id": project["environments"][0]["id"],
                "display_name": "acceptance-db",
                "template_id": "postgres",
                "version": "16",
                "target_id": "local",
                "size_id": "small",
                "ttl_seconds": 3600,
            }
            first = client.post("/api/v1/resources", json=body, headers=headers)
            assert first.status_code == 202
            accepted = first.json()
            assert client.post("/api/v1/resources", json=body, headers=headers).json() == accepted
            resource_id, operation_id = (
                UUID(accepted["resource_id"]),
                UUID(accepted["operation_id"]),
            )
            # Simulate a worker process stopping after the effect but before its completion write.
            job = asyncio.run(queue.claim())
            assert job is not None and job.resource_id == resource_id
            endpoint = asyncio.run(provider.provision(job))
            with Session(postgres_engine) as session, session.begin():
                session.get(Operation, operation_id).claim_expires_at = datetime.now(
                    UTC
                ) - timedelta(seconds=1)
            restarted_queue = SqlAlchemyProvisioningQueue(
                async_sessionmaker(database, expire_on_commit=False),
                installation,
                cipher,
                "acceptance",
            )
            restarted = ResourceWorkerHandler(
                restarted_queue, provider, PostgresResourceEffectGuard(database)
            )
            assert asyncio.run(restarted.tick())
            view = client.get(f"/api/v1/resources/{resource_id}", headers=headers).json()
            assert view["status"] == "ready"
            owned = daemon.containers.list(
                all=True,
                filters={
                    "label": [
                        f"devops-hub.installation={installation}",
                        f"devops-hub.resource={resource_id}",
                    ]
                },
            )
            assert len(owned) == 1
            owned[0].restart(timeout=10)
            # Provision retry adopts the same object and credentials after a real container restart.
            assert asyncio.run(provider.provision(job)).host == endpoint.host
            # Docker may reassign an ephemeral host port on restart. Reconciliation
            # must persist its new observed endpoint before returning connection info.
            asyncio.run(restarted_queue.reconcile((resource_id,)))
            assert asyncio.run(restarted.tick())
            connection = client.post(f"/api/v1/resources/{resource_id}/connection", headers=headers)
            assert connection.status_code == 200
            assert "no-store" in connection.headers["cache-control"]
            assert (
                client.post(
                    f"/api/v1/resources/{resource_id}/connection",
                    headers={"Authorization": "Bearer " + foreign_token},
                ).status_code
                == 404
            )
            foreign_headers = {"Authorization": "Bearer " + foreign_token}
            assert (
                client.get(f"/api/v1/resources/{resource_id}", headers=foreign_headers).status_code
                == 404
            )
            assert (
                client.delete(
                    f"/api/v1/resources/{resource_id}", headers=foreign_headers
                ).status_code
                == 404
            )
            assert (
                client.post(
                    f"/api/v1/resources/{resource_id}/renew",
                    headers=foreign_headers,
                    json={
                        "expected_revision": view["revision"],
                        "expires_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
                    },
                ).status_code
                == 404
            )
            secret = connection.json()["connection_string"]
            ordinary = client.get(
                f"/api/v1/projects/{project['project_id']}/resources", headers=headers
            )
            assert job.credentials.password not in ordinary.text
            assert secret not in ordinary.text
            with psycopg.connect(secret) as db:
                db.execute("CREATE TABLE acceptance (value integer)")
                db.execute("INSERT INTO acceptance VALUES (42)")
                assert db.execute("SELECT value FROM acceptance").fetchone() == (42,)
                assert db.execute(
                    "SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
                ).fetchone() == (False,)
            renewal = {
                "expected_revision": view["revision"],
                "expires_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            }
            assert (
                client.post(
                    f"/api/v1/resources/{resource_id}/renew", json=renewal, headers=headers
                ).status_code
                == 200
            )
            assert (
                client.post(
                    f"/api/v1/resources/{resource_id}/renew", json=renewal, headers=headers
                ).status_code
                == 409
            )
            if cleanup_reason == "expiry":
                with Session(postgres_engine) as session, session.begin():
                    row = session.get(Resource, resource_id)
                    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                assert asyncio.run(restarted.tick())
            deletion = client.delete(f"/api/v1/resources/{resource_id}", headers=headers)
            assert deletion.status_code == 202
            assert (
                client.delete(f"/api/v1/resources/{resource_id}", headers=headers).json()
                == deletion.json()
            )
            if cleanup_reason == "explicit":
                assert asyncio.run(restarted.tick())
            assert (
                client.get(f"/api/v1/resources/{resource_id}", headers=headers).json()["status"]
                == "deleted"
            )
            assert asyncio.run(provider.discover(installation)) == ()
            with pytest.raises(psycopg.OperationalError):
                psycopg.connect(secret, connect_timeout=1)
            with Session(postgres_engine) as session:
                assert session.get(Reservation, resource_id).released_at is not None
                assert session.get(ResourceSecret, resource_id) is None
            assert client.post("/api/v1/resources", json=body, headers=headers).json() == accepted
    finally:
        if job is not None:
            asyncio.run(provider.delete(job))
        daemon.close()
        asyncio.run(database.dispose())
