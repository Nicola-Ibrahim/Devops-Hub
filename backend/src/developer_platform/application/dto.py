"""Transport-independent values exchanged with provisioning workflows."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import UUID

if TYPE_CHECKING:
    from developer_platform.application.ledger import PostgresOption


@dataclass(frozen=True, slots=True)
class AccessContext:
    user_id: UUID
    project_id: UUID
    role: Literal["developer", "admin"]
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class CatalogResult:
    project_id: UUID
    templates: tuple["PostgresOption", ...] = ()
    message: str = "No verified provisioning provider is enabled; requests are disabled"
