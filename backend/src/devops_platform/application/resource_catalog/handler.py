"""Catalog read workflow."""

from devops_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from devops_platform.application.resource_catalog.query import ReadCatalog
from devops_platform.application.shared.dto import CatalogResult


class ReadCatalogQueryHandler:
    def __init__(self, catalog: ApprovedPostgresCatalog | None = None) -> None:
        self.catalog = catalog if catalog is not None else ApprovedPostgresCatalog()

    async def execute(self, query: ReadCatalog) -> CatalogResult:
        return CatalogResult(project_id=query.access.project_id, templates=self.catalog.options)
