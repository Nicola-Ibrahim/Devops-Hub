"""Bridge application delivery to the durable database ledger, without provider effects."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devops_platform.application.database_provisioning.submit_database_request.command import (
    DatabaseRequest,
    RequestTemporaryDatabase,
)
from devops_platform.application.database_provisioning.submit_database_request.handler import (
    RequestTemporaryDatabaseHandler,
)
from devops_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from devops_platform.application.shared.dto import AccessContext
from devops_platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentSpec,
)
from devops_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
)
from devops_platform.authorization import ALL_SCOPES, authorize_platform_action
from devops_platform.infra.persistence.models import Resource
from devops_platform.infra.persistence.resource_repository import SQLAlchemyResourceRepository
from identity.infra.persistence.resource_request_authority import resource_request_role


class LedgerApplicationResources:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        catalog: ApprovedPostgresCatalog,
        installation_id: UUID | None,
    ) -> None:
        self.sessions, self.catalog, self.installation_id = sessions, catalog, installation_id

    async def request(
        self,
        *,
        project_id: UUID,
        environment_id: UUID,
        owner_id: UUID,
        command: ResourceAttachmentSpec,
        idempotency_key: str,
    ) -> UUID:
        async with self.sessions() as session, session.begin():
            role = await resource_request_role(session, owner_id, project_id)
            if role is None:
                raise ApplicationDeliveryFailure("resource_owner_not_authorized", retryable=False)
            access = AccessContext(owner_id, project_id, role, frozenset(ALL_SCOPES))
            request = DatabaseRequest(
                project_id,
                environment_id,
                "application-database",
                command.template_id,
                command.version,
                command.target_id,
                command.size_id,
                command.ttl_seconds,
            )
            authorize_platform_action(RequestTemporaryDatabase(access, request, idempotency_key))
            usecase = RequestTemporaryDatabaseHandler(
                SQLAlchemyResourceRepository(session),
                self.catalog,
                lambda: datetime.now(UTC),
                lambda value: hashlib.sha256(
                    json.dumps(asdict(value), sort_keys=True, default=str).encode()
                ).hexdigest(),
                self.installation_id,
            )
            # Delivery keys include UUIDs/kinds; hash to the resource API's bounded key contract.
            key = "app:" + hashlib.sha256(idempotency_key.encode()).hexdigest()
            return (
                await usecase.execute(RequestTemporaryDatabase(access, request, key))
            ).resource_id

    async def ready(self, project_id: UUID, resource_id: UUID) -> bool:
        async with self.sessions() as session:
            row = await session.scalar(
                select(Resource).where(
                    Resource.id == resource_id, Resource.project_id == project_id
                )
            )
            return bool(
                row is not None
                and row.status == "ready"
                and row.desired_state == "running"
                and row.expires_at > datetime.now(UTC)
            )

    async def delete(
        self, project_id: UUID, owner_id: UUID, resource_id: UUID, idempotency_key: str
    ) -> None:
        async with self.sessions() as session, session.begin():
            resource = await session.scalar(
                select(Resource)
                .where(
                    Resource.id == resource_id,
                    Resource.project_id == project_id,
                    Resource.owner_id == owner_id,
                )
                .with_for_update()
            )
            if resource is None:
                raise ApplicationDeliveryFailure("resource_identity_mismatch", retryable=False)
            if resource.status == "deleted":
                return
            await SQLAlchemyResourceRepository(session).mark_for_deletion(
                resource, "pr_closed", None, datetime.now(UTC)
            )
        # Cleanup completes only after the database worker confirms physical deletion.
        raise ApplicationDeliveryFailure("resource_cleanup_pending")
