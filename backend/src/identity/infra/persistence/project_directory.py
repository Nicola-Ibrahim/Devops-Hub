"""SQLAlchemy adapter for operator-managed project and team references."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from identity.application.errors import IdentityUnavailable
from identity.domain.project_access import ProjectAccessReferences
from identity.infra.persistence.models import ProjectRow, TeamRow


class SQLAlchemyProjectAccessDirectory:
    """Register identity references without creating user memberships or committing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_references(
        self, project_name: str, team_name: str
    ) -> ProjectAccessReferences:
        try:
            await self._session.execute(
                insert(TeamRow)
                .values(name=team_name)
                .on_conflict_do_nothing(index_elements=[TeamRow.name])
            )
            team = await self._session.scalar(
                select(TeamRow).where(TeamRow.name == team_name).with_for_update()
            )
            if team is None:
                raise IdentityUnavailable()

            await self._session.execute(
                insert(ProjectRow)
                .values(name=project_name)
                .on_conflict_do_nothing(index_elements=[ProjectRow.name])
            )
            project = await self._session.scalar(
                select(ProjectRow).where(ProjectRow.name == project_name).with_for_update()
            )
            if project is None:
                raise IdentityUnavailable()

            return ProjectAccessReferences(project_id=project.id, team_id=team.id)
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc
