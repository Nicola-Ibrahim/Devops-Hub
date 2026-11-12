# ruff: noqa: F401
"""Safe local adapters for approved templates and explicitly configured providers."""

import base64
import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from developer_platform.application.workload_delivery.shared.models import (
    GeneratedFile,
    TemplateVersion,
)
from developer_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    ApprovedImageCatalog,
    RequestFingerprint,
    TemplateCatalog,
    WebhookSignatureVerifier,
)


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
