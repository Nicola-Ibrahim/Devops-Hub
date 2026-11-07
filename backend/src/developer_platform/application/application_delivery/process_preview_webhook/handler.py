"""Validate and record approved GitHub pull-request preview events."""

import re
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from developer_platform.application.application_delivery.process_preview_webhook.command import (
    ProcessGithubPreviewWebhookCommand,
)
from developer_platform.application.application_delivery.process_preview_webhook.port import (
    PreviewWebhookRepository,
)
from developer_platform.application.application_delivery.shared.models import WebhookResult
from developer_platform.application.application_delivery.shared.ports import (
    ApprovedImageCatalog,
    WebhookSignatureVerifier,
)
from developer_platform.application.shared.errors import PlatformRequestError

_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
_DIGEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,250}@sha256:[a-f0-9]{64}\Z")


def _safe_repository_name(value: str) -> bool:
    return bool(_REPOSITORY.fullmatch(value)) and ".." not in value


class ProcessGithubPreviewWebhookHandler:
    def __init__(
        self,
        repository: PreviewWebhookRepository,
        clock: Callable[[], datetime],
        images: ApprovedImageCatalog,
        webhook_verifier: WebhookSignatureVerifier | None,
        allowed_repository_owner: str | None,
        preview_owner_id: UUID | None,
        preview_ttl_seconds: int,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.images = images
        self.webhook_verifier = webhook_verifier
        self.allowed_repository_owner = allowed_repository_owner
        self.preview_owner_id = preview_owner_id
        self.preview_ttl_seconds = preview_ttl_seconds

    async def execute(self, command: ProcessGithubPreviewWebhookCommand) -> WebhookResult:
        raw_body, signature = command.raw_body, command.signature
        delivery_id, event = command.delivery_id, command.event
        if self.webhook_verifier is None or self.allowed_repository_owner is None:
            raise PlatformRequestError(
                "webhooks_disabled", "GitHub preview events are not configured", 503
            )
        if len(raw_body) > 1024 * 1024 or not re.fullmatch(r"[A-Fa-f0-9-]{16,100}", delivery_id):
            raise PlatformRequestError("webhook_invalid", "Webhook envelope is invalid", 400)
        payload, payload_hash = self.webhook_verifier.verify(raw_body, signature)
        action = payload.get("action")
        repository_data = payload.get("repository")
        pull_request = payload.get("pull_request")
        if (
            event != "pull_request"
            or not isinstance(action, str)
            or action not in {"opened", "reopened", "synchronize", "closed"}
            or not isinstance(repository_data, dict)
            or not isinstance(pull_request, dict)
        ):
            raise PlatformRequestError("webhook_invalid", "Unsupported GitHub event", 400)
        repository = repository_data.get("full_name")
        if not isinstance(repository, str) or not _safe_repository_name(repository):
            raise PlatformRequestError("webhook_invalid", "Repository identity is invalid", 400)
        owner, _ = repository.split("/", 1)
        if owner.casefold() != self.allowed_repository_owner.casefold():
            raise PlatformRequestError("webhook_forbidden", "Repository is not approved", 403)
        number = pull_request.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise PlatformRequestError("webhook_invalid", "Pull request identity is invalid", 400)
        recorded = await self.repository.record_webhook(
            delivery_id=delivery_id,
            payload_hash=payload_hash,
            event=event,
            repository=repository.casefold(),
            pull_request=number,
            action=action,
            now=self.clock(),
        )
        if not recorded:
            return WebhookResult(True, True, None, reason="duplicate_delivery")
        registered = await self.repository.find_registered_repository(repository.casefold())
        if registered is None:
            return WebhookResult(False, False, None, reason="repository_not_registered")
        if action == "closed":
            count = await self.repository.close_preview(
                repository=repository.casefold(), pull_request=number, now=self.clock()
            )
            return WebhookResult(True, False, None, cleanup_count=count)
        head = pull_request.get("head")
        base = pull_request.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            return WebhookResult(False, False, None, reason="pull_request_head_missing")
        head_repo = head.get("repo")
        base_repo = base.get("repo")
        if not isinstance(head_repo, dict) or not isinstance(base_repo, dict):
            return WebhookResult(False, False, None, reason="pull_request_repo_missing")
        head_full_name, base_full_name = head_repo.get("full_name"), base_repo.get("full_name")
        if (
            not isinstance(head_full_name, str)
            or head_full_name.casefold() != repository.casefold()
        ):
            return WebhookResult(False, False, None, reason="untrusted_fork")
        if (
            not isinstance(base_full_name, str)
            or base_full_name.casefold() != repository.casefold()
        ):
            return WebhookResult(False, False, None, reason="pull_request_base_mismatch")
        if self.preview_owner_id is None:
            return WebhookResult(False, False, None, reason="preview_owner_not_configured")
        head_sha, branch = head.get("sha"), head.get("ref")
        if (
            not isinstance(head_sha, str)
            or not re.fullmatch(r"[a-f0-9]{40}", head_sha)
            or not isinstance(branch, str)
            or len(branch) > 255
            or ".." in branch
        ):
            return WebhookResult(False, False, None, reason="untrusted_head_reference")
        image_digest = pull_request.get("platform_image_digest")
        if image_digest is not None and (
            not isinstance(image_digest, str)
            or not _DIGEST.fullmatch(image_digest)
            or not self.images.is_approved(image_digest, "local")
        ):
            return WebhookResult(False, False, None, reason="preview_image_not_approved")
        application_id = await self.repository.request_preview(
            project_id=registered.project_id,
            owner_id=self.preview_owner_id,
            repository=repository.casefold(),
            pull_request=number,
            branch=branch,
            head_sha=head_sha,
            image_digest=image_digest,
            template_id="python-fastapi",
            template_version="1.0.0",
            ttl_seconds=self.preview_ttl_seconds,
            now=self.clock(),
        )
        return WebhookResult(True, False, application_id)
