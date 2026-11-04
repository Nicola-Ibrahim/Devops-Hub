"""Transactional lifecycle persistence; external effects never run in these transactions."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError, resource_not_found
from developer_platform.domain.leases import LeasePolicy
from developer_platform.domain.resources import DesiredState, ResourceStatus
from developer_platform.infra.persistence.models import (
    Operation,
    Resource,
    ResourceActivityRow,
    ResourceSecret,
)


def require_owner(access: AccessContext, resource: Resource, scope: str) -> None:
    if resource.project_id != access.project_id:
        raise resource_not_found()
    if scope not in access.scopes or (
        access.user_id != resource.owner_id and access.role != "admin"
    ):
        raise PlatformRequestError("forbidden", "This action is not permitted", 403)


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
        resource.expires_at = LeasePolicy(
            max_lifetime_seconds=int(resource.configuration.get("max_lifetime_seconds", 86400))
        ).renewal_expiry(
            created_at=resource.created_at.astimezone(UTC),
            current_expiry=resource.expires_at.astimezone(UTC),
            requested_expiry=expiry,
            now=now.astimezone(UTC),
            desired_state=DesiredState(resource.desired_state),
            status=ResourceStatus(resource.status),
        )
        resource.revision += 1
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
        if (
            resource.status != "ready"
            or resource.desired_state != "running"
            or resource.expires_at <= now
        ):
            raise PlatformRequestError(
                "resource_not_ready", "Resource access is not available", 409
            )
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
