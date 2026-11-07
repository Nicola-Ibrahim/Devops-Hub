"""Persistence interface for registered projects."""

from typing import Protocol
from uuid import UUID

from developer_platform.domain.entities.project import Project


class ProjectRepository(Protocol):
    async def find_project(self, project_id: UUID) -> Project | None: ...
