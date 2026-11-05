"""Project-scoped authorization for platform use cases."""

from uuid import UUID

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import CatalogForbidden, resource_not_found


def require_project_scope(access: AccessContext, project_id: UUID, scope: str) -> None:
    if access.project_id != project_id:
        raise resource_not_found()
    if scope not in access.scopes:
        raise CatalogForbidden()
