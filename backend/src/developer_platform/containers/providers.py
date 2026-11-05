"""Declarative bindings; this is the only layer selecting concrete implementations."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from api.health.metrics import OperationalMetrics
from api.platform.applications import ApplicationDeliveryOperations
from developer_platform.application.catalog import ReadCatalog
from developer_platform.application.delivery import (
    ApplicationDeliveryRepository,
    ResourceProvisioner,
)
from developer_platform.application.ledger import PlatformLedgerRepository, RequestDatabaseCommand
from developer_platform.application.lifecycle import ResourceCredentialCipher
from developer_platform.application.manage_databases import ManageDatabases
from developer_platform.application.requests import (
    ApprovedPostgresCatalog,
    ReadPlatformLedger,
    RegisterProject,
    RequestTestDatabase,
)
from developer_platform.containers.application_host import ApplicationDeliveryHost
from developer_platform.containers.metrics_operations import DatabaseOperationalMetrics
from developer_platform.containers.ports import PlatformRequestAuthenticator
from developer_platform.domain.resource_lifecycle_repository import ResourceLifecycleRepository
from developer_platform.infra.application_runtime import (
    ApplicationDatabaseBindingResolver,
    DockerApplicationRuntime,
)
from developer_platform.infra.credentials import FernetResourceCredentialCipher
from developer_platform.infra.delivery_adapters import (
    DockerApplicationAdapter,
    FilesystemTemplateCatalog,
    GitHubRepositoryAdapter,
    HmacGitHubWebhookVerifier,
    Sha256RequestFingerprint,
    StaticApprovedImageCatalog,
)
from developer_platform.infra.persistence.application_bindings import (
    SQLAlchemyApplicationDatabaseBindings,
)
from developer_platform.infra.persistence.delivery import SQLAlchemyApplicationDeliveryRepository
from developer_platform.infra.persistence.ledger import SQLAlchemyPlatformLedgerRepository
from developer_platform.infra.persistence.lifecycle import SQLAlchemyResourceLifecycleRepository
from developer_platform.infra.persistence.worker_queue import PostgresResourceEffectGuard
from shared.infra.clock import Clock
from shared.infra.settings import Settings


class PlatformProvider(Provider):
    repository = provide(
        SQLAlchemyPlatformLedgerRepository, provides=PlatformLedgerRepository, scope=Scope.REQUEST
    )
    read = provide(ReadPlatformLedger, scope=Scope.REQUEST)
    register = provide(RegisterProject, scope=Scope.REQUEST)
    lifecycle_repository = provide(
        SQLAlchemyResourceLifecycleRepository,
        provides=ResourceLifecycleRepository,
        scope=Scope.REQUEST,
    )
    manage_databases = provide(ManageDatabases, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def credential_cipher(self, settings: Settings) -> ResourceCredentialCipher | None:
        if settings.resource_key is None:
            return None
        return FernetResourceCredentialCipher(
            settings.resource_key.get_secret_value(), settings.resource_key_id
        )

    @provide(scope=Scope.APP)
    def approved_catalog(self, settings: Settings) -> ApprovedPostgresCatalog:
        # Register the planned option without claiming an implemented provider.
        from developer_platform.application.ledger import PostgresOption

        enabled = (
            settings.local_provider_enabled
            and settings.resource_key is not None
            and settings.installation_id is not None
        )
        return ApprovedPostgresCatalog(
            (
                PostgresOption(
                    requestable=enabled,
                    unavailable_reason=None if enabled else "provider_not_enabled",
                ),
            )
        )

    @provide(scope=Scope.REQUEST)
    def catalog(self, catalog: ApprovedPostgresCatalog) -> ReadCatalog:
        return ReadCatalog(catalog)

    @provide(scope=Scope.REQUEST)
    def request(
        self,
        repository: PlatformLedgerRepository,
        catalog: ApprovedPostgresCatalog,
        clock: Clock,
        settings: Settings,
    ) -> RequestTestDatabase:
        def fingerprint(command: RequestDatabaseCommand) -> str:
            payload = json.dumps(
                asdict(command), sort_keys=True, separators=(",", ":"), default=str
            )
            return hashlib.sha256(payload.encode()).hexdigest()

        return RequestTestDatabase(
            repository, catalog, clock, fingerprint, settings.installation_id
        )


class ApplicationDeliveryProvider(Provider):
    metrics = provide(DatabaseOperationalMetrics, provides=OperationalMetrics, scope=Scope.APP)

    repository = provide(
        SQLAlchemyApplicationDeliveryRepository,
        provides=ApplicationDeliveryRepository,
        scope=Scope.REQUEST,
    )

    @provide(scope=Scope.APP)
    def templates(self, settings: Settings) -> FilesystemTemplateCatalog:
        return FilesystemTemplateCatalog(
            Path(settings.template_root), settings.template_workflow_repository
        )

    @provide(scope=Scope.APP)
    def images(self, settings: Settings) -> StaticApprovedImageCatalog:
        return StaticApprovedImageCatalog({"local": frozenset(settings.approved_local_images)})

    @provide(scope=Scope.APP)
    def repository_provisioner(self, settings: Settings) -> GitHubRepositoryAdapter | None:
        if settings.github_organization is None or settings.github_token is None:
            return None
        return GitHubRepositoryAdapter(
            settings.github_organization,
            settings.github_token.get_secret_value(),
            settings.github_api_url,
        )

    @provide(scope=Scope.APP)
    def application_runtime(self, settings: Settings) -> DockerApplicationRuntime:
        return DockerApplicationRuntime(settings.docker_url, settings.postgres_image)

    @provide(scope=Scope.APP)
    def database_bindings(
        self, settings: Settings, sessions: async_sessionmaker[AsyncSession]
    ) -> ApplicationDatabaseBindingResolver | None:
        if settings.installation_id is None or settings.resource_key is None:
            return None
        cipher = FernetResourceCredentialCipher(
            settings.resource_key.get_secret_value(), settings.resource_key_id
        )
        return SQLAlchemyApplicationDatabaseBindings(sessions, settings.installation_id, cipher)

    @provide(scope=Scope.APP)
    def deployer(
        self,
        settings: Settings,
        runtime: DockerApplicationRuntime,
        bindings: ApplicationDatabaseBindingResolver | None,
    ) -> DockerApplicationAdapter | None:
        if not settings.approved_local_images or settings.installation_id is None:
            return None
        return DockerApplicationAdapter(
            frozenset(settings.approved_local_images),
            runtime,
            settings.installation_id,
            bindings,
        )

    @provide(scope=Scope.REQUEST)
    def delivery_operations(
        self,
        engine: AsyncEngine,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
        templates: FilesystemTemplateCatalog,
        images: StaticApprovedImageCatalog,
        repository_provisioner: GitHubRepositoryAdapter | None,
        resources: ResourceProvisioner,
        deployer: DockerApplicationAdapter | None,
        settings: Settings,
        authenticate: PlatformRequestAuthenticator,
    ) -> ApplicationDeliveryHost:
        return ApplicationDeliveryHost(
            sessions=sessions,
            clock=clock,
            authenticate=lambda session, identity: authenticate(session, identity, settings, clock),
            templates=templates,
            images=images,
            repositories=repository_provisioner,
            resources=resources,
            deployer=deployer,
            fingerprint=Sha256RequestFingerprint(),
            webhook_verifier=(
                HmacGitHubWebhookVerifier(settings.github_webhook_secret.get_secret_value())
                if settings.github_webhook_secret is not None
                else None
            ),
            allowed_repository_owner=settings.github_allowed_repository_owner,
            preview_owner_id=settings.preview_owner_id,
            preview_ttl_seconds=settings.preview_ttl_seconds,
            effect_guard=PostgresResourceEffectGuard(engine),
        )

    @provide(scope=Scope.REQUEST)
    def application_delivery_operations(
        self, service: ApplicationDeliveryHost
    ) -> ApplicationDeliveryOperations:
        return service
