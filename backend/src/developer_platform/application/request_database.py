"""Accept an idempotent temporary database request."""

import re
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.application.postgres_catalog import ApprovedPostgresCatalog
from developer_platform.application.project_access import require_project_scope
from developer_platform.domain.leases import LeasePolicy
from developer_platform.domain.ledger import (
    AcceptedDatabaseRequest,
    PlatformLedgerRepository,
    RequestDatabaseCommand,
)


class RequestTestDatabase:
    def __init__(
        self,
        repository: PlatformLedgerRepository,
        catalog: ApprovedPostgresCatalog,
        clock: Callable[[], datetime],
        fingerprint: Callable[[RequestDatabaseCommand], str],
        installation_id: UUID | None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.clock = clock
        self.fingerprint = fingerprint
        self.installation_id = installation_id

    async def execute(
        self, access: AccessContext, command: RequestDatabaseCommand, key: str
    ) -> AcceptedDatabaseRequest:
        require_project_scope(access, command.project_id, "resources:write")
        if (
            not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key)
            or not command.display_name.strip()
            or len(command.display_name) > 100
        ):
            raise PlatformRequestError("invalid_request", "Invalid request or idempotency key", 422)
        request_hash = self.fingerprint(command)
        replay = await self.repository.replay_request(access, key, request_hash)
        if replay is not None:
            return replay
        option = self.catalog.require_option(command)
        if self.installation_id is None:
            raise PlatformRequestError(
                "installation_not_configured", "Platform installation is not configured", 503
            )
        now = self.clock()
        expiry = LeasePolicy(max_lifetime_seconds=option.max_lifetime_seconds).initial_expiry(
            now, command.ttl_seconds
        )
        return await self.repository.accept_database_request(
            access,
            command,
            option,
            key,
            request_hash,
            now,
            expiry,
            self.installation_id,
        )
