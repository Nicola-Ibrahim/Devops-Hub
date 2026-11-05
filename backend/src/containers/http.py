from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from api.app import APIConfiguration, DevOpsHubAPI
from containers.factory import create_container
from shared.infra.settings import Settings


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    container: AsyncContainer | None = None,
    api_config: APIConfiguration | None = None,
) -> FastAPI:
    # An explicitly injected container/engine remains caller-owned.
    runtime = (
        container
        if container is not None
        else create_container(
            settings if settings is not None else Settings(),  # type: ignore[call-arg]
            engine=engine,
        )
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if container is None:
                await runtime.close()

    app = DevOpsHubAPI(api_config, lifespan=lifespan)
    setup_dishka(runtime, app)
    return app
