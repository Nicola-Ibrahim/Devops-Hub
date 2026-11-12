"""Transport-independent values exchanged with provisioning workflows."""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from devops_hub.platform.domain.access import AccessContext as AccessContext

if TYPE_CHECKING:
    from devops_hub.platform.application.resource_catalog.models import PostgresOption


@dataclass(frozen=True, slots=True)
class CatalogResult:
    project_id: UUID
    templates: tuple["PostgresOption", ...] = ()
    message: str = "No verified provisioning provider is enabled; requests are disabled"
