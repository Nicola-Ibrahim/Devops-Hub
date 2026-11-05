"""Opt-in disposable Compose acceptance; requires prebuilt acceptance image tags.

Run with backend/.venv/bin/python and an explicitly permitted
PLATFORM_TEST_DOCKER_URL Unix socket. Uses local ports 8000 and 3000;
Compose fails safely if they are occupied. Removes only its unique project and
installation-labeled resource objects. Never prints generated credentials.
"""

import base64
import json
import os
import secrets
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import docker
import httpx

root = Path(__file__).resolve().parents[2]
docker_url = os.environ.get("PLATFORM_TEST_DOCKER_URL", "")
if not docker_url.startswith("unix://"):
    raise SystemExit("Explicit PLATFORM_TEST_DOCKER_URL Unix socket is required")
project = "devops-hub-test-" + uuid.uuid4().hex[:12]
installation = str(uuid.uuid4())
with tempfile.TemporaryDirectory(prefix="hub-packaged-", dir="/private/tmp") as scratch:
    path = Path(scratch)
    path.chmod(0o700)
    password = secrets.token_hex(24)
    values = {
        "postgres_password": password,
        "platform_database_url": f"postgresql+psycopg://platform:{password}@postgres:5432/platform",
        "platform_token_pepper": secrets.token_hex(48),
        "platform_installation_id": installation,
        "platform_resource_encryption_key": base64.urlsafe_b64encode(
            os.urandom(32)
        ).decode(),
        "platform_resource_key_id": "acceptance",
        "platform_metrics_token": secrets.token_hex(48),
    }
    for name, value in values.items():
        (path / name).write_text(value + "\n")
        (path / name).chmod(0o600)
    login_password = secrets.token_hex(24)
    (path / "password").write_text(login_password)
    (path / "password").chmod(0o600)
    override = path / "override.yaml"
    override.write_text("services:\n  postgres:\n    image: postgres:16\n")
    env = dict(
        os.environ,
        DOCKER_HOST=docker_url,
        PLATFORM_SECRETS_DIR=str(path),
        PLATFORM_API_IMAGE="devops-hub/backend:acceptance",
        PLATFORM_FRONTEND_IMAGE="devops-hub/frontend:acceptance",
        PLATFORM_LOCAL_PROVIDER_ENABLED="true",
        PLATFORM_COOKIE_SECURE="false",
    )
    compose = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(root / "compose.yaml"),
        "-f",
        str(override),
        "--profile",
        "app",
    ]

    def run(args, check=True):
        result = subprocess.run(
            args, cwd=root, env=env, text=True, capture_output=True, check=False
        )
        if check and result.returncode:
            # Commands carry no credential values; provider/SQL response bodies stay private.
            detail = result.stderr[-3000:]
            for private_value in [*values.values(), login_password]:
                detail = detail.replace(private_value, "[REDACTED]")
            print(detail)
            raise RuntimeError("Packaged check command failed: " + " ".join(args[:7]))
        return result.stdout.strip()

    daemon = docker.DockerClient(base_url=docker_url)
    try:
        run(
            compose
            + [
                "up",
                "-d",
                "--no-build",
                "--wait",
                "--wait-timeout",
                "90",
                "api",
                "frontend",
            ]
        )
        api = run(compose + ["ps", "-q", "api"])
        written = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                api,
                "sh",
                "-c",
                "umask 077; cat > /run/platform-secrets/acceptance_password",
            ],
            check=False,
            input=login_password,
            text=True,
            capture_output=True,
        )
        assert written.returncode == 0, "Private test password delivery failed"
        run(
            [
                "docker",
                "exec",
                api,
                "chmod",
                "600",
                "/run/platform-secrets/acceptance_password",
            ]
        )
        seed_fixture = r"""import asyncio, json
from pathlib import Path
from containers.factory import create_container
from containers.project_registration import RegisterProjectCommandHandler
from identity.containers.browser_operations import BrowserIdentityService
from containers.schema import registered_metadata
from developer_platform.application.ledger import RegisterProjectCommand
from shared.infra.settings import Settings
from api.identity.browser import BrowserIdentityOperations

async def seed():
    settings = Settings()
    registered_metadata()
    container = create_container(settings)
    try:
        async with container() as scope:
            registration = await scope.get(RegisterProjectCommandHandler)
            project = await registration.execute(
                RegisterProjectCommand("demo", "platform", "example/demo", ("dev",))
            )
            identity = await scope.get(BrowserIdentityOperations)
            assert isinstance(identity, BrowserIdentityService)
            password = Path("/run/platform-secrets/acceptance_password").read_text().strip()
            user_id = await identity.create_user("demo", password)
            await identity.bootstrap_first_project_admin(user_id, project.project_id)
        print(json.dumps({"project_id": str(project.project_id), "user_id": str(user_id)}))
    finally:
        await container.close()

asyncio.run(seed())
"""
        seeded = subprocess.run(
            ["docker", "exec", "-i", api, "python", "-"],
            cwd=root, env=env, text=True, input=seed_fixture, capture_output=True, check=False,
        )
        if seeded.returncode:
            raise RuntimeError("Packaged identity fixture setup failed; private details suppressed")
        identifiers = json.loads(seeded.stdout.strip().splitlines()[-1])
        project_id = identifiers["project_id"]
        probe_fixture = r"""import asyncio, secrets
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from containers.schema import registered_metadata
from developer_platform.application.lifecycle import DatabaseCredentials, ProvisioningJob
from developer_platform.infra.docker_provider import DockerPostgresProvider
from developer_platform.infra.persistence.models import QuotaBudget
from shared.infra.settings import Settings
from shared.infra.persistence.database import create_async_database_engine

async def probe():
    settings = Settings()
    if settings.installation_id is None or settings.resource_key is None:
        raise RuntimeError("Acceptance target configuration is incomplete")
    registered_metadata()
    engine = create_async_database_engine(settings.database_url.get_secret_value(), settings.database_connect_timeout)
    try:
        job = ProvisioningJob(uuid4(), uuid4(), settings.installation_id, 1, uuid4(),
            "provision", 500, 536870912,
            DatabaseCredentials("verify_user", "verify_db", secrets.token_urlsafe(32), secrets.token_urlsafe(32)))
        provider = DockerPostgresProvider(settings.docker_url, settings.postgres_image, settings.advertised_host)
        try:
            await provider.provision(job)
            await provider.provision(job)
        finally:
            observation = await provider.delete(job)
            if not observation.absent:
                raise RuntimeError("Owned target probe cleanup incomplete")
        async with AsyncSession(engine) as session, session.begin():
            session.add(QuotaBudget(scope="target", scope_id="local", max_resources=3,
                max_cpu_millis=1500, max_memory_bytes=1610612736, max_storage_bytes=3221225472))
    finally:
        await engine.dispose()

asyncio.run(probe())
"""
        checked_probe = subprocess.run(
            compose + ["run", "--rm", "--no-deps", "-T", "worker", "python", "-"],
            cwd=root, env=env, text=True, input=probe_fixture, capture_output=True, check=False,
        )
        if checked_probe.returncode:
            raise RuntimeError("Owned local-target probe failed; private details suppressed")
        run(compose + ["up", "-d", "--no-build", "worker"])
        with httpx.Client(base_url="http://127.0.0.1:3000", timeout=10) as client:
            assert client.get("/").status_code == 200
            headers = {"Origin": "http://127.0.0.1:3000"}
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "userName": "demo",
                    "password": login_password,
                    "projectId": project_id,
                },
                headers=headers,
            )
            assert response.status_code == 200, (
                "Packaged browser login failed: "
                + str(response.status_code)
                + " "
                + response.text[:500]
            )
            headers["X-CSRF-Token"] = response.json()["csrfToken"]
            projects = client.get("/api/v1/projects").json()
            command = {
                "project_id": project_id,
                "environment_id": projects[0]["environments"][0]["id"],
                "display_name": "packaged-db",
                "template_id": "postgres",
                "version": "16",
                "target_id": "local",
                "size_id": "small",
                "ttl_seconds": 3600,
            }
            response = client.post(
                "/api/v1/resources",
                json=command,
                headers=dict(headers, **{"Idempotency-Key": "packaged-demo"}),
            )
            assert response.status_code == 202, "Packaged resource request failed"
            resource = response.json()["resource_id"]
            for _ in range(80):
                data = client.get("/api/v1/resources/" + resource).json()
                if data.get("status") == "ready":
                    break
                time.sleep(0.5)
            if data.get("status") != "ready":
                print("Packaged sanitized resource state:", json.dumps(data))
                print(
                    "Packaged sanitized worker events:",
                    run(compose + ["logs", "--tail", "10", "worker"], check=False),
                )
            assert data.get("status") == "ready", "Packaged worker did not provision"
            assert (
                client.post(
                    "/api/v1/resources/" + resource + "/connection", headers=headers
                ).status_code
                == 200
            )
            assert (
                client.delete(
                    "/api/v1/resources/" + resource, headers=headers
                ).status_code
                == 202
            )
            for _ in range(40):
                data = client.get("/api/v1/resources/" + resource).json()
                if data.get("status") == "deleted":
                    break
                time.sleep(0.5)
            assert data.get("status") == "deleted", "Packaged worker cleanup incomplete"
        print(
            "PACKAGED ACCEPTANCE PASSED: migrations, nonroot API, frontend proxy/cookie/CSRF, internal account, provider probe, worker request/ready/connection/deletion."
        )
    finally:
        owned = {
            "label": [
                "devops-hub.managed=true",
                "devops-hub.installation=" + installation,
            ]
        }
        for item in daemon.containers.list(all=True, filters=owned):
            item.remove(force=True, v=True)
        for item in daemon.volumes.list(filters=owned):
            item.remove(force=True)
        run(compose + ["down", "--volumes", "--remove-orphans"], check=False)
        daemon.close()
