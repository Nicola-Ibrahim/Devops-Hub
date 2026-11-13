import asyncio
import hashlib
import hmac
import json
from pathlib import Path
from uuid import uuid4

import pytest
from devops_platform.application.application_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    TemplateVersion,
)

from devops_platform.domain.aggregates.application_delivery import ApplicationDelivery
from devops_platform.domain.entities.application import Application, DeliveryStep
from devops_platform.infra.security.webhooks import HmacGitHubWebhookVerifier
from devops_platform.infra.templates.catalog import FilesystemTemplateCatalog

TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "src/devops_platform/infra/templates/catalogs"


def test_delivery_aggregate_retry_resets_failed_step_and_application_state() -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    application_id = uuid4()
    step_id = uuid4()
    delivery = ApplicationDelivery(
        Application(
            id=application_id,
            project_id=uuid4(),
            environment_id=uuid4(),
            owner_id=uuid4(),
            name="example",
            template_id="python-fastapi",
            template_version="1.0.0",
            status="failed",
            created_at=now,
            updated_at=now,
        ),
        (
            DeliveryStep(
                id=step_id,
                application_id=application_id,
                kind="repository",
                status="failed",
                attempts=2,
                created_at=now,
                updated_at=now,
                error_code="provider_unavailable",
            ),
        ),
    )

    retried = delivery.retry(step_id, now)

    assert retried.application.status == "pending"
    assert retried.application.updated_at == now
    assert retried.steps[0].status == "pending"
    assert retried.steps[0].error_code is None
    assert retried.steps[0].attempts == 2


def test_catalog_lists_and_renders_only_versioned_templates() -> None:
    catalog = FilesystemTemplateCatalog(TEMPLATE_ROOT)

    found = {(item.template_id, item.version) for item in catalog.list_templates()}
    assert found == {
        ("python-fastapi", "1.0.0"),
        ("nodejs-http", "1.0.0"),
        ("aspnet-core", "1.0.0"),
    }

    files = catalog.render("python-fastapi", "1.0.0", {"application_name": "payments-api"})
    by_path = {item.path: item for item in files}
    assert "app/main.py" in by_path
    assert b"payments-api" in by_path["README.md"].content
    assert b"__APPLICATION_NAME__" not in by_path["README.md"].content
    provenance = json.loads(by_path[".platform-template.json"].content)
    assert provenance["template_id"] == "python-fastapi"
    assert provenance["template_version"] == "1.0.0"
    assert "README.md" in provenance["managed_files"]


def test_catalog_renders_self_contained_workflows() -> None:
    catalog = FilesystemTemplateCatalog(TEMPLATE_ROOT)
    for template_id in ("python-fastapi", "nodejs-http", "aspnet-core"):
        files = catalog.render(template_id, "1.0.0", {"application_name": "demo"})
        workflow = next(item.content for item in files if item.path == ".github/workflows/ci.yml")
        assert b"__PLATFORM_WORKFLOWS_REPOSITORY__" not in workflow
        assert b"reusable-ci-" not in workflow


def test_catalog_rejects_path_traversal() -> None:
    catalog = FilesystemTemplateCatalog(TEMPLATE_ROOT)
    with pytest.raises(ApplicationDeliveryFailure, match="template_not_found"):
        catalog.get("../secrets", "1.0.0")


def test_github_signature_validation_is_constant_time_and_body_bound() -> None:
    secret = "test-secret"
    body = b'{"action":"opened"}'
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    verifier = HmacGitHubWebhookVerifier(secret)
    payload, digest = verifier.verify(body, signature)
    assert payload == {"action": "opened"}
    assert digest == hashlib.sha256(body).hexdigest()
    with pytest.raises(ApplicationDeliveryFailure, match="webhook_signature_invalid"):
        verifier.verify(body + b" ", signature)


def test_template_file_symlink_is_rejected(tmp_path: Path) -> None:
    version = tmp_path / "python-fastapi" / "1.0.0"
    version.mkdir(parents=True)
    (version / "template.json").write_text(
        json.dumps(
            {
                "id": "python-fastapi",
                "version": "1.0.0",
                "language": "python",
                "display_name": "Python",
                "description": "Test",
            }
        )
    )
    outside = tmp_path / "outside.txt"
    outside.write_text("not template data")
    (version / "README.md").symlink_to(outside)
    catalog = FilesystemTemplateCatalog(tmp_path)

    with pytest.raises(ApplicationDeliveryFailure, match="template_invalid"):
        catalog.render("python-fastapi", "1.0.0", {})


def test_disabled_repository_adapter_does_not_claim_success() -> None:
    from devops_platform.infra.providers.github import GitHubRepositoryAdapter

    adapter = GitHubRepositoryAdapter("", None)

    async def run() -> None:
        with pytest.raises(ApplicationDeliveryFailure, match="repository_provider_disabled"):
            await adapter.create_repository(
                project_id=uuid4(),
                application_id=uuid4(),
                name="sample",
                template=TemplateVersion("python-fastapi", "1.0.0", "python", "Python", "Test"),
                files=(),
                idempotency_key="request-1",
            )

    asyncio.run(run())


def test_template_update_pr_preserves_user_changes_and_uses_owned_branch(monkeypatch):
    import base64

    import httpx
    from devops_platform.application.application_delivery.shared.ports import GeneratedFile

    from devops_platform.infra.providers.github import GitHubRepositoryAdapter

    def digest(value):
        return hashlib.sha256(value).hexdigest()

    old = {
        "template_id": "python-fastapi",
        "template_version": "1.0.0",
        "managed_files": {
            "app/main.py": digest(b"original"),
            "README.md": digest(b"original docs"),
        },
    }
    proposed = {"template_id": "python-fastapi", "template_version": "2.0.0", "managed_files": {}}
    files = tuple(
        GeneratedFile(path, content, digest(content))
        for path, content in {
            "app/main.py": b"new code",
            "README.md": b"new docs",
            ".platform-template.json": json.dumps(proposed).encode(),
        }.items()
    )
    writes = []

    def handler(request):
        path = request.url.path
        if request.method == "GET":
            if path.endswith("/org/demo"):
                return httpx.Response(200, json={"default_branch": "main", "private": True})
            if path.endswith("/pulls"):
                return httpx.Response(200, json=[])
            if path.endswith("/git/ref/heads/main"):
                return httpx.Response(200, json={"object": {"sha": "base"}})
            if path.endswith("/git/commits/base"):
                return httpx.Response(200, json={"tree": {"sha": "tree"}})
            content = (
                json.dumps(old).encode()
                if path.endswith(".platform-template.json")
                else b"original"
                if path.endswith("app/main.py")
                else b"user-edited docs"
            )
            return httpx.Response(200, json={"content": base64.b64encode(content).decode()})
        payload = json.loads(request.content)
        writes.append((path, payload))
        if path.endswith("/pulls"):
            return httpx.Response(201, json={"html_url": "https://github.com/org/demo/pull/1"})
        return httpx.Response(201, json={"sha": "generated"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = asyncio.run(
        GitHubRepositoryAdapter("org", "synthetic-test-token").create_update_pull_request(
            repository_url="https://github.com/org/demo",
            branch="platform/template-2",
            files=files,
            idempotency_key="update-request",
        )
    )
    assert result.endswith("/pull/1")
    tree = next(payload for path, payload in writes if path.endswith("/git/trees"))
    assert {item["path"] for item in tree["tree"]} == {"app/main.py", ".platform-template.json"}
    assert all(payload.get("force") is not True for _, payload in writes)
