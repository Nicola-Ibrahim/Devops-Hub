"""Catalog read workflow."""

from developer_platform.application.dto import AccessContext, CatalogResult
from developer_platform.application.errors import CatalogForbidden


class ReadCatalog:
    def execute(self, access: AccessContext) -> CatalogResult:
        if "catalog:read" not in access.scopes:
            raise CatalogForbidden()
        return CatalogResult(project_id=access.project_id)
