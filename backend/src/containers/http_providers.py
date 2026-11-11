"""HTTP composition across identity and developer platform capabilities."""

from dishka import AsyncContainer, Provider, Scope, provide
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from containers.application_resources import LedgerApplicationResources
from containers.authentication import authenticate_request
from containers.platform_module import PlatformHttpModule
from containers.project_registration import RegisterProjectCommandHandler
from developer_platform.application.module import DeveloperPlatformModule
from developer_platform.application.projects.handler import RegisterProjectHandler
from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryService,
    ResourceProvisioner,
)
from developer_platform.containers.application_host import ApplicationDeliveryHost
from developer_platform.containers.ports import PlatformRequestAuthenticator
from developer_platform.infra.persistence.delivery import SQLAlchemyApplicationDeliveryRepository
from identity.application.module import IdentityModule
from identity.containers.module import IdentityModuleDispatcher
from identity.domain.project_access import ProjectAccessDirectory
from shared.infra.clock import Clock
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.settings import Settings


class HttpCompositionProvider(Provider):
    """Adapt context capabilities to HTTP contracts at the process boundary."""

    @provide(scope=Scope.REQUEST)
    def identity_module(self, container: AsyncContainer) -> IdentityModule:
        return IdentityModuleDispatcher(container)

    @provide(scope=Scope.REQUEST)
    def platform_module(
        self, container: AsyncContainer, request: Request, settings: Settings, clock: Clock
    ) -> DeveloperPlatformModule:
        return PlatformHttpModule(container, request, settings, clock)

    @provide(scope=Scope.REQUEST)
    def delivery_service(
        self, host: ApplicationDeliveryHost, session: AsyncSession
    ) -> ApplicationDeliveryService:
        return host._use_case(SQLAlchemyApplicationDeliveryRepository(session))

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
