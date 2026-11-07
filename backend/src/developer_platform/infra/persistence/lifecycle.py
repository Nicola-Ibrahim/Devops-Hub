"""Transactional lifecycle persistence; external effects never run in these transactions."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError, resource_not_found
from developer_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from developer_platform.domain.entities.resource import TemporaryResource
from developer_platform.domain.errors import DomainError
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceActivity,
    ResourceConnectionSecret,
    ResourceSnapshot,
)
from developer_platform.domain.services.resource_access import ResourceAccessPolicy, ResourceActor
from developer_platform.domain.value_objects.lease import ResourceLease
from developer_platform.domain.value_objects.resource_name import ResourceName
from developer_platform.domain.value_objects.resource_spec import ResourceSpec
from developer_platform.domain.value_objects.revision import ResourceRevision
from developer_platform.domain.value_objects.statuses import DesiredState, ResourceStatus
from developer_platform.infra.persistence.models import (
    Operation,
    Resource,
    ResourceActivityRow,
    ResourceSecret,
)


def require_owner(access: AccessContext, resource: Resource, scope: str) -> None:
    if resource.project_id != access.project_id:
        raise resource_not_found()
    try:
        ResourceAccessPolicy.require(
            _to_lifecycle(resource).resource,
            ResourceActor(access.user_id, access.project_id, access.role, access.scopes),
            scope,
        )
    except DomainError as error:
        raise PlatformRequestError("forbidden", "This action is not permitted", 403) from error


def _to_lifecycle(resource: Resource) -> ResourceLifecycle:
    maximum = int(resource.configuration.get("max_lifetime_seconds", 86400))
    return ResourceLifecycle(
        TemporaryResource(
            id=resource.id,
            project_id=resource.project_id,
            environment_id=resource.environment_id,
            owner_id=resource.owner_id,
            installation_id=resource.installation_id,
            name=ResourceName(resource.display_name),
            specification=ResourceSpec(
                resource.template_id,
                str(resource.configuration.get("version", "unknown")),
                resource.target_id,
                resource.size_id,
                int(resource.configuration.get("cpu_millis", 0)),
                int(resource.configuration.get("memory_bytes", 0)),
                int(resource.configuration.get("storage_bytes", 0)),
                maximum,
                str(resource.configuration.get("storage_enforcement", "reservation_only")),
            ),
            lease=ResourceLease(
                resource.created_at.astimezone(UTC),
                resource.expires_at.astimezone(UTC),
                maximum,
            ),
            desired_state=DesiredState(resource.desired_state),
            status=ResourceStatus(resource.status),
            revision=resource.revision,
            generation=resource.generation,
            created_at=resource.created_at.astimezone(UTC),
            failure_code=resource.failure_code,
        )
    )


def _apply_lifecycle(resource: Resource, lifecycle: ResourceLifecycle) -> None:
    state = lifecycle.resource
    resource.desired_state = state.desired_state.value
    resource.status = state.status.value
    resource.revision = state.revision
    resource.generation = state.generation
    resource.expires_at = state.lease.expires_at


async def mark_for_deletion(
    session: AsyncSession, resource: Resource, reason: str, actor_id: UUID | None, now: datetime
) -> Operation:
    if resource.desired_state != "deleted":
        resource.desired_state = "deleted"
        resource.generation += 1
        resource.revision += 1
        resource.deletion_reason = reason
        resource.status = "deleting"
    operation = await session.scalar(
        select(Operation).where(
            Operation.resource_id == resource.id,
            Operation.resource_revision == resource.generation,
            Operation.action == "delete",
        )
    )
    if operation is None:
        operation = Operation(
            id=uuid4(),
            resource_id=resource.id,
            resource_revision=resource.generation,
            action="delete",
            status="pending",
            next_attempt_at=now,
            deadline_at=now + timedelta(days=1),
            created_at=now,
        )
        session.add(operation)
        await session.flush()
        session.add(
            ResourceActivityRow(
                actor_id=actor_id,
                project_id=resource.project_id,
                resource_id=resource.id,
                operation_id=operation.id,
                action="resource_deletion_requested",
                created_at=now,
            )
        )
    elif operation.status in {"failed", "cancelled"}:
        operation.status = "pending"
        operation.next_attempt_at = now
    return operation


class SQLAlchemyResourceLifecycle:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def renew(
        self, access: AccessContext, resource_id: UUID, revision: int, expiry: datetime
    ) -> Resource:
        resource = await self.session.scalar(
            select(Resource)
            .where(Resource.id == resource_id, Resource.project_id == access.project_id)
            .with_for_update()
        )
        if resource is None:
            raise resource_not_found()
        require_owner(access, resource, "resources:write")
        if resource.revision != revision:
            raise PlatformRequestError(
                "revision_conflict", "Resource changed; refresh before retrying", 409
            )
        now = await self.session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        lifecycle = _to_lifecycle(resource).renew(
            expected_revision=ResourceRevision(revision),
            requested_expiry=expiry,
            now=now.astimezone(UTC),
        )
        _apply_lifecycle(resource, lifecycle)
        operation = await self.session.scalar(
            select(Operation)
            .where(Operation.resource_id == resource.id)
            .order_by(Operation.created_at)
            .limit(1)
        )
        if operation is not None:
            self.session.add(
                ResourceActivityRow(
                    actor_id=access.user_id,
                    project_id=resource.project_id,
                    resource_id=resource.id,
                    operation_id=operation.id,
                    action="resource_renewed",
                    created_at=now,
                )
            )
        return resource

    async def delete(self, access: AccessContext, resource_id: UUID) -> Operation:
        resource = await self.session.scalar(
            select(Resource)
            .where(Resource.id == resource_id, Resource.project_id == access.project_id)
            .with_for_update()
        )
        if resource is None:
            raise resource_not_found()
        require_owner(access, resource, "resources:write")
        now = await self.session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        lifecycle = _to_lifecycle(resource).request_deletion()
        _apply_lifecycle(resource, lifecycle)
        resource.deletion_reason = "requested"
        return await mark_for_deletion(self.session, resource, "requested", access.user_id, now)

    async def connection(
        self, access: AccessContext, resource_id: UUID
    ) -> tuple[Resource, ResourceSecret]:
        resource = await self.session.scalar(
            select(Resource)
            .where(Resource.id == resource_id, Resource.project_id == access.project_id)
            .with_for_update(read=True)
        )
        if resource is None:
            raise resource_not_found()
        require_owner(access, resource, "connections:read")
        now = await self.session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        try:
            _to_lifecycle(resource).require_connection(now.astimezone(UTC))
        except DomainError as error:
            raise PlatformRequestError(
                "resource_not_ready", "Resource access is not available", 409
            ) from error
        secret = await self.session.get(ResourceSecret, resource.id)
        if secret is None or resource.endpoint is None:
            raise PlatformRequestError(
                "resource_not_ready", "Resource access is not available", 409
            )
        operation = await self.session.scalar(
            select(Operation)
            .where(Operation.resource_id == resource.id)
            .order_by(Operation.created_at)
            .limit(1)
        )
        if operation is not None:
            self.session.add(
                ResourceActivityRow(
                    actor_id=access.user_id,
                    project_id=resource.project_id,
                    resource_id=resource.id,
                    operation_id=operation.id,
                    action="resource_connection_accessed",
                    created_at=now,
                )
            )
        return resource, secret


class SQLAlchemyResourceLifecycleRepository:
    """Map lifecycle persistence to domain-facing records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lifecycle = SQLAlchemyResourceLifecycle(session)

    @staticmethod
    def _access(
        project_id: UUID,
        actor_id: UUID,
        actor_role: Literal["developer", "admin"],
        scopes: frozenset[str],
    ) -> AccessContext:
        return AccessContext(actor_id, project_id, actor_role, scopes)

    async def renew(
        self,
        *,
        project_id: UUID,
        actor_id: UUID,
        actor_role: Literal["developer", "admin"],
        scopes: frozenset[str],
        resource_id: UUID,
        revision: int,
        expiry: datetime,
    ) -> ResourceSnapshot:
        row = await self.lifecycle.renew(
            self._access(project_id, actor_id, actor_role, scopes), resource_id, revision, expiry
        )
        return ResourceSnapshot(
            id=row.id,
            project_id=row.project_id,
            environment_id=row.environment_id,
            owner_id=row.owner_id,
            display_name=row.display_name,
            template_id=row.template_id,
            target_id=row.target_id,
            size_id=row.size_id,
            desired_state=row.desired_state,
            status=row.status,
            revision=row.revision,
            created_at=row.created_at,
            expires_at=row.expires_at,
            failure_code=row.failure_code,
        )

    async def delete(
        self,
        *,
        project_id: UUID,
        actor_id: UUID,
        actor_role: Literal["developer", "admin"],
        scopes: frozenset[str],
        resource_id: UUID,
    ) -> UUID:
        operation = await self.lifecycle.delete(
            self._access(project_id, actor_id, actor_role, scopes), resource_id
        )
        return operation.id

    async def connection(
        self,
        *,
        project_id: UUID,
        actor_id: UUID,
        actor_role: Literal["developer", "admin"],
        scopes: frozenset[str],
        resource_id: UUID,
    ) -> ResourceConnectionSecret:
        row, secret = await self.lifecycle.connection(
            self._access(project_id, actor_id, actor_role, scopes), resource_id
        )
        assert row.endpoint is not None
        return ResourceConnectionSecret(
            resource_id=row.id,
            host=str(row.endpoint["host"]),
            port=int(row.endpoint["port"]),
            ciphertext=secret.ciphertext,
            key_id=secret.key_id,
        )

    async def activity(self, project_id: UUID, limit: int) -> tuple[ResourceActivity, ...]:
        rows = await self.session.scalars(
            select(ResourceActivityRow)
            .where(ResourceActivityRow.project_id == project_id)
            .order_by(ResourceActivityRow.created_at.desc())
            .limit(limit)
        )
        return tuple(
            ResourceActivity(
                id=row.id,
                actor_id=row.actor_id,
                resource_id=row.resource_id,
                operation_id=row.operation_id,
                action=row.action,
                created_at=row.created_at,
            )
            for row in rows
        )
