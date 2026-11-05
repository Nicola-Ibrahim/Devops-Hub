"""HTTP composition across identity and developer platform capabilities."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.dependencies import ReadCurrentIdentity
from api.platform.capabilities import PlatformRequestQueries
from containers.application_resources import LedgerApplicationResources
from containers.authentication import authenticate_request
from containers.http_identity import CurrentIdentityQuery
from containers.platform_http_operations import PlatformHttpOperations
from containers.project_registration import RegisterProjectCommandHandler
from developer_platform.application.delivery import ResourceProvisioner
from developer_platform.application.manage_databases import ManageDatabases
from developer_platform.application.requests import (
    ApprovedPostgresCatalog,
    ReadPlatformLedger,
    RegisterProject,
    RequestTestDatabase,
)
from developer_platform.containers.ports import PlatformRequestAuthenticator
from identity.application.authenticate import AuthenticateApiToken
from identity.application.project_directory import ProjectAccessDirectory
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.settings import Settings


class HttpCompositionProvider(Provider):
    """Adapt context capabilities to HTTP contracts at the process boundary."""

    @provide(scope=Scope.APP)
    def application_resources(
        self,
        sessions: async_sessionmaker[AsyncSession],
        catalog: ApprovedPostgresCatalog,
        settings: Settings,
    ) -> ResourceProvisioner:
        return LedgerApplicationResources(sessions, catalog, settings.installation_id)

    @provide(scope=Scope.APP)
    def platform_authenticator(self) -> PlatformRequestAuthenticator:
        return authenticate_request

    @provide(scope=Scope.REQUEST)
    def current_identity(
        self, inner: AuthenticateApiToken, unit: SqlAlchemyUnitOfWork, settings: Settings
    ) -> ReadCurrentIdentity:
        return CurrentIdentityQuery(inner, unit, settings)

    @provide(scope=Scope.REQUEST)
    def platform_queries(
        self,
        authenticate: AuthenticateApiToken,
        request: RequestTestDatabase,
        read: ReadPlatformLedger,
        databases: ManageDatabases,
        unit: SqlAlchemyUnitOfWork,
        settings: Settings,
    ) -> PlatformRequestQueries:
        return PlatformHttpOperations(authenticate, request, read, databases, unit, settings)

    @provide(scope=Scope.REQUEST)
    def register_project(
        self,
        directory: ProjectAccessDirectory,
        register: RegisterProject,
        unit: SqlAlchemyUnitOfWork,
    ) -> RegisterProjectCommandHandler:
        return RegisterProjectCommandHandler(directory, register, unit)
