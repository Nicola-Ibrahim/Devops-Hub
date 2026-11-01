"""Transport-independent values exchanged with provisioning workflows."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccessContext:
    user_id: UUID
    project_id: UUID
    role: Literal["developer", "admin"]
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class CatalogResult:
    project_id: UUID
    templates: tuple[dict[str, str], ...] = ()
    message: str = "No provisioning providers are enabled in this foundation release"
