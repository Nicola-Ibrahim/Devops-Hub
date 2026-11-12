"""Aggregate persistence for resource requests and lifecycle transitions."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from developer_platform.application.database_provisioning.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import (
    PlatformRequestError,
    ledger_unavailable,
    resource_not_found,
)
from developer_platform.application.shared.resource_repository import (
    ResourceActivity,
    ResourceConnectionSecret,
    ResourceRepository,
    ResourceSnapshot,
)
from developer_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from developer_platform.domain.entities.operation import AcceptedResourceRequest
from developer_platform.domain.entities.resource import TemporaryResource
from developer_platform.domain.errors import DomainError
from developer_platform.domain.services.resource_access import ResourceAccessPolicy, ResourceActor
from developer_platform.domain.services.resource_admission import (
    CapacitySnapshot,
    ResourceAdmissionPolicy,
)
from developer_platform.domain.value_objects.idempotency_key import IdempotencyKey
from developer_platform.domain.value_objects.lease import ResourceLease
from developer_platform.domain.value_objects.resource_name import ResourceName
from developer_platform.domain.value_objects.resource_spec import ResourceSpec
from developer_platform.domain.value_objects.revision import ResourceRevision
from developer_platform.domain.value_objects.statuses import DesiredState, ResourceStatus
from developer_platform.infra.persistence.models import (
    IdempotencyRecord,
    Operation,
    ProjectEnvironmentRow,
    ProjectRegistrationRow,
    QuotaBudget,
    Reservation,
    Resource,
    ResourceActivityRow,
    ResourceSecret,
)


def _require_owner(access: AccessContext, resource: Resource, scope: str) -> None:
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


class SQLAlchemyResourceRepository(ResourceRepository):
    """Persist a resource aggregate and its atomic request/lifecycle writes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replay_request(
        self, access: AccessContext, key: IdempotencyKey, request_hash: str
    ) -> AcceptedResourceRequest | None:
        try:
            prior = await self._session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.user_id == access.user_id,
                    IdempotencyRecord.project_id == access.project_id,
                    IdempotencyRecord.route == "/api/v1/resources",
                    IdempotencyRecord.key == key.value,
                )
            )
            if prior is None:
                return None
            if prior.request_hash != request_hash:
                raise PlatformRequestError(
                    "idempotency_conflict",
                    "Idempotency key was already used for a different request",
                    409,
                )
            return AcceptedResourceRequest(prior.resource_id, prior.operation_id)
        except PlatformRequestError:
            raise
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

    async def renew(
        self, *, access: AccessContext, resource_id: UUID, revision: int, expiry: datetime
    ) -> ResourceSnapshot:
        resource = await self._session.scalar(
            select(Resource)
            .where(Resource.id == resource_id, Resource.project_id == access.project_id)
            .with_for_update()
        )
        if resource is None:
            raise resource_not_found()
        _require_owner(access, resource, "resources:write")
        if resource.revision != revision:
            raise PlatformRequestError(
                "revision_conflict", "Resource changed; refresh before retrying", 409
            )
        now = await self._session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        lifecycle = _to_lifecycle(resource).renew(
            expected_revision=ResourceRevision(revision),
            requested_expiry=expiry,
            now=now.astimezone(UTC),
        )
        _apply_lifecycle(resource, lifecycle)
        operation = await self._session.scalar(
            select(Operation)
            .where(Operation.resource_id == resource.id)
            .order_by(Operation.created_at)
            .limit(1)
        )
        if operation is not None:
            self._session.add(
                ResourceActivityRow(
                    actor_id=access.user_id,
                    project_id=resource.project_id,
                    resource_id=resource.id,
                    operation_id=operation.id,
                    action="resource_renewed",
                    created_at=now,
                )
            )
        return ResourceSnapshot(
            id=resource.id,
            project_id=resource.project_id,
            environment_id=resource.environment_id,
            owner_id=resource.owner_id,
            display_name=resource.display_name,
            template_id=resource.template_id,
            target_id=resource.target_id,
            size_id=resource.size_id,
            desired_state=resource.desired_state,
            status=resource.status,
            revision=resource.revision,
            created_at=resource.created_at,
            expires_at=resource.expires_at,
            failure_code=resource.failure_code,
        )

    async def delete(self, *, access: AccessContext, resource_id: UUID) -> UUID:
        resource = await self._session.scalar(
            select(Resource)
            .where(Resource.id == resource_id, Resource.project_id == access.project_id)
            .with_for_update()
        )
        if resource is None:
            raise resource_not_found()
        _require_owner(access, resource, "resources:write")
        now = await self._session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        lifecycle = _to_lifecycle(resource).request_deletion()
        _apply_lifecycle(resource, lifecycle)
        resource.deletion_reason = "requested"
        operation = await self.mark_for_deletion(resource, "requested", access.user_id, now)
        return operation.id

    async def mark_for_deletion(
        self, resource: Resource, reason: str, actor_id: UUID | None, now: datetime
    ) -> Operation:
        if resource.desired_state != "deleted":
            resource.desired_state = "deleted"
            resource.generation += 1
            resource.revision += 1
            resource.deletion_reason = reason
            resource.status = "deleting"
        operation = await self._session.scalar(
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
            self._session.add(operation)
            await self._session.flush()
            self._session.add(
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

    async def connection(
        self, *, access: AccessContext, resource_id: UUID
    ) -> ResourceConnectionSecret:
        resource = await self._session.scalar(
            select(Resource)
            .where(Resource.id == resource_id, Resource.project_id == access.project_id)
            .with_for_update(read=True)
        )
        if resource is None:
            raise resource_not_found()
        _require_owner(access, resource, "connections:read")
        now = await self._session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        try:
            _to_lifecycle(resource).require_connection(now.astimezone(UTC))
        except DomainError as error:
            raise PlatformRequestError(
                "resource_not_ready", "Resource access is not available", 409
            ) from error
        secret = await self._session.get(ResourceSecret, resource.id)
        if secret is None or resource.endpoint is None:
            raise PlatformRequestError(
                "resource_not_ready", "Resource access is not available", 409
            )
        operation = await self._session.scalar(
            select(Operation)
            .where(Operation.resource_id == resource.id)
            .order_by(Operation.created_at)
            .limit(1)
        )
        if operation is not None:
            self._session.add(
                ResourceActivityRow(
                    actor_id=access.user_id,
                    project_id=resource.project_id,
                    resource_id=resource.id,
                    operation_id=operation.id,
                    action="resource_connection_accessed",
                    created_at=now,
                )
            )
        return ResourceConnectionSecret(
            resource_id=resource.id,
            host=str(resource.endpoint["host"]),
            port=int(resource.endpoint["port"]),
            ciphertext=secret.ciphertext,
            key_id=secret.key_id,
        )

    async def activity(self, project_id: UUID, limit: int) -> tuple[ResourceActivity, ...]:
        rows = await self._session.scalars(
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

    async def list_resources(
        self, project_id: UUID, after: UUID | None, limit: int
    ) -> tuple[ResourceDetails, ...]:
        try:
            statement = select(Resource).where(Resource.project_id == project_id)
            if after is not None:
                statement = statement.where(Resource.id > after)
            rows = await self._session.scalars(statement.order_by(Resource.id).limit(limit))
            return tuple(self._resource_details(row) for row in rows)
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

    async def find_resource(self, project_id: UUID, resource_id: UUID) -> ResourceDetails | None:
        try:
            row = await self._session.scalar(
                select(Resource).where(
                    Resource.id == resource_id, Resource.project_id == project_id
                )
            )
            return None if row is None else self._resource_details(row)
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

    async def find_operation(self, project_id: UUID, operation_id: UUID) -> OperationDetails | None:
        try:
            row = await self._session.execute(
                select(Operation, Resource)
                .join(Resource, Resource.id == Operation.resource_id)
                .where(Operation.id == operation_id, Resource.project_id == project_id)
            )
            found = row.first()
            if found is None:
                return None
            operation, _resource = found
            return OperationDetails(
                operation.id,
                operation.resource_id,
                operation.action,
                operation.status,
                operation.attempts,
                operation.next_attempt_at,
                operation.error_code,
            )
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

    @staticmethod
    def _resource_details(row: Resource) -> ResourceDetails:
        return ResourceDetails(
            row.id,
            row.project_id,
            row.environment_id,
            row.owner_id,
            row.display_name,
            row.template_id,
            row.target_id,
            row.size_id,
            row.desired_state,
            row.status,
            row.revision,
            row.created_at,
            row.expires_at,
            row.failure_code,
        )

    async def accept_database_request(
        self,
        access: AccessContext,
        lifecycle: ResourceLifecycle,
        key: IdempotencyKey,
        request_hash: str,
    ) -> AcceptedResourceRequest:
        try:
            requested_resource = lifecycle.resource
            if access.project_id != requested_resource.project_id:
                raise resource_not_found()

            registration = await self._session.scalar(
                select(ProjectRegistrationRow)
                .where(ProjectRegistrationRow.project_id == requested_resource.project_id)
                .with_for_update(read=True)
            )
            if registration is None or not registration.configured:
                raise resource_not_found()
            environment = await self._session.scalar(
                select(ProjectEnvironmentRow).where(
                    ProjectEnvironmentRow.id == requested_resource.environment_id,
                    ProjectEnvironmentRow.project_id == requested_resource.project_id,
                )
            )
            if environment is None:
                raise resource_not_found()

            # Lock both configured capacity rows in a globally deterministic order.
            quota_keys = sorted(
                (
                    ("project", str(requested_resource.project_id)),
                    ("target", requested_resource.specification.target_id),
                )
            )
            budgets: dict[tuple[str, str], QuotaBudget] = {}
            for scope, scope_id in quota_keys:
                budget = await self._session.scalar(
                    select(QuotaBudget)
                    .where(QuotaBudget.scope == scope, QuotaBudget.scope_id == scope_id)
                    .with_for_update()
                )
                if budget is None:
                    raise PlatformRequestError(
                        "quota_unconfigured", "Required resource quota is not configured", 503
                    )
                budgets[(scope, scope_id)] = budget

            prior = await self._session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.user_id == access.user_id,
                    IdempotencyRecord.project_id == requested_resource.project_id,
                    IdempotencyRecord.route == "/api/v1/resources",
                    IdempotencyRecord.key == key.value,
                )
            )
            if prior is not None:
                if prior.request_hash != request_hash:
                    raise PlatformRequestError(
                        "idempotency_conflict",
                        "Idempotency key was already used for a different request",
                        409,
                    )
                return AcceptedResourceRequest(prior.resource_id, prior.operation_id)

            usage: dict[tuple[str, str], tuple[int, int, int, int]] = {}
            for scope, scope_id in quota_keys:
                filters = (
                    (Resource.project_id == requested_resource.project_id,)
                    if scope == "project"
                    else (Resource.target_id == requested_resource.specification.target_id,)
                )
                totals = (
                    await self._session.execute(
                        select(
                            func.count(Resource.id),
                            func.coalesce(func.sum(Reservation.cpu_millis), 0),
                            func.coalesce(func.sum(Reservation.memory_bytes), 0),
                            func.coalesce(func.sum(Reservation.storage_bytes), 0),
                        )
                        .select_from(Reservation)
                        .join(Resource, Resource.id == Reservation.resource_id)
                        .where(Reservation.released_at.is_(None), *filters)
                    )
                ).one()
                usage[(scope, scope_id)] = (totals[0], totals[1], totals[2], totals[3])
            requested = CapacitySnapshot(
                1,
                requested_resource.specification.cpu_millis,
                requested_resource.specification.memory_bytes,
                requested_resource.specification.storage_bytes,
            )
            try:
                for budget_key in quota_keys:
                    budget = budgets[budget_key]
                    ResourceAdmissionPolicy.require_capacity(
                        CapacitySnapshot(*usage[budget_key]),
                        CapacitySnapshot(
                            budget.max_resources,
                            budget.max_cpu_millis,
                            budget.max_memory_bytes,
                            budget.max_storage_bytes,
                        ),
                        requested,
                    )
            except DomainError as error:
                raise PlatformRequestError(
                    "quota_exceeded", "Resource request exceeds configured capacity", 409
                ) from error

            # Capacity locks can wait: lease/deadline start at actual acceptance,
            # not at the earlier request/authentication time. Preserve validated TTL.
            accepted_at = await self._session.scalar(select(func.clock_timestamp()))
            if not isinstance(accepted_at, datetime) or accepted_at.tzinfo is None:
                raise ledger_unavailable()
            accepted = lifecycle.accepted_at(accepted_at.astimezone(UTC))
            state = accepted.resource
            now = state.created_at
            resource_id, operation_id = state.id, uuid4()
            resource = Resource(
                id=resource_id,
                environment_id=state.environment_id,
                owner_id=state.owner_id,
                project_id=state.project_id,
                display_name=state.name.value,
                template_id=state.specification.template_id,
                target_id=state.specification.target_id,
                size_id=state.specification.size_id,
                configuration={
                    "version": state.specification.version,
                    "max_lifetime_seconds": state.specification.max_lifetime_seconds,
                    "cpu_millis": state.specification.cpu_millis,
                    "memory_bytes": state.specification.memory_bytes,
                    "storage_bytes": state.specification.storage_bytes,
                    "storage_enforcement": state.specification.storage_enforcement,
                },
                desired_state=state.desired_state.value,
                status=state.status.value,
                revision=state.revision,
                generation=state.generation,
                installation_id=state.installation_id,
                created_at=now,
                expires_at=state.lease.expires_at,
            )
            operation = Operation(
                id=operation_id,
                resource_id=resource_id,
                resource_revision=1,
                action="provision",
                status="pending",
                attempts=0,
                next_attempt_at=now,
                deadline_at=now + timedelta(minutes=5),
                provider_outcome_uncertain=False,
                created_at=now,
            )
            # Explicit parent flushes keep insertion order independent of ORM
            # relationship declarations while retaining one atomic transaction.
            self._session.add(resource)
            await self._session.flush()
            self._session.add(operation)
            await self._session.flush()
            self._session.add_all(
                [
                    Reservation(
                        resource_id=resource_id,
                        cpu_millis=state.specification.cpu_millis,
                        memory_bytes=state.specification.memory_bytes,
                        storage_bytes=state.specification.storage_bytes,
                    ),
                    IdempotencyRecord(
                        user_id=access.user_id,
                        project_id=state.project_id,
                        route="/api/v1/resources",
                        key=key.value,
                        request_hash=request_hash,
                        resource_id=resource_id,
                        operation_id=operation_id,
                        created_at=now,
                    ),
                    ResourceActivityRow(
                        actor_id=access.user_id,
                        project_id=state.project_id,
                        resource_id=resource_id,
                        operation_id=operation_id,
                        action="resource_requested",
                        created_at=now,
                    ),
                ]
            )
            await self._session.flush()
            return AcceptedResourceRequest(resource_id, operation_id)
        except PlatformRequestError:
            raise
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc
