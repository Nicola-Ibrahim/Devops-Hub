"""Project ownership and scope policy for temporary resources."""

from dataclasses import dataclass
from uuid import UUID

from devops_platform.domain.entities.resource import TemporaryResource
from devops_platform.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class ResourceActor:
    user_id: UUID
    project_id: UUID
    role: str
    scopes: frozenset[str]


class ResourceAccessPolicy:
    @staticmethod
    def require(resource: TemporaryResource, actor: ResourceActor, scope: str) -> None:
        if resource.project_id != actor.project_id:
            raise DomainError("Resource was not found.")
        if scope not in actor.scopes or (
            actor.user_id != resource.owner_id and actor.role != "admin"
        ):
            raise DomainError("Resource action is not permitted.")
