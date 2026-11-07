"""Persistence required for preview-webhook idempotency and lifecycle."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.application.application_delivery.shared.models import RegisteredRepository


class PreviewWebhookRepository(Protocol):
    async def record_webhook(
        self,
        *,
        delivery_id: str,
        payload_hash: str,
        event: str,
        repository: str,
        pull_request: int | None,
        action: str,
        now: datetime,
    ) -> bool: ...
    async def find_registered_repository(self, repository: str) -> RegisteredRepository | None: ...
    async def request_preview(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        repository: str,
        pull_request: int,
        branch: str,
        head_sha: str,
        image_digest: str | None,
        template_id: str,
        template_version: str,
        ttl_seconds: int,
        now: datetime,
    ) -> UUID | None: ...
    async def close_preview(self, *, repository: str, pull_request: int, now: datetime) -> int: ...
    async def expire_previews(self, now: datetime, limit: int) -> int: ...
