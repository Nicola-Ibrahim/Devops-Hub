"""Application workflows for a durable request ledger, without provisioning effects."""

import re
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import (
    CatalogForbidden,
    PlatformRequestError,
    resource_not_found,
)
from developer_platform.application.ledger import (
    AcceptedDatabaseRequest,
    OperationDetails,
    PlatformLedgerRepository,
    PostgresOption,
    ProjectRegistrationDetails,
    RegisterProjectCommand,
    RequestDatabaseCommand,
    ResourceDetails,
)
from developer_platform.domain.leases import LeasePolicy


def require_project_scope(access: AccessContext, project_id: UUID, scope: str) -> None:
    if access.project_id != project_id:
        raise resource_not_found()
    if scope not in access.scopes:
        raise CatalogForbidden()


def validate_registration(command: RegisterProjectCommand) -> None:
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", command.name)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", command.owning_team)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", command.repository)
        or len(command.repository) > 200
        or not 1 <= len(command.environments) <= 20
        or len(set(command.environments)) != len(command.environments)
        or any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) for name in command.environments)
    ):
        raise PlatformRequestError("invalid_registration", "Invalid project registration", 422)


class ApprovedPostgresCatalog:
    def __init__(self, options: tuple[PostgresOption, ...] = (PostgresOption(),)) -> None:
        self.options = options

    def require_option(self, command: RequestDatabaseCommand) -> PostgresOption:
        for option in self.options:
            if (option.template_id, option.version, option.target_id, option.size.id) == (
                command.template_id,
                command.version,
                command.target_id,
                command.size_id,
            ):
                if not option.requestable:
                    raise PlatformRequestError(
                        "provider_unavailable", "Provisioning is not enabled for this option", 503
                    )
                return option
        raise PlatformRequestError("unsupported_option", "Unsupported catalog option", 422)


class RegisterProject:
    def __init__(self, repository: PlatformLedgerRepository) -> None:
        self.repository = repository

    async def execute(
        self, command: RegisterProjectCommand, project_id: UUID, team_id: UUID
    ) -> ProjectRegistrationDetails:
        validate_registration(command)
        return await self.repository.register_project(command, project_id, team_id)


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


class ReadPlatformLedger:
    def __init__(self, repository: PlatformLedgerRepository) -> None:
        self.repository = repository

    async def project(self, access: AccessContext, project_id: UUID) -> ProjectRegistrationDetails:
        require_project_scope(access, project_id, "resources:read")
        project = await self.repository.find_project(project_id)
        if project is None:
            raise resource_not_found()
        return project

    async def resources(
        self, access: AccessContext, project_id: UUID, after: UUID | None, limit: int
    ) -> tuple[ResourceDetails, ...]:
        require_project_scope(access, project_id, "resources:read")
        if not 1 <= limit <= 100:
            raise PlatformRequestError("invalid_page", "Page limit must be between 1 and 100", 422)
        return await self.repository.list_resources(project_id, after, limit)

    async def resource(self, access: AccessContext, resource_id: UUID) -> ResourceDetails:
        require_project_scope(access, access.project_id, "resources:read")
        resource = await self.repository.find_resource(access.project_id, resource_id)
        if resource is None:
            raise resource_not_found()
        return resource

    async def operation(self, access: AccessContext, operation_id: UUID) -> OperationDetails:
        require_project_scope(access, access.project_id, "resources:read")
        operation = await self.repository.find_operation(access.project_id, operation_id)
        if operation is None:
            raise resource_not_found()
        return operation
