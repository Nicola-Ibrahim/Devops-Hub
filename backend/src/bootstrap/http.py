from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from api.app import create_api
from bootstrap.composition import build_services
from bootstrap.settings import Settings
from shared.infra.persistence.database import create_database_engine


def create_app(settings: Settings | None = None, *, engine: Engine | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()  # type: ignore[call-arg]
    owns_engine = engine is None
    database = (
        engine
        if engine is not None
        else create_database_engine(
            config.database_url.get_secret_value(), config.database_connect_timeout
        )
    )
    services = build_services(config, database)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            # An injected engine is owned by its caller (e.g. the isolated test fixture).
            if owns_engine:
                database.dispose()

    return create_api(services.api, lifespan=lifespan)
