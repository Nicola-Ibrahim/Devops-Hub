from identity.application.list_project_members.query import ListProjectMembersByActorQuery
from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.records import ProjectMemberDetails


class ListProjectMembersHandler:
    def __init__(self, repository: ProjectMembershipRepository) -> None:
        self.repository = repository

    async def execute(
        self, query: ListProjectMembersByActorQuery
    ) -> tuple[ProjectMemberDetails, ...]:
        return await self.repository.list_project_members(
            actor_id=query.actor_id, project_id=query.project_id
        )
