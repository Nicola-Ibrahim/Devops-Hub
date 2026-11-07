import asyncio
import hashlib
import hmac
import json
from pathlib import Path
from uuid import uuid4

import pytest

from developer_platform.application.application_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    TemplateVersion,
)
from developer_platform.infra.delivery_adapters import (
    FilesystemTemplateCatalog,
    HmacGitHubWebhookVerifier,
)

TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "../templates"


def test_catalog_lists_and_renders_only_versioned_templates() -> None:
    catalog = FilesystemTemplateCatalog(TEMPLATE_ROOT, "company/platform-workflows")

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


def test_catalog_rejects_unapproved_workflow_reference() -> None:
    catalog = FilesystemTemplateCatalog(TEMPLATE_ROOT)
    with pytest.raises(ApplicationDeliveryFailure, match="template_workflow_not_configured"):
        catalog.render("python-fastapi", "1.0.0", {"application_name": "demo"})


def test_catalog_rejects_path_traversal() -> None:
    catalog = FilesystemTemplateCatalog(TEMPLATE_ROOT, "company/platform-workflows")
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
    catalog = FilesystemTemplateCatalog(tmp_path, "company/workflows")

    with pytest.raises(ApplicationDeliveryFailure, match="template_invalid"):
        catalog.render("python-fastapi", "1.0.0", {})


def test_disabled_repository_adapter_does_not_claim_success() -> None:
    from developer_platform.infra.delivery_adapters import GitHubRepositoryAdapter

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

    from developer_platform.application.application_delivery.shared.ports import GeneratedFile
    from developer_platform.infra.delivery_adapters import GitHubRepositoryAdapter

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
