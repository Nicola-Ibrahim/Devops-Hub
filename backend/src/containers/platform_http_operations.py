"""Private authentication and completion around repository-backed platform use cases."""

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Literal, TypeVar, cast
from uuid import UUID

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
from developer_platform.application.errors import ledger_unavailable
from developer_platform.application.ledger import (
    ProjectRegistrationDetails,
    RequestDatabaseCommand,
)
from developer_platform.application.manage_databases import ManageDatabases, RenewDatabaseLease
from developer_platform.application.requests import (
    ReadPlatformLedger,
    RequestTestDatabase,
)
from identity.application.authenticate import AuthenticateApiToken
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork
from shared.infra.settings import Settings

T = TypeVar("T")
R = TypeVar("R")


class PlatformHttpOperations:
    def __init__(
        self,
        authenticate: AuthenticateApiToken,
        request: RequestTestDatabase,
        read: ReadPlatformLedger,
        databases: ManageDatabases,
        unit: SqlAlchemyUnitOfWork,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings
        self.authenticate = authenticate
        self.request = request
        self.read = read
        self.databases = databases
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
                from developer_platform.application.permissions import ALL_SCOPES
                from identity.containers.browser_operations import authenticate_browser_operation

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
        return await self._run(
            token,
            lambda access: self.databases.renew(
                access,
                RenewDatabaseLease(resource_id, command.expected_revision, command.expires_at),
            ),
            lambda row: ResourceView.model_validate(asdict(row)),
        )

    async def delete(self, token: RequestIdentity, resource_id: UUID) -> AcceptedOperation:
        return await self._run(
            token,
            lambda access: self.databases.delete(access, resource_id),
            lambda operation_id: AcceptedOperation(
                resource_id=resource_id, operation_id=operation_id
            ),
        )

    async def connection(self, token: RequestIdentity, resource_id: UUID) -> ConnectionView:
        return await self._run(
            token,
            lambda access: self.databases.connection(access, resource_id),
            lambda result: ConnectionView.model_validate(asdict(result)),
        )

    async def activity(self, token: RequestIdentity, project_id: UUID) -> ActivityPage:
        return await self._run(
            token,
            lambda access: self.databases.activity(access, project_id),
            lambda rows: ActivityPage(
                items=[ActivityView.model_validate(asdict(row)) for row in rows]
            ),
        )
