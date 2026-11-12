"""Declarative bindings; this is the only layer selecting concrete implementations."""

from pathlib import Path

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devops_hub.platform.application.workload_delivery.attach_database.handler import (
    AttachApplicationResourceHandler,
)
from devops_hub.platform.application.workload_delivery.attach_database.port import (
    ApplicationResourceAttachmentRepository,
)
from devops_hub.platform.application.workload_delivery.create_workload.handler import (
    CreateApplicationHandler,
)
from devops_hub.platform.application.workload_delivery.create_workload.port import (
    ApplicationCreationRepository,
)
from devops_hub.platform.application.workload_delivery.deploy_workload.handler import (
    DeployApplicationHandler,
)
from devops_hub.platform.application.workload_delivery.deploy_workload.port import (
    ApplicationDeploymentRepository,
)
from devops_hub.platform.application.workload_delivery.handle_preview_webhook.handler import (
    ProcessGithubPreviewWebhookHandler,
)
from devops_hub.platform.application.workload_delivery.handle_preview_webhook.port import (
    PreviewWebhookRepository,
)
from devops_hub.platform.application.workload_delivery.read_templates.handler import (
    ReadTemplatesHandler,
)
from devops_hub.platform.application.workload_delivery.read_workloads.handler import (
    ReadApplicationHandler,
    ReadApplicationsHandler,
    ReadDeploymentHistoryHandler,
)
from devops_hub.platform.application.workload_delivery.read_workloads.port import (
    ApplicationReadRepository,
)
from devops_hub.platform.application.workload_delivery.retry_delivery_step.handler import (
    RetryDeliveryStepHandler,
)
from devops_hub.platform.application.workload_delivery.retry_delivery_step.port import (
    DeliveryRetryRepository,
)
from devops_hub.platform.application.workload_delivery.shared.database_binding import (
    ApplicationDatabaseBindingResolver,
)
from devops_hub.platform.application.workload_delivery.shared.ports import (
    ApprovedImageCatalog,
    RequestFingerprint,
    TemplateCatalog,
    WebhookSignatureVerifier,
)
from devops_hub.platform.infra.persistence.application_bindings import (
    SQLAlchemyApplicationDatabaseBindings,
)
from devops_hub.platform.infra.persistence.delivery import SQLAlchemyApplicationDeliveryRepository
from devops_hub.platform.infra.providers.docker_application import DockerApplicationAdapter
from devops_hub.platform.infra.providers.github import GitHubRepositoryAdapter
from devops_hub.platform.infra.security.approval import StaticApprovedImageCatalog
from devops_hub.platform.infra.security.credentials import FernetResourceCredentialCipher
from devops_hub.platform.infra.security.fingerprint import Sha256RequestFingerprint
from devops_hub.platform.infra.security.webhooks import HmacGitHubWebhookVerifier
from devops_hub.platform.infra.templates.catalog import FilesystemTemplateCatalog
from shared.infra.clock import Clock
from shared.infra.settings import Settings


class ApplicationDeliveryProvider(Provider):
    read_templates_handler = provide(ReadTemplatesHandler, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def templates(self, settings: Settings) -> FilesystemTemplateCatalog:
        return FilesystemTemplateCatalog(
            Path(settings.template_root), settings.template_workflow_repository
        )

    @provide(scope=Scope.APP)
    def template_catalog(self, templates: FilesystemTemplateCatalog) -> TemplateCatalog:
        return templates

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
        bindings: ApplicationDatabaseBindingResolver | None,
    ) -> DockerApplicationAdapter | None:
        if not settings.approved_local_images or settings.installation_id is None:
            return None
        return DockerApplicationAdapter(
            frozenset(settings.approved_local_images),
            settings.docker_url,
            settings.postgres_image,
            settings.installation_id,
            bindings,
        )

    @provide(scope=Scope.REQUEST)
    def delivery_repository(self, session: AsyncSession) -> SQLAlchemyApplicationDeliveryRepository:
        return SQLAlchemyApplicationDeliveryRepository(session)

    @provide(scope=Scope.REQUEST)
    def application_creation_repository(
        self, repository: SQLAlchemyApplicationDeliveryRepository
    ) -> ApplicationCreationRepository:
        return repository

    @provide(scope=Scope.REQUEST)
    def application_read_repository(
        self, repository: SQLAlchemyApplicationDeliveryRepository
    ) -> ApplicationReadRepository:
        return repository

    @provide(scope=Scope.REQUEST)
    def application_attachment_repository(
        self, repository: SQLAlchemyApplicationDeliveryRepository
    ) -> ApplicationResourceAttachmentRepository:
        return repository

    @provide(scope=Scope.REQUEST)
    def application_deployment_repository(
        self, repository: SQLAlchemyApplicationDeliveryRepository
    ) -> ApplicationDeploymentRepository:
        return repository

    @provide(scope=Scope.REQUEST)
    def delivery_retry_repository(
        self, repository: SQLAlchemyApplicationDeliveryRepository
    ) -> DeliveryRetryRepository:
        return repository

    @provide(scope=Scope.REQUEST)
    def preview_webhook_repository(
        self, repository: SQLAlchemyApplicationDeliveryRepository
    ) -> PreviewWebhookRepository:
        return repository

    @provide(scope=Scope.APP)
    def request_fingerprint(self) -> RequestFingerprint:
        return Sha256RequestFingerprint()

    @provide(scope=Scope.APP)
    def webhook_verifier(self, settings: Settings) -> WebhookSignatureVerifier | None:
        if settings.github_webhook_secret is None:
            return None
        return HmacGitHubWebhookVerifier(settings.github_webhook_secret.get_secret_value())

    create_application_handler = provide(CreateApplicationHandler, scope=Scope.REQUEST)
    attach_application_resource_handler = provide(
        AttachApplicationResourceHandler, scope=Scope.REQUEST
    )
    deploy_application_handler = provide(DeployApplicationHandler, scope=Scope.REQUEST)
    retry_delivery_step_handler = provide(RetryDeliveryStepHandler, scope=Scope.REQUEST)
    read_applications_handler = provide(ReadApplicationsHandler, scope=Scope.REQUEST)
    read_application_handler = provide(ReadApplicationHandler, scope=Scope.REQUEST)
    read_deployment_history_handler = provide(ReadDeploymentHistoryHandler, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def process_preview_webhook_handler(
        self,
        repository: PreviewWebhookRepository,
        clock: Clock,
        images: ApprovedImageCatalog,
        verifier: WebhookSignatureVerifier | None,
        settings: Settings,
    ) -> ProcessGithubPreviewWebhookHandler:
        return ProcessGithubPreviewWebhookHandler(
            repository,
            clock,
            images,
            verifier,
            settings.github_allowed_repository_owner,
            settings.preview_owner_id,
            settings.preview_ttl_seconds,
        )

    @provide(scope=Scope.REQUEST)
    def approved_image_catalog(self, images: StaticApprovedImageCatalog) -> ApprovedImageCatalog:
        return images
