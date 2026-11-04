"""Operator-only identity references. Team ownership does not confer membership."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ProjectAccessReferences:
    project_id: UUID
    team_id: UUID


class ProjectAccessDirectory(Protocol):
    async def register_references(
        self, project_name: str, team_name: str
    ) -> ProjectAccessReferences: ...
