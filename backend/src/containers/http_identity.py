"""HTTP response adaptation and transaction completion for identity queries."""

from datetime import UTC, datetime

from api.credentials import BrowserRequestCredentials, RequestIdentity
from api.dependencies import ReadCurrentIdentity
from api.identity.schemas import PrincipalView
from containers.authentication import authenticate_request
from developer_platform.application.shared.dto import AccessContext
from identity.application.authenticate_api_token.handler import AuthenticateApiTokenHandler
from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.shared.errors import IdentityUnavailable
from identity.contracts import AuthenticatedPrincipal
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork
from shared.infra.settings import Settings


class CurrentIdentityQuery(ReadCurrentIdentity):
    """Materialize the HTTP identity result before completing its database operation."""

    def __init__(
        self,
        inner: AuthenticateApiTokenHandler,
        unit: SqlAlchemyUnitOfWork,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings
        self.inner = inner
        self.unit = unit

    async def execute(self, token: RequestIdentity) -> PrincipalView:
        def present(principal: AuthenticatedPrincipal | AccessContext) -> PrincipalView:
            return PrincipalView(
                user_id=principal.user_id,
                project_id=principal.project_id,
                role=principal.role,
                scopes=sorted(principal.scopes),
            )

        async def authenticate() -> AuthenticatedPrincipal | AccessContext:
            if isinstance(token, BrowserRequestCredentials):
                assert self.settings is not None
                return await authenticate_request(
                    self.unit.session, token, self.settings, lambda: datetime.now(UTC)
                )
            return await self.inner.execute(AuthenticateApiTokenQuery(token))

        try:
            return await self.unit.run(authenticate, present)
        except DatabaseUnavailable as error:
            raise IdentityUnavailable() from error
