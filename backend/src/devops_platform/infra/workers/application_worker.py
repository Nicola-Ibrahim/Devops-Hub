"""Application delivery worker process; provider effects are adapter-gated."""

import argparse
import asyncio

from composition.container import BackendContainer
from devops_platform.infra.workers.application_host import (
    ApplicationDeliveryHost,
    run_application_worker,
)
from shared.infra.persistence.database import create_async_database_engine
from shared.infra.readiness import SqlAlchemyReadinessProbe
from shared.infra.settings import SCHEMA_REVISION, Settings


async def run(config: Settings, once: bool = False) -> None:
    engine = create_async_database_engine(
        config.database_url.get_secret_value(), config.database_connect_timeout
    )
    container = BackendContainer(config, engine=engine).worker()
    try:
        if await SqlAlchemyReadinessProbe(engine, SCHEMA_REVISION).inspect() != "ready":
            raise ValueError("Application delivery schema is not ready")
        async with container() as scope:
            service = await scope.get(ApplicationDeliveryHost)
            await run_application_worker(service, once=once)
    finally:
        await container.close()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Durable application delivery worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(Settings(), args.once))  # type: ignore[call-arg]
    except KeyboardInterrupt:
        pass
    except Exception:
        raise SystemExit(
            "Application worker failed. Check private configuration and schema readiness."
        ) from None


if __name__ == "__main__":
    main()
