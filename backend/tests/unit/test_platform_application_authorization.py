"""Platform application handlers leave coarse permission checks to their hosts."""

from uuid import uuid4

from developer_platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from developer_platform.application.shared.dto import AccessContext


def test_catalog_handler_returns_catalog_without_rechecking_transport_scope() -> None:
    access = AccessContext(
        user_id=uuid4(),
        project_id=uuid4(),
        role="developer",
        scopes=frozenset(),
    )

    result = ReadCatalogQueryHandler().execute(access)

    assert result.project_id == access.project_id
    assert result.templates
