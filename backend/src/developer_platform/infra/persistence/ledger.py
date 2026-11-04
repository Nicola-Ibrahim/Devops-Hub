"""SQL persistence for project registrations and the durable request ledger."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import (
    PlatformRequestError,
    ledger_unavailable,
    resource_not_found,
)
from developer_platform.application.ledger import (
    AcceptedDatabaseRequest,
    EnvironmentDetails,
    OperationDetails,
    PlatformLedgerRepository,
    PostgresOption,
    ProjectRegistrationDetails,
    RegisterProjectCommand,
    RequestDatabaseCommand,
    ResourceDetails,
)
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


class SQLAlchemyPlatformLedgerRepository(PlatformLedgerRepository):
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
        self, access: AccessContext, key: str, request_hash: str
    ) -> AcceptedDatabaseRequest | None:
        try:
            prior = await self._session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.user_id == access.user_id,
                    IdempotencyRecord.project_id == access.project_id,
                    IdempotencyRecord.route == "/api/v1/resources",
                    IdempotencyRecord.key == key,
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
            return AcceptedDatabaseRequest(prior.resource_id, prior.operation_id)
        except PlatformRequestError:
            raise
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

    async def accept_database_request(
        self,
        access: AccessContext,
        command: RequestDatabaseCommand,
        option: PostgresOption,
        key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
        installation_id: UUID,
    ) -> AcceptedDatabaseRequest:
        try:
            if access.project_id != command.project_id:
                raise resource_not_found()
            if not option.requestable:
                raise PlatformRequestError(
                    "option_unavailable", "This database option is not currently available", 409
                )

            registration = await self._session.scalar(
                select(ProjectRegistrationRow)
                .where(ProjectRegistrationRow.project_id == command.project_id)
                .with_for_update(read=True)
            )
            if registration is None or not registration.configured:
                raise resource_not_found()
            environment = await self._session.scalar(
                select(ProjectEnvironmentRow).where(
                    ProjectEnvironmentRow.id == command.environment_id,
                    ProjectEnvironmentRow.project_id == command.project_id,
                )
            )
            if environment is None:
                raise resource_not_found()

            # Lock both configured capacity rows in a globally deterministic order.
            quota_keys = sorted(
                (("project", str(command.project_id)), ("target", command.target_id))
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
                    IdempotencyRecord.project_id == command.project_id,
                    IdempotencyRecord.route == "/api/v1/resources",
                    IdempotencyRecord.key == key,
                )
            )
            if prior is not None:
                if prior.request_hash != request_hash:
                    raise PlatformRequestError(
                        "idempotency_conflict",
                        "Idempotency key was already used for a different request",
                        409,
                    )
                return AcceptedDatabaseRequest(prior.resource_id, prior.operation_id)

            usage: dict[tuple[str, str], tuple[int, int, int, int]] = {}
            for scope, scope_id in quota_keys:
                filters = (
                    (Resource.project_id == command.project_id,)
                    if scope == "project"
                    else (Resource.target_id == command.target_id,)
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
            requested = (
                1,
                option.size.cpu_millis,
                option.size.memory_bytes,
                option.size.storage_bytes,
            )
            dimensions = (
                "max_resources",
                "max_cpu_millis",
                "max_memory_bytes",
                "max_storage_bytes",
            )
            if any(
                used + add > getattr(budgets[budget_key], field)
                for budget_key in quota_keys
                for field, used, add in zip(dimensions, usage[budget_key], requested, strict=True)
            ):
                raise PlatformRequestError(
                    "quota_exceeded", "Resource request exceeds configured capacity", 409
                )

            # Capacity locks can wait: lease/deadline start at actual acceptance,
            # not at the earlier request/authentication time. Preserve validated TTL.
            ttl = expires_at - now
            accepted_at = await self._session.scalar(select(func.clock_timestamp()))
            if not isinstance(accepted_at, datetime) or accepted_at.tzinfo is None:
                raise ledger_unavailable()
            now = accepted_at.astimezone(UTC)
            expires_at = now + ttl
            resource_id, operation_id = uuid4(), uuid4()
            resource = Resource(
                id=resource_id,
                environment_id=command.environment_id,
                owner_id=access.user_id,
                project_id=command.project_id,
                display_name=command.display_name,
                template_id=command.template_id,
                target_id=command.target_id,
                size_id=command.size_id,
                configuration={
                    "version": command.version,
                    "max_lifetime_seconds": option.max_lifetime_seconds,
                    "cpu_millis": option.size.cpu_millis,
                    "memory_bytes": option.size.memory_bytes,
                    "storage_bytes": option.size.storage_bytes,
                    "storage_enforcement": option.size.storage_enforcement,
                },
                desired_state="running",
                status="pending",
                revision=1,
                generation=1,
                installation_id=installation_id,
                created_at=now,
                expires_at=expires_at,
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
                        cpu_millis=option.size.cpu_millis,
                        memory_bytes=option.size.memory_bytes,
                        storage_bytes=option.size.storage_bytes,
                    ),
                    IdempotencyRecord(
                        user_id=access.user_id,
                        project_id=command.project_id,
                        route="/api/v1/resources",
                        key=key,
                        request_hash=request_hash,
                        resource_id=resource_id,
                        operation_id=operation_id,
                        created_at=now,
                    ),
                    ResourceActivityRow(
                        actor_id=access.user_id,
                        project_id=command.project_id,
                        resource_id=resource_id,
                        operation_id=operation_id,
                        action="resource_requested",
                        created_at=now,
                    ),
                ]
            )
            await self._session.flush()
            return AcceptedDatabaseRequest(resource_id, operation_id)
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
