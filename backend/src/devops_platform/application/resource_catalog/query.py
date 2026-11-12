from dataclasses import dataclass

from devops_platform.application.shared.dto import AccessContext, CatalogResult
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class ReadCatalog(Query[CatalogResult]):
    access: AccessContext
