"""Bind application worker hosts at the process boundary."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from developer_platform.application.workload_delivery.shared.ports import ResourceProvisioner
from developer_platform.infra.delivery_adapters import (
    DockerApplicationAdapter,
    FilesystemTemplateCatalog,
    GitHubRepositoryAdapter,
    StaticApprovedImageCatalog,
)
from developer_platform.infra.persistence.worker_queue import PostgresResourceEffectGuard
from infra.workers.application_host import ApplicationDeliveryHost
from shared.infra.clock import Clock


class ApplicationWorkerProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def delivery_host(
        self,
        engine: AsyncEngine,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
        templates: FilesystemTemplateCatalog,
        images: StaticApprovedImageCatalog,
        repository_provisioner: GitHubRepositoryAdapter | None,
        resources: ResourceProvisioner,
        deployer: DockerApplicationAdapter | None,
    ) -> ApplicationDeliveryHost:
        return ApplicationDeliveryHost(
            sessions=sessions,
            clock=clock,
            templates=templates,
            images=images,
            repositories=repository_provisioner,
            resources=resources,
            deployer=deployer,
            effect_guard=PostgresResourceEffectGuard(engine),
        )
