"""Declarative bindings; this is the only layer selecting concrete implementations."""

import hashlib
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from api.dependencies import ReadCurrentIdentity, ReadinessProbe
from api.health.metrics import OperationalMetrics
from api.identity.browser import BrowserIdentityOperations
from api.platform.applications import ApplicationDeliveryOperations
from api.platform.capabilities import PlatformRequestQueries
from containers.application_bindings import SQLAlchemyApplicationDatabaseBindings
from containers.application_operations import ApplicationDeliveryService
from containers.application_resources import LedgerApplicationResources
from containers.authentication import authenticate_request
from containers.browser_operations import BrowserIdentityService
from containers.metrics_operations import DatabaseOperationalMetrics
from containers.operations import (
    CurrentIdentityQuery,
    IssueApiTokenToFile,
    RevokeApiTokenCommand,
)
from containers.platform_operations import PlatformHttpOperations, RegisterProjectCommandHandler
from containers.worker_queue import PostgresResourceEffectGuard
from developer_platform.application.catalog import ReadCatalog
from developer_platform.application.delivery import ApplicationDeliveryRepository
from developer_platform.application.ledger import PlatformLedgerRepository, RequestDatabaseCommand
from developer_platform.application.permissions import ALL_SCOPES
from developer_platform.application.requests import (
    ApprovedPostgresCatalog,
    ReadPlatformLedger,
    RegisterProject,
    RequestTestDatabase,
)
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
from developer_platform.infra.persistence.delivery import SQLAlchemyApplicationDeliveryRepository
from developer_platform.infra.persistence.ledger import SQLAlchemyPlatformLedgerRepository
from entrypoints.settings import SCHEMA_REVISION, Settings
from identity.application.authenticate import AuthenticateApiToken
from identity.application.issue_token import IssueApiToken
from identity.application.ports import ApiTokenRepository, TokenGenerator, TokenHasher
from identity.application.project_directory import ProjectAccessDirectory
from identity.application.revoke_token import RevokeApiToken
from identity.infra.persistence.project_directory import SQLAlchemyProjectAccessDirectory
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from identity.infra.tokens import PepperedTokenHasher, SecureTokenGenerator
from shared.infra.persistence.database import create_async_database_engine
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.readiness import SqlAlchemyReadinessProbe

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class ExternalDatabase:
    engine: AsyncEngine | None = None


class DatabaseProvider(Provider):
    metrics = provide(DatabaseOperationalMetrics, provides=OperationalMetrics, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def engine(
        self, settings: Settings, external: ExternalDatabase
    ) -> AsyncIterator[AsyncEngine]:
        engine = external.engine or create_async_database_engine(
            settings.database_url.get_secret_value(), settings.database_connect_timeout
        )
        try:
            yield engine
        finally:
            if external.engine is None:
                await engine.dispose()

    @provide(scope=Scope.APP)
    def sessions(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    def session(self, sessions: async_sessionmaker[AsyncSession]) -> AsyncSession:
        # The outer UoW closes this session before returning, not after HTTP emission.
        return sessions()

    unit = provide(SqlAlchemyUnitOfWork, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def readiness(self, engine: AsyncEngine) -> ReadinessProbe:
        return SqlAlchemyReadinessProbe(engine, SCHEMA_REVISION)


class IdentityProvider(Provider):
    @provide(scope=Scope.APP)
    def browser(
        self, sessions: async_sessionmaker[AsyncSession], clock: Clock, settings: Settings
    ) -> BrowserIdentityOperations:
        return BrowserIdentityService(
            sessions,
            clock,
            settings.cookie_secure,
            settings.browser_allowed_origins,
            settings.token_pepper.get_secret_value(),
        )

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        return lambda: datetime.now(UTC)

    @provide(scope=Scope.APP)
    def hasher(self, settings: Settings) -> TokenHasher:
        return PepperedTokenHasher(settings.token_pepper.get_secret_value())

    @provide(scope=Scope.APP)
    def generator(self) -> TokenGenerator:
        return SecureTokenGenerator()

    project_directory = provide(
        SQLAlchemyProjectAccessDirectory, provides=ProjectAccessDirectory, scope=Scope.REQUEST
    )

    repository = provide(
        SQLAlchemyApiTokenRepository, provides=ApiTokenRepository, scope=Scope.REQUEST
    )
    authenticate = provide(AuthenticateApiToken, scope=Scope.REQUEST)
    revoke = provide(RevokeApiToken, scope=Scope.REQUEST)
    revoke_command = provide(RevokeApiTokenCommand, scope=Scope.REQUEST)
    issue_command = provide(IssueApiTokenToFile, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def issue(
        self,
        repository: ApiTokenRepository,
        hasher: TokenHasher,
        generator: TokenGenerator,
        clock: Clock,
    ) -> IssueApiToken:
        return IssueApiToken(repository, hasher, generator, clock, ALL_SCOPES, ALL_SCOPES)

    @provide(scope=Scope.REQUEST)
    def current_identity(
        self, inner: AuthenticateApiToken, unit: SqlAlchemyUnitOfWork, settings: Settings
    ) -> ReadCurrentIdentity:
        return CurrentIdentityQuery(inner, unit, settings)


class PlatformProvider(Provider):
    repository = provide(
        SQLAlchemyPlatformLedgerRepository, provides=PlatformLedgerRepository, scope=Scope.REQUEST
    )
    read = provide(ReadPlatformLedger, scope=Scope.REQUEST)
    register = provide(RegisterProject, scope=Scope.REQUEST)
    register_command = provide(RegisterProjectCommandHandler, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def queries(
        self,
        authenticate: AuthenticateApiToken,
        request: RequestTestDatabase,
        read: ReadPlatformLedger,
        unit: SqlAlchemyUnitOfWork,
        settings: Settings,
    ) -> PlatformRequestQueries:
        return PlatformHttpOperations(authenticate, request, read, unit, settings)

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
        catalog: ApprovedPostgresCatalog,
        deployer: DockerApplicationAdapter | None,
        settings: Settings,
    ) -> ApplicationDeliveryService:
        return ApplicationDeliveryService(
            sessions=sessions,
            clock=clock,
            authenticate=lambda session, identity: authenticate_request(
                session, identity, settings, clock
            ),
            templates=templates,
            images=images,
            repositories=repository_provisioner,
            resources=LedgerApplicationResources(sessions, catalog, settings.installation_id),
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
        self, service: ApplicationDeliveryService
    ) -> ApplicationDeliveryOperations:
        return service
