"""Catalog read workflow."""

from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.shared.dto import AccessContext, CatalogResult


class ReadCatalogQueryHandler:
    def __init__(self, catalog: ApprovedPostgresCatalog | None = None) -> None:
        self.catalog = catalog if catalog is not None else ApprovedPostgresCatalog()

    def execute(self, access: AccessContext) -> CatalogResult:
        return CatalogResult(project_id=access.project_id, templates=self.catalog.options)
