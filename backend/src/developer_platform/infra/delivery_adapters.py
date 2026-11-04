"""Safe local adapters for approved templates and explicitly configured providers."""

import base64
import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from developer_platform.application.delivery import (
    ApplicationDeliveryFailure,
    ApprovedImageCatalog,
    GeneratedFile,
    RequestFingerprint,
    TemplateCatalog,
    TemplateVersion,
    WebhookSignatureVerifier,
)
from developer_platform.infra.application_runtime import (
    ApplicationDatabaseBindingResolver,
    DockerApplicationRuntime,
)


class Sha256RequestFingerprint(RequestFingerprint):
    """Stable request identity encoding for idempotency conflict checks."""

    def for_value(self, value: object) -> str:
        payload = json.dumps(value.__dict__, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode()).hexdigest()


class HmacGitHubWebhookVerifier(WebhookSignatureVerifier):
    """Authenticates GitHub's raw-body signature before parsing its JSON payload."""

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("GitHub webhook secret must not be empty")
        self._secret = secret.encode()

    def verify(self, raw_body: bytes, signature: str | None) -> tuple[dict[str, object], str]:
        if not signature or not signature.startswith("sha256="):
            raise ApplicationDeliveryFailure("webhook_signature_invalid", retryable=False)
        expected = hmac.new(self._secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature[7:], expected):
            raise ApplicationDeliveryFailure("webhook_signature_invalid", retryable=False)
        try:
            payload = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError):
            raise ApplicationDeliveryFailure("webhook_payload_invalid", retryable=False) from None
        if not isinstance(payload, dict):
            raise ApplicationDeliveryFailure("webhook_payload_invalid", retryable=False)
        return payload, hashlib.sha256(raw_body).hexdigest()


class FilesystemTemplateCatalog(TemplateCatalog):
    """Reads versioned templates without allowing path traversal or symlink escape."""

    _TOKEN = re.compile(r"__[A-Z][A-Z0-9_]{1,63}__")
    _MAX_FILES = 500
    _MAX_FILE_BYTES = 1024 * 1024

    def __init__(self, root: Path, workflow_repository: str | None = None) -> None:
        self.root = root.resolve()
        self.workflow_repository = workflow_repository

    def list_templates(self) -> tuple[TemplateVersion, ...]:
        found: list[TemplateVersion] = []
        if not self.root.is_dir():
            return ()
        for descriptor in sorted(self.root.glob("*/[0-9]*.*/template.json")):
            try:
                found.append(self._metadata(json.loads(descriptor.read_text(encoding="utf-8"))))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return tuple(found)

    def get(self, template_id: str, version: str) -> TemplateVersion:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", template_id) or not re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+", version
        ):
            raise ApplicationDeliveryFailure("template_not_found", retryable=False)
        directory = (self.root / template_id / version).resolve()
        if self.root not in directory.parents or not directory.is_dir():
            raise ApplicationDeliveryFailure("template_not_found", retryable=False)
        descriptor = directory / "template.json"
        try:
            if descriptor.is_symlink():
                raise ApplicationDeliveryFailure("template_invalid", retryable=False)
            metadata = self._metadata(json.loads(descriptor.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            raise ApplicationDeliveryFailure("template_invalid", retryable=False) from None
        if metadata.template_id != template_id or metadata.version != version:
            raise ApplicationDeliveryFailure("template_invalid", retryable=False)
        return metadata

    def render(
        self, template_id: str, version: str, values: dict[str, str]
    ) -> tuple[GeneratedFile, ...]:
        self.get(template_id, version)
        if self.workflow_repository is None or not re.fullmatch(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.workflow_repository
        ):
            raise ApplicationDeliveryFailure("template_workflow_not_configured", retryable=False)
        directory = self.root / template_id / version
        result: list[GeneratedFile] = []
        paths = sorted(path for path in directory.rglob("*") if path.is_file())
        if len(paths) > self._MAX_FILES:
            raise ApplicationDeliveryFailure("template_too_large", retryable=False)
        manifest: dict[str, str] = {}
        for path in paths:
            if path.is_symlink() or path.name == "template.json":
                if path.is_symlink():
                    raise ApplicationDeliveryFailure("template_invalid", retryable=False)
                continue
            resolved = path.resolve()
            if directory.resolve() not in resolved.parents:
                raise ApplicationDeliveryFailure("template_invalid", retryable=False)
            relative = path.relative_to(directory).as_posix()
            if relative.startswith("/") or ".." in Path(relative).parts:
                raise ApplicationDeliveryFailure("template_invalid", retryable=False)
            raw = path.read_bytes()
            if len(raw) > self._MAX_FILE_BYTES:
                raise ApplicationDeliveryFailure("template_too_large", retryable=False)
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = None
            if content is not None:
                content = content.replace(
                    "__PLATFORM_WORKFLOWS_REPOSITORY__", self.workflow_repository
                )
                for key, value in values.items():
                    token_key = key.upper()
                    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", token_key):
                        raise ApplicationDeliveryFailure("template_value_invalid", retryable=False)
                    if "\n" in value or "\r" in value:
                        raise ApplicationDeliveryFailure("template_value_invalid", retryable=False)
                    content = content.replace(f"__{token_key}__", value)
                if self._TOKEN.search(content):
                    raise ApplicationDeliveryFailure("template_value_missing", retryable=False)
                raw = content.encode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()
            manifest[relative] = digest
            result.append(GeneratedFile(relative, raw, digest))
        provenance = {
            "template_id": template_id,
            "template_version": version,
            "managed_files": manifest,
        }
        raw_manifest = (json.dumps(provenance, sort_keys=True, indent=2) + "\n").encode()
        result.append(
            GeneratedFile(
                ".platform-template.json", raw_manifest, hashlib.sha256(raw_manifest).hexdigest()
            )
        )
        return tuple(result)

    @staticmethod
    def _metadata(data: Any) -> TemplateVersion:
        if not isinstance(data, dict):
            raise ValueError("invalid template descriptor")
        return TemplateVersion(
            template_id=str(data["id"]),
            version=str(data["version"]),
            language=str(data["language"]),
            display_name=str(data["display_name"]),
            description=str(data["description"]),
        )


class StaticApprovedImageCatalog(ApprovedImageCatalog):
    """Exact allowlist for immutable digest references."""

    def __init__(self, approved: dict[str, frozenset[str]]) -> None:
        self.approved = approved

    def is_approved(self, digest: str, target_id: str) -> bool:
        return digest in self.approved.get(target_id, frozenset())


class GitHubRepositoryAdapter:
    """Optional GitHub adapter. It has no network capability until configured."""

    def __init__(
        self, organization: str, token: str | None, api_url: str = "https://api.github.com"
    ) -> None:
        self.organization = organization
        self.token = token
        self.api_url = api_url.rstrip("/")

    def _configured(self) -> str:
        if not self.token or not re.fullmatch(r"[A-Za-z0-9_.-]+", self.organization):
            raise ApplicationDeliveryFailure("repository_provider_disabled", retryable=False)
        return self.token

    async def create_repository(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        name: str,
        template: TemplateVersion,
        files: tuple[GeneratedFile, ...],
        idempotency_key: str,
    ) -> str:
        token = self._configured()
        try:
            import httpx
        except ImportError:
            raise ApplicationDeliveryFailure(
                "repository_client_unavailable", retryable=False
            ) from None
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.api_url}/orgs/{self.organization}/repos",
                headers=headers,
                json={
                    "name": name,
                    "private": True,
                    "auto_init": True,
                    "description": (
                        f"DevOps Hub managed application {application_id} project {project_id}"
                    ),
                },
            )
            if response.status_code == 422:
                response = await client.get(
                    f"{self.api_url}/repos/{self.organization}/{name}", headers=headers
                )
                if response.status_code != 200:
                    raise ApplicationDeliveryFailure("repository_conflict", retryable=False)
                data = response.json()
                expected = f"DevOps Hub managed application {application_id} project {project_id}"
                if data.get("description") != expected or data.get("private") is not True:
                    raise ApplicationDeliveryFailure("repository_conflict", retryable=False)
            elif response.status_code not in (200, 201):
                raise ApplicationDeliveryFailure("repository_provider_failure")
            else:
                data = response.json()
            full_name = data.get("full_name")
            if full_name != f"{self.organization}/{name}":
                raise ApplicationDeliveryFailure("repository_identity_invalid", retryable=False)
            default_branch = str(data.get("default_branch", "main"))
            for item in files:
                await self._create_file(client, headers, full_name, default_branch, item)
            return str(data["html_url"])

    async def _create_file(
        self,
        client: Any,
        headers: dict[str, str],
        repository: str,
        branch: str,
        item: GeneratedFile,
    ) -> None:
        encoded = base64.b64encode(item.content).decode("ascii")
        url = f"{self.api_url}/repos/{repository}/contents/{item.path}"
        payload = {
            "message": f"Add platform template file {item.path}",
            "content": encoded,
            "branch": branch,
        }
        response = await client.put(url, headers=headers, json=payload)
        if response.status_code in (200, 201):
            return
        if response.status_code == 422:
            existing = await client.get(url, headers=headers, params={"ref": branch})
            if existing.status_code == 200:
                data = existing.json()
                if (
                    data.get("sha")
                    and base64.b64decode(data.get("content", "").replace("\n", "")) == item.content
                ):
                    return
                raise ApplicationDeliveryFailure("repository_file_conflict", retryable=False)
        raise ApplicationDeliveryFailure("repository_provider_failure")

    async def create_update_pull_request(
        self,
        *,
        repository_url: str,
        branch: str,
        files: tuple[GeneratedFile, ...],
        idempotency_key: str,
    ) -> str:
        import httpx

        token = self._configured()
        match = re.fullmatch(
            r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", repository_url
        )
        if match is None or match.group(1).casefold() != self.organization.casefold():
            raise ApplicationDeliveryFailure("repository_identity_invalid", retryable=False)
        repository = f"{match.group(1)}/{match.group(2)}"
        marker = "platform-template-update:" + hashlib.sha256(idempotency_key.encode()).hexdigest()
        update_branch = "platform/template-" + marker.split(":")[1][:24]
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        endpoint = f"{self.api_url}/repos/{repository}"
        generated = {item.path: item for item in files}
        if ".platform-template.json" not in generated:
            raise ApplicationDeliveryFailure("template_provenance_missing", retryable=False)
        proposed = json.loads(generated[".platform-template.json"].content)
        async with httpx.AsyncClient(timeout=20) as client:

            async def get(path: str, **kwargs: Any) -> Any:
                response = await client.get(endpoint + path, headers=headers, **kwargs)
                if response.status_code != 200:
                    raise ApplicationDeliveryFailure("repository_provider_failure")
                return response.json()

            metadata = await get("")
            base_branch = metadata["default_branch"]
            if metadata.get("private") is not True:
                raise ApplicationDeliveryFailure("repository_identity_invalid", retryable=False)
            existing_prs = await get(
                "/pulls", params={"state": "open", "head": f"{self.organization}:{update_branch}"}
            )
            if existing_prs:
                return str(existing_prs[0]["html_url"])
            base = await get("/git/ref/heads/" + base_branch)
            base_sha = base["object"]["sha"]
            manifest = await get("/contents/.platform-template.json", params={"ref": base_sha})
            old = json.loads(base64.b64decode(manifest["content"]))
            managed = old.get("managed_files")
            if not isinstance(managed, dict) or old.get("template_id") != proposed.get(
                "template_id"
            ):
                raise ApplicationDeliveryFailure("template_provenance_invalid", retryable=False)
            preserved = dict(managed)
            changes = []
            for path, item in generated.items():
                if path == ".platform-template.json":
                    continue
                if path.startswith("/") or ".." in Path(path).parts or "\\" in path:
                    raise ApplicationDeliveryFailure("template_path_invalid", retryable=False)
                response = await client.get(
                    endpoint + "/contents/" + path, headers=headers, params={"ref": base_sha}
                )
                if response.status_code == 200:
                    remote = response.json()
                    actual = hashlib.sha256(base64.b64decode(remote["content"])).hexdigest()
                    # User-owned edits stay untouched. Already updated files are retry-safe.
                    if actual not in {managed.get(path), item.sha256}:
                        continue
                    if actual == item.sha256:
                        preserved[path] = item.sha256
                        continue
                elif response.status_code != 404:
                    raise ApplicationDeliveryFailure("repository_provider_failure")
                elif path in managed:
                    # A user deletion is an edit too.
                    continue
                changes.append(
                    {
                        "path": path,
                        "mode": "100644",
                        "type": "blob",
                        "content": item.content.decode(),
                    }
                )
                preserved[path] = item.sha256
            if not changes:
                raise ApplicationDeliveryFailure("template_no_safe_updates", retryable=False)
            proposed["managed_files"] = preserved
            changes.append(
                {
                    "path": ".platform-template.json",
                    "mode": "100644",
                    "type": "blob",
                    "content": json.dumps(proposed, sort_keys=True, indent=2) + "\n",
                }
            )
            base_commit = await get("/git/commits/" + base_sha)
            tree_response = await client.post(
                endpoint + "/git/trees",
                headers=headers,
                json={"base_tree": base_commit["tree"]["sha"], "tree": changes},
            )
            if tree_response.status_code != 201:
                raise ApplicationDeliveryFailure("repository_provider_failure")
            commit_response = await client.post(
                endpoint + "/git/commits",
                headers=headers,
                json={
                    "message": marker,
                    "tree": tree_response.json()["sha"],
                    "parents": [base_sha],
                },
            )
            if commit_response.status_code != 201:
                raise ApplicationDeliveryFailure("repository_provider_failure")
            branch_response = await client.post(
                endpoint + "/git/refs",
                headers=headers,
                json={"ref": "refs/heads/" + update_branch, "sha": commit_response.json()["sha"]},
            )
            if branch_response.status_code == 422:
                # Resume only the exact commit authored for this operation; never force a ref.
                current = await get("/git/ref/heads/" + update_branch)
                commit = await get("/git/commits/" + current["object"]["sha"])
                if commit.get("message") != marker:
                    raise ApplicationDeliveryFailure("template_branch_conflict", retryable=False)
            elif branch_response.status_code != 201:
                raise ApplicationDeliveryFailure("repository_provider_failure")
            result = await client.post(
                endpoint + "/pulls",
                headers=headers,
                json={
                    "title": "Update approved application template",
                    "head": update_branch,
                    "base": base_branch,
                    "body": (
                        "Review template changes before merging. "
                        "Locally edited files were preserved."
                    ),
                },
            )
            if result.status_code == 201:
                return str(result.json()["html_url"])
            if result.status_code == 422:
                existing = await get(
                    "/pulls",
                    params={"state": "open", "head": f"{self.organization}:{update_branch}"},
                )
                if existing:
                    return str(existing[0]["html_url"])
            raise ApplicationDeliveryFailure("repository_provider_failure")


class DockerApplicationAdapter:
    """Local Docker deployer for allowlisted images and securely bound resources."""

    def __init__(
        self,
        approved_images: frozenset[str],
        runtime: DockerApplicationRuntime,
        installation_id: UUID,
        bindings: ApplicationDatabaseBindingResolver | None,
    ) -> None:
        self.approved_images = approved_images
        self.runtime = runtime
        self.installation_id = installation_id
        self.bindings = bindings

    async def deploy(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        deployment_id: UUID,
        image_digest: str,
        target_id: str,
        resource_id: UUID | None,
        idempotency_key: str,
    ) -> tuple[str, str]:
        if target_id != "local" or image_digest not in self.approved_images:
            raise ApplicationDeliveryFailure("image_not_approved", retryable=False)
        binding = None
        if resource_id is not None:
            if self.bindings is None:
                raise ApplicationDeliveryFailure(
                    "resource_configuration_not_configured", retryable=False
                )
            binding = await self.bindings.resolve(project_id, application_id, resource_id)
        return await self.runtime.deploy(
            project_id=project_id,
            application_id=application_id,
            deployment_id=deployment_id,
            installation_id=self.installation_id,
            image_digest=image_digest,
            binding=binding,
        )

    async def remove(self, project_id: UUID, application_id: UUID, idempotency_key: str) -> None:
        await self.runtime.remove(
            project_id=project_id,
            application_id=application_id,
            installation_id=self.installation_id,
        )
