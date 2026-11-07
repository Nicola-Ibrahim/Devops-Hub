"""SQL persistence for project registrations and the durable request ledger."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from developer_platform.application.project_registration.command import RegisterProjectCommand
from developer_platform.application.project_registration.result import (
    EnvironmentDetails,
    ProjectRegistrationDetails,
)
from developer_platform.application.resource_requests.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import (
    PlatformRequestError,
    ledger_unavailable,
    resource_not_found,
)
from developer_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from developer_platform.domain.entities.operation import AcceptedResourceRequest
from developer_platform.domain.errors import DomainError
from developer_platform.domain.services.resource_admission import (
    CapacitySnapshot,
    ResourceAdmissionPolicy,
)
from developer_platform.domain.value_objects.idempotency_key import IdempotencyKey
from developer_platform.infra.persistence.models import (
    IdempotencyRecord,
    Operation,
    ProjectEnvironmentRow,
    ProjectRegistrationRow,
    QuotaBudget,
    Reservation,
    Resource,
    ResourceActivityRow,
)


class SQLAlchemyPlatformLedgerRepository:
    """Repository adapter; transaction lifecycle belongs to the request UoW."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_project(
        self, command: RegisterProjectCommand, project_id: UUID, team_id: UUID
    ) -> ProjectRegistrationDetails:
        try:
            # Serialize registration by the stable identity project name, including the
            # absent-row case. The CLI has already created/validated the identity rows.
            await self._session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:name, 0))"),
                {"name": command.name},
            )
            row = await self._session.get(ProjectRegistrationRow, project_id)
            if row is None:
                by_name = await self._session.scalar(
                    select(ProjectRegistrationRow).where(
                        ProjectRegistrationRow.name == command.name
                    )
                )
                if by_name is not None:
                    raise PlatformRequestError(
                        "project_configuration_conflict",
                        "Project name is already registered with different identity",
                        409,
                    )
                row = ProjectRegistrationRow(
                    project_id=project_id,
                    name=command.name,
                    owning_team_id=team_id,
                    owning_team_name=command.owning_team,
                    repository=command.repository,
                    configured=True,
                )
                self._session.add(row)
            elif row.configured:
                if (
                    row.name != command.name
                    or row.owning_team_id != team_id
                    or row.owning_team_name != command.owning_team
                    or row.repository != command.repository
                ):
                    raise PlatformRequestError(
                        "project_configuration_conflict",
                        "Project is already registered with different configuration",
                        409,
                    )
                existing_names = set(
                    await self._session.scalars(
                        select(ProjectEnvironmentRow.name).where(
                            ProjectEnvironmentRow.project_id == project_id
                        )
                    )
                )
                if existing_names != set(command.environments):
                    raise PlatformRequestError(
                        "project_configuration_conflict",
                        "Project is already registered with different environments",
                        409,
                    )
            else:
                row.name = command.name
                row.owning_team_id = team_id
                row.owning_team_name = command.owning_team
                row.repository = command.repository
                row.configured = True

            await self._session.flush()
            for name in command.environments:
                existing = await self._session.scalar(
                    select(ProjectEnvironmentRow).where(
                        ProjectEnvironmentRow.project_id == project_id,
                        ProjectEnvironmentRow.name == name,
                    )
                )
                if existing is None:
                    self._session.add(ProjectEnvironmentRow(project_id=project_id, name=name))

            project_budget = await self._session.get(QuotaBudget, ("project", str(project_id)))
            if project_budget is None:
                self._session.add(
                    QuotaBudget(
                        scope="project",
                        scope_id=str(project_id),
                        max_resources=3,
                        max_cpu_millis=2000,
                        max_memory_bytes=2147483648,
                        max_storage_bytes=5368709120,
                    )
                )
            await self._session.flush()
            details = await self._project_details(project_id)
            assert details is not None
            return details
        except PlatformRequestError:
            raise
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

    async def find_project(self, project_id: UUID) -> ProjectRegistrationDetails | None:
        try:
            return await self._project_details(project_id)
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

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

    async def _project_details(self, project_id: UUID) -> ProjectRegistrationDetails | None:
        row = await self._session.get(ProjectRegistrationRow, project_id)
        if row is None:
            return None
        environments = await self._session.scalars(
            select(ProjectEnvironmentRow)
            .where(ProjectEnvironmentRow.project_id == project_id)
            .order_by(ProjectEnvironmentRow.name, ProjectEnvironmentRow.id)
        )
        return ProjectRegistrationDetails(
            row.project_id,
            row.name,
            row.owning_team_id,
            row.owning_team_name,
            row.repository,
            row.configured,
            tuple(EnvironmentDetails(item.id, item.name) for item in environments),
        )

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
