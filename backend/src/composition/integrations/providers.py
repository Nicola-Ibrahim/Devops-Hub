"""Dependency bindings for cross-context application bridges."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from composition.integrations.application_resources import LedgerApplicationResources
from composition.integrations.project_registration import RegisterProjectCommandHandler
from developer_platform.application.projects.handler import RegisterProjectHandler
from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.workload_delivery.shared.ports import ResourceProvisioner
from identity.domain.interfaces.project_access_directory import ProjectAccessDirectory
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.settings import Settings


class CrossContextIntegrationProvider(Provider):
    """Bind adapters that coordinate identity and developer-platform capabilities."""

    @provide(scope=Scope.APP)
    def application_resources(
        self,
        sessions: async_sessionmaker[AsyncSession],
        catalog: ApprovedPostgresCatalog,
        settings: Settings,
    ) -> ResourceProvisioner:
        return LedgerApplicationResources(sessions, catalog, settings.installation_id)

    @provide(scope=Scope.REQUEST)
    def register_project(
        self,
        directory: ProjectAccessDirectory,
        register: RegisterProjectHandler,
        unit: SqlAlchemyUnitOfWork,
    ) -> RegisterProjectCommandHandler:
        return RegisterProjectCommandHandler(directory, register, unit)
