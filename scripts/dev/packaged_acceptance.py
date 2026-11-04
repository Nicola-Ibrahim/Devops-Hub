"""Opt-in disposable Compose acceptance; requires prebuilt acceptance image tags.

Run with backend/.venv/bin/python and an explicitly permitted
PLATFORM_TEST_DOCKER_URL Unix socket. Uses local ports 8000 and 3000;
Compose fails safely if they are occupied. Removes only its unique project and
installation-labeled resource objects. Never prints generated credentials.
"""

import base64
import json
import os
import re
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
        output = run(
            compose
            + [
                "exec",
                "-T",
                "api",
                "platform-admin",
                "register-project",
                "--name",
                "demo",
                "--team",
                "platform",
                "--repository",
                "example/demo",
                "--environment",
                "dev",
            ]
        )
        project_id = re.search(
            r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", output
        ).group()
        output = run(
            compose
            + [
                "exec",
                "-T",
                "api",
                "platform-admin",
                "create-user",
                "--name",
                "demo",
                "--password-file",
                "/run/platform-secrets/acceptance_password",
            ]
        )
        user_id = re.search(
            r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", output
        ).group()
        run(
            compose
            + [
                "exec",
                "-T",
                "api",
                "platform-admin",
                "bootstrap-project-admin",
                "--user-id",
                user_id,
                "--project-id",
                project_id,
            ]
        )
        run(
            compose
            + [
                "run",
                "--rm",
                "--no-deps",
                "worker",
                "platform-admin",
                "verify-local-target",
                "--max-resources",
                "3",
            ]
        )
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
