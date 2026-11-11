"""Declarative bindings; this is the only layer selecting concrete implementations."""

import hashlib
import json
from dataclasses import asdict

from dishka import Provider, Scope, provide

from developer_platform.application.database_lifecycle.delete_database.handler import (
    DeleteTemporaryDatabaseHandler,
)
from developer_platform.application.database_lifecycle.ports import ResourceCredentialCipher
from developer_platform.application.database_lifecycle.read_activity.handler import (
    ListResourceActivityQueryHandler,
)
from developer_platform.application.database_lifecycle.read_connection.handler import (
    GetDatabaseConnectionQueryHandler,
)
from developer_platform.application.database_lifecycle.renew_lease.handler import (
    RenewDatabaseLeaseHandler,
)
from developer_platform.application.database_provisioning.read_resources.handler import (
    ReadOperationHandler,
    ReadProjectHandler,
    ReadProjectsHandler,
    ReadResourceHandler,
    ReadResourcesHandler,
)
from developer_platform.application.database_provisioning.read_resources.port import (
    PlatformResourceReadRepository,
)
from developer_platform.application.database_provisioning.submit_database_request.command import (
    DatabaseRequest,
)
from developer_platform.application.database_provisioning.submit_database_request.handler import (
    RequestTemporaryDatabaseHandler,
)
from developer_platform.application.projects.handler import RegisterProjectHandler
from developer_platform.application.projects.port import ProjectRegistrationRepository
from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from developer_platform.domain.interfaces.resource_request_repository import (
    ResourceRequestRepository,
)
from developer_platform.domain.resource_lifecycle_repository import ResourceLifecycleRepository
from developer_platform.infra.credentials import FernetResourceCredentialCipher
from developer_platform.infra.persistence.ledger import SQLAlchemyPlatformLedgerRepository
from developer_platform.infra.persistence.lifecycle import SQLAlchemyResourceLifecycleRepository
from shared.infra.clock import Clock
from shared.infra.settings import Settings


class PlatformProvider(Provider):
    project_handler = provide(ReadProjectHandler, scope=Scope.REQUEST)
    projects_handler = provide(ReadProjectsHandler, scope=Scope.REQUEST)
    resources_handler = provide(ReadResourcesHandler, scope=Scope.REQUEST)
    resource_handler = provide(ReadResourceHandler, scope=Scope.REQUEST)
    operation_handler = provide(ReadOperationHandler, scope=Scope.REQUEST)
    renew_handler = provide(RenewDatabaseLeaseHandler, scope=Scope.REQUEST)
    delete_handler = provide(DeleteTemporaryDatabaseHandler, scope=Scope.REQUEST)
    connection_handler = provide(GetDatabaseConnectionQueryHandler, scope=Scope.REQUEST)
    activity_handler = provide(ListResourceActivityQueryHandler, scope=Scope.REQUEST)
    sql_ledger_repository = provide(SQLAlchemyPlatformLedgerRepository, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def project_registration_repository(
        self, repository: SQLAlchemyPlatformLedgerRepository
    ) -> ProjectRegistrationRepository:
        return repository

    @provide(scope=Scope.REQUEST)
    def platform_resource_read_repository(
        self, repository: SQLAlchemyPlatformLedgerRepository
    ) -> PlatformResourceReadRepository:
        return repository

    @provide(scope=Scope.REQUEST)
    def request_repository(
        self, repository: SQLAlchemyPlatformLedgerRepository
    ) -> ResourceRequestRepository:
        return repository

    register = provide(RegisterProjectHandler, scope=Scope.REQUEST)
    lifecycle_repository = provide(
        SQLAlchemyResourceLifecycleRepository,
        provides=ResourceLifecycleRepository,
        scope=Scope.REQUEST,
    )

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
        from developer_platform.application.resource_catalog.models import PostgresOption

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
    def catalog(self, catalog: ApprovedPostgresCatalog) -> ReadCatalogQueryHandler:
        return ReadCatalogQueryHandler(catalog)

    @provide(scope=Scope.REQUEST)
    def request(
        self,
        repository: ResourceRequestRepository,
        catalog: ApprovedPostgresCatalog,
        clock: Clock,
        settings: Settings,
    ) -> RequestTemporaryDatabaseHandler:
        def fingerprint(command: DatabaseRequest) -> str:
            payload = json.dumps(
                asdict(command), sort_keys=True, separators=(",", ":"), default=str
            )
            return hashlib.sha256(payload.encode()).hexdigest()

        return RequestTemporaryDatabaseHandler(
            repository, catalog, clock, fingerprint, settings.installation_id
        )
