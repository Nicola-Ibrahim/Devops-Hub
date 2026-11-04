"""Catalog read workflow."""

from developer_platform.application.dto import AccessContext, CatalogResult
from developer_platform.application.errors import CatalogForbidden
from developer_platform.application.requests import ApprovedPostgresCatalog


class ReadCatalog:
    def __init__(self, catalog: ApprovedPostgresCatalog | None = None) -> None:
        self.catalog = catalog if catalog is not None else ApprovedPostgresCatalog()

    def execute(self, access: AccessContext) -> CatalogResult:
        if "catalog:read" not in access.scopes:
            raise CatalogForbidden()
        return CatalogResult(project_id=access.project_id, templates=self.catalog.options)
