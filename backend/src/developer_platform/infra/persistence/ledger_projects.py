"""SQL persistence for project registrations and the durable request ledger."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from developer_platform.application.projects.command import RegisterProjectCommand
from developer_platform.application.projects.result import (
    EnvironmentDetails,
    ProjectRegistrationDetails,
)
from developer_platform.application.shared.errors import (
    PlatformRequestError,
    ledger_unavailable,
)
from developer_platform.infra.persistence.models import (
    ProjectEnvironmentRow,
    ProjectRegistrationRow,
    QuotaBudget,
)


class SQLAlchemyProjectRegistrationRepository:
    """Request-scoped persistence adapter for one platform capability."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_project(self, project_id: UUID) -> ProjectRegistrationDetails | None:
        try:
            return await self._project_details(project_id)
        except SQLAlchemyError as exc:
            raise ledger_unavailable() from exc

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
