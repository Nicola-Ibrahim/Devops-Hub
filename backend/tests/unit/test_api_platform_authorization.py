"""API dispatch is blocked by the typed platform authorization boundary."""

import asyncio
from uuid import uuid4

import pytest

from api.platform.application_delivery.routes import applications
from api.platform.catalog.routes import catalog
from devops_platform.application.shared.dto import AccessContext
from devops_platform.application.shared.errors import CatalogForbidden, PlatformRequestError


class RecordingModule:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def query(self, message: object) -> object:
        self.calls.append(message)
        raise AssertionError("business module must not be called for a denied action")

    async def execute(self, message: object) -> object:
        self.calls.append(message)
        raise AssertionError("business module must not be called for a denied action")


@pytest.mark.parametrize("route", [catalog, applications])
def test_denied_platform_action_does_not_dispatch(route) -> None:
    access = AccessContext(
        user_id=uuid4(),
        project_id=uuid4(),
        role="developer",
        scopes=frozenset(),
    )
    module = RecordingModule()
    handler = route.__dishka_orig_func__

    async def invoke() -> None:
        with pytest.raises((CatalogForbidden, PlatformRequestError)):
            await handler(access, module)

    asyncio.run(invoke())
    assert module.calls == []
