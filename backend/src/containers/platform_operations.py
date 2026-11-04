"""Private authentication and completion around repository-backed platform use cases."""

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Literal, TypeVar, cast
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select

from api.credentials import BrowserRequestCredentials, RequestIdentity
from api.platform.schemas import (
    AcceptedOperation,
    ActivityPage,
    ActivityView,
    ConnectionView,
    OperationView,
    ProjectRegistrationView,
    RenewRequest,
    ResourcePage,
    ResourceRequest,
    ResourceView,
)
from containers.authentication import authenticate_request
from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError, ledger_unavailable
from developer_platform.application.ledger import (
    ProjectRegistrationDetails,
    RegisterProjectCommand,
    RequestDatabaseCommand,
    ResourceDetails,
)
from developer_platform.application.requests import (
    ReadPlatformLedger,
    RegisterProject,
    RequestTestDatabase,
    require_project_scope,
    validate_registration,
)
from developer_platform.infra.credentials import FernetResourceCredentialCipher
from developer_platform.infra.persistence.ledger import SQLAlchemyPlatformLedgerRepository
from developer_platform.infra.persistence.lifecycle import SQLAlchemyResourceLifecycle
from developer_platform.infra.persistence.models import ResourceActivityRow
from entrypoints.settings import Settings
from identity.application.authenticate import AuthenticateApiToken
from identity.application.project_directory import ProjectAccessDirectory
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork

T = TypeVar("T")
R = TypeVar("R")


class PlatformHttpOperations:
    def __init__(
        self,
        authenticate: AuthenticateApiToken,
        request: RequestTestDatabase,
        read: ReadPlatformLedger,
        unit: SqlAlchemyUnitOfWork,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings
        self.authenticate = authenticate
        self.request = request
        self.read = read
        self.unit = unit

    async def _run(
        self,
        token: RequestIdentity,
        action: Callable[[AccessContext], Awaitable[T]],
        present: Callable[[T], R],
    ) -> R:
        async def authorized() -> T:
            # Revalidate private bearer and lock identity rows in THIS transaction.
            if isinstance(token, BrowserRequestCredentials):
                assert self.settings is not None
                access = await authenticate_request(
                    self.unit.session, token, self.settings, lambda: datetime.now(UTC)
                )
            else:
                principal = await self.authenticate.execute(token)
                access = AccessContext(
                    principal.user_id, principal.project_id, principal.role, principal.scopes
                )
            return await action(access)

        try:
            return await self.unit.run(authorized, present)
        except DatabaseUnavailable as error:
            raise ledger_unavailable() from error

    async def request_database(
        self, token: RequestIdentity, command: ResourceRequest, key: str
    ) -> AcceptedOperation:
        request = RequestDatabaseCommand(**command.model_dump())
        return await self._run(
            token,
            lambda access: self.request.execute(access, request, key),
            lambda result: AcceptedOperation(**asdict(result)),
        )

    async def projects(self, token: RequestIdentity) -> list[ProjectRegistrationView]:
        if isinstance(token, BrowserRequestCredentials):

            async def all_projects() -> list[ProjectRegistrationDetails]:
                from containers.browser_operations import authenticate_browser_operation
                from developer_platform.application.permissions import ALL_SCOPES

                assert self.settings is not None
                principal = await authenticate_browser_operation(
                    self.unit.session,
                    token.session_token,
                    None,
                    lambda: datetime.now(UTC),
                    token_pepper=self.settings.token_pepper.get_secret_value(),
                )
                rows = []
                for member in principal.memberships:
                    access = AccessContext(
                        principal.user_id,
                        member.project_id,
                        cast(Literal["developer", "admin"], member.role),
                        frozenset(ALL_SCOPES),
                    )
                    rows.append(await self.read.project(access, member.project_id))
                return rows

            return await self.unit.run(
                all_projects,
                lambda rows: [ProjectRegistrationView.model_validate(asdict(row)) for row in rows],
            )
        return await self._run(
            token,
            lambda access: self.read.project(access, access.project_id),
            lambda result: [ProjectRegistrationView.model_validate(asdict(result))],
        )

    async def project(self, token: RequestIdentity, project_id: UUID) -> ProjectRegistrationView:
        return await self._run(
            token,
            lambda access: self.read.project(access, project_id),
            lambda result: ProjectRegistrationView.model_validate(asdict(result)),
        )

    async def resources(
        self, token: RequestIdentity, project_id: UUID, after: UUID | None, limit: int
    ) -> ResourcePage:
        return await self._run(
            token,
            lambda access: self.read.resources(access, project_id, after, limit),
            lambda results: ResourcePage(
                items=[ResourceView.model_validate(asdict(item)) for item in results],
                next_after=results[-1].id if len(results) == limit else None,
            ),
        )

    async def resource(self, token: RequestIdentity, resource_id: UUID) -> ResourceView:
        return await self._run(
            token,
            lambda access: self.read.resource(access, resource_id),
            lambda result: ResourceView.model_validate(asdict(result)),
        )

    async def operation(self, token: RequestIdentity, operation_id: UUID) -> OperationView:
        return await self._run(
            token,
            lambda access: self.read.operation(access, operation_id),
            lambda result: OperationView.model_validate(asdict(result)),
        )

    async def renew(
        self, token: RequestIdentity, resource_id: UUID, command: RenewRequest
    ) -> ResourceView:
        async def action(access: AccessContext) -> ResourceDetails:
            row = await SQLAlchemyResourceLifecycle(self.unit.session).renew(
                access, resource_id, command.expected_revision, command.expires_at
            )
            return SQLAlchemyPlatformLedgerRepository._resource_details(row)

        return await self._run(token, action, lambda row: ResourceView.model_validate(asdict(row)))

    async def delete(self, token: RequestIdentity, resource_id: UUID) -> AcceptedOperation:
        async def action(access: AccessContext) -> AcceptedOperation:
            operation = await SQLAlchemyResourceLifecycle(self.unit.session).delete(
                access, resource_id
            )
            return AcceptedOperation(resource_id=resource_id, operation_id=operation.id)

        return await self._run(token, action, lambda row: row)

    async def connection(self, token: RequestIdentity, resource_id: UUID) -> ConnectionView:
        async def action(access: AccessContext) -> ConnectionView:
            if self.settings is None or self.settings.resource_key is None:
                raise PlatformRequestError(
                    "credentials_unavailable", "Resource access is unavailable", 503
                )
            row, secret = await SQLAlchemyResourceLifecycle(self.unit.session).connection(
                access, resource_id
            )
            credentials = FernetResourceCredentialCipher(
                self.settings.resource_key.get_secret_value(), self.settings.resource_key_id
            ).decrypt(row.id, secret.ciphertext, secret.key_id)
            assert row.endpoint is not None
            host = str(row.endpoint["host"])
            port = int(row.endpoint["port"])
            hostpart = "[" + host + "]" if ":" in host else host
            dsn = (
                f"postgresql://{quote(credentials.user, safe='')}:"
                f"{quote(credentials.password, safe='')}@{hostpart}:{port}/"
                f"{quote(credentials.database, safe='')}"
            )
            return ConnectionView(
                connection_string=dsn,
                host=host,
                port=port,
                database=credentials.database,
                user=credentials.user,
                instructions=(
                    "Connect from the configured developer host or approved tunnel. "
                    "This temporary database and its stored data are removed "
                    "on deletion or lease expiry."
                ),
            )

        return await self._run(token, action, lambda row: row)

    async def activity(self, token: RequestIdentity, project_id: UUID) -> ActivityPage:
        async def action(access: AccessContext) -> list[ActivityView]:
            require_project_scope(access, project_id, "resources:read")
            rows = await self.unit.session.scalars(
                select(ResourceActivityRow)
                .where(ResourceActivityRow.project_id == project_id)
                .order_by(ResourceActivityRow.created_at.desc())
                .limit(100)
            )
            return [
                ActivityView(
                    id=row.id,
                    actor_id=row.actor_id,
                    resource_id=row.resource_id,
                    operation_id=row.operation_id,
                    action=row.action,
                    created_at=row.created_at,
                )
                for row in rows
            ]

        return await self._run(token, action, lambda rows: ActivityPage(items=rows))


class RegisterProjectCommandHandler:
    def __init__(
        self,
        directory: ProjectAccessDirectory,
        register: RegisterProject,
        unit: SqlAlchemyUnitOfWork,
    ) -> None:
        self.directory = directory
        self.register = register
        self.unit = unit

    async def execute(self, command: RegisterProjectCommand) -> ProjectRegistrationDetails:
        validate_registration(command)

        async def register() -> ProjectRegistrationDetails:
            refs = await self.directory.register_references(command.name, command.owning_team)
            return await self.register.execute(command, refs.project_id, refs.team_id)

        try:
            return await self.unit.run(register, lambda result: result)
        except DatabaseUnavailable as error:
            raise ledger_unavailable() from error
