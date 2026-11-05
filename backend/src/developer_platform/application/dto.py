"""Transport-independent values exchanged with provisioning workflows."""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from developer_platform.domain.access import AccessContext as AccessContext

if TYPE_CHECKING:
    from developer_platform.application.ledger import PostgresOption


@dataclass(frozen=True, slots=True)
class CatalogResult:
    project_id: UUID
    templates: tuple["PostgresOption", ...] = ()
    message: str = "No verified provisioning provider is enabled; requests are disabled"
