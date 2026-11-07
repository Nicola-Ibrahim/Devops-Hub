"""Atomic persistence contract for accepting idempotent resource intent."""

from typing import Protocol

from developer_platform.domain.access import AccessContext
from developer_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from developer_platform.domain.entities.operation import AcceptedResourceRequest
from developer_platform.domain.value_objects.idempotency_key import IdempotencyKey


class ResourceRequestRepository(Protocol):
    async def replay_request(
        self, access: AccessContext, key: IdempotencyKey, request_hash: str
    ) -> AcceptedResourceRequest | None: ...

    async def accept_database_request(
        self,
        access: AccessContext,
        lifecycle: ResourceLifecycle,
        key: IdempotencyKey,
        request_hash: str,
    ) -> AcceptedResourceRequest: ...
