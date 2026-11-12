"""Accept an idempotent temporary database request."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from developer_platform.application.database_provisioning.submit_database_request.command import (
    DatabaseRequest,
    RequestTemporaryDatabase,
)
from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.shared.errors import PlatformRequestError
from developer_platform.application.shared.resource_repository import ResourceRepository
from developer_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from developer_platform.domain.entities.operation import AcceptedResourceRequest
from developer_platform.domain.errors import DomainError
from developer_platform.domain.value_objects.idempotency_key import IdempotencyKey
from developer_platform.domain.value_objects.resource_name import ResourceName
from developer_platform.domain.value_objects.resource_spec import ResourceSpec


class RequestTemporaryDatabaseHandler:
    def __init__(
        self,
        repository: ResourceRepository,
        catalog: ApprovedPostgresCatalog,
        clock: Callable[[], datetime],
        fingerprint: Callable[[DatabaseRequest], str],
        installation_id: UUID | None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.clock = clock
        self.fingerprint = fingerprint
        self.installation_id = installation_id

    async def execute(self, message: RequestTemporaryDatabase) -> AcceptedResourceRequest:
        access, command, key = message.access, message.request, message.idempotency_key
        try:
            idempotency_key = IdempotencyKey(key)
            name = ResourceName(command.display_name)
        except DomainError as error:
            raise PlatformRequestError(
                "invalid_request", "Invalid request or idempotency key", 422
            ) from error
        request_hash = self.fingerprint(command)
        replay = await self.repository.replay_request(access, idempotency_key, request_hash)
        if replay is not None:
            return replay
        option = self.catalog.require_option(command)
        if self.installation_id is None:
            raise PlatformRequestError(
                "installation_not_configured", "Platform installation is not configured", 503
            )
        now = self.clock()
        lifecycle = ResourceLifecycle.request(
            resource_id=uuid4(),
            project_id=command.project_id,
            environment_id=command.environment_id,
            owner_id=access.user_id,
            installation_id=self.installation_id,
            name=name,
            specification=ResourceSpec(
                command.template_id,
                command.version,
                command.target_id,
                command.size_id,
                option.size.cpu_millis,
                option.size.memory_bytes,
                option.size.storage_bytes,
                option.max_lifetime_seconds,
                option.size.storage_enforcement,
            ),
            now=now,
            ttl_seconds=command.ttl_seconds,
            max_lifetime_seconds=option.max_lifetime_seconds,
        )
        return await self.repository.accept_database_request(
            access,
            lifecycle,
            idempotency_key,
            request_hash,
        )
