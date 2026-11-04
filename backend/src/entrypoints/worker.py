"""Resource worker process; no migrations or host provisioning at startup."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from containers.worker_queue import PostgresResourceEffectGuard, SqlAlchemyProvisioningQueue
from developer_platform.application.worker import ResourceWorker
from developer_platform.infra.credentials import FernetResourceCredentialCipher
from developer_platform.infra.docker_provider import DockerPostgresProvider
from entrypoints.schema import registered_metadata
from entrypoints.settings import Settings
from shared.infra.persistence.database import create_async_database_engine
from shared.infra.readiness import SqlAlchemyReadinessProbe


async def run_worker(config: Settings, once: bool = False) -> None:
    if (
        not config.local_provider_enabled
        or config.resource_key is None
        or config.installation_id is None
    ):
        raise ValueError(
            "Worker requires an enabled target, stable installation and credential key"
        )
    registered_metadata()
    engine = create_async_database_engine(
        config.database_url.get_secret_value(), config.database_connect_timeout
    )
    try:
        from entrypoints.settings import SCHEMA_REVISION

        if await SqlAlchemyReadinessProbe(engine, SCHEMA_REVISION).inspect() != "ready":
            raise ValueError("Worker schema is not ready")
        queue = SqlAlchemyProvisioningQueue(
            async_sessionmaker(engine, expire_on_commit=False),
            config.installation_id,
            FernetResourceCredentialCipher(
                config.resource_key.get_secret_value(), config.resource_key_id
            ),
            config.resource_key_id,
        )
        provider = DockerPostgresProvider(
            config.docker_url, config.postgres_image, config.advertised_host
        )
        worker = ResourceWorker(queue, provider, PostgresResourceEffectGuard(engine))
        last_reconcile = 0.0
        while True:
            try:
                loop = asyncio.get_running_loop()
                if loop.time() - last_reconcile >= 30:
                    await queue.reconcile(await provider.discover(config.installation_id))
                    last_reconcile = loop.time()
                worked = await worker.tick()
                if once:
                    return
                if not worked:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                print(
                    json.dumps(
                        {"event": "worker_operation_failed", "at": datetime.now(UTC).isoformat()}
                    ),
                    flush=True,
                )
                if once:
                    raise
                await asyncio.sleep(2)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Durable local resource worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run_worker(Settings(), args.once))  # type: ignore[call-arg]
    except KeyboardInterrupt:
        pass
    except Exception:
        raise SystemExit(
            "Worker failed. Check private configuration and schema readiness."
        ) from None


if __name__ == "__main__":
    main()
