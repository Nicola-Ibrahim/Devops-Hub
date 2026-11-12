"""Platform application handlers leave coarse permission checks to their hosts."""

import asyncio
from uuid import uuid4

from devops_hub.platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from devops_hub.platform.application.resource_catalog.query import ReadCatalog
from devops_hub.platform.application.shared.dto import AccessContext


def test_catalog_handler_returns_catalog_without_rechecking_transport_scope() -> None:
    access = AccessContext(
        user_id=uuid4(),
        project_id=uuid4(),
        role="developer",
        scopes=frozenset(),
    )

    result = asyncio.run(ReadCatalogQueryHandler().execute(ReadCatalog(access)))

    assert result.project_id == access.project_id
    assert result.templates
