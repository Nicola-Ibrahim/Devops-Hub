"""HTTP composition across identity and developer platform capabilities."""

from dishka import AsyncContainer, Provider, Scope, provide
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.health.metrics import OperationalMetrics
from api.identity.cookie_policy import BrowserCookiePolicy
from developer_platform.application.module import DeveloperPlatformModule
from developer_platform.application.projects.handler import RegisterProjectHandler
from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.workload_delivery.shared.ports import ResourceProvisioner
from identity.application.module import IdentityModule
from identity.domain.interfaces.project_access_directory import ProjectAccessDirectory
from identity.infra.composition.module import IdentityModuleDispatcher
from infra.hosts.application_resources import LedgerApplicationResources
from infra.hosts.project_registration import RegisterProjectCommandHandler
from infra.http.authentication import authenticate_request
from infra.http.metrics import DatabaseOperationalMetrics
from infra.http.platform_module import PlatformHttpModule
from infra.http.ports import PlatformRequestAuthenticator
from shared.infra.clock import Clock
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.settings import Settings


class HttpCompositionProvider(Provider):
    """Adapt context capabilities to HTTP contracts at the process boundary."""

    metrics = provide(DatabaseOperationalMetrics, provides=OperationalMetrics, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def browser_cookie_policy(self, settings: Settings) -> BrowserCookiePolicy:
        return BrowserCookiePolicy(secure=settings.cookie_secure)

    @provide(scope=Scope.REQUEST)
    def identity_module(self, container: AsyncContainer) -> IdentityModule:
        return IdentityModuleDispatcher(container)

    @provide(scope=Scope.REQUEST)
    def platform_module(
        self, container: AsyncContainer, request: Request, settings: Settings, clock: Clock
    ) -> DeveloperPlatformModule:
        return PlatformHttpModule(container, request, settings, clock)

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
    def register_project(
        self,
        directory: ProjectAccessDirectory,
        register: RegisterProjectHandler,
        unit: SqlAlchemyUnitOfWork,
    ) -> RegisterProjectCommandHandler:
        return RegisterProjectCommandHandler(directory, register, unit)
