"""Application process lifecycle for the backend dependency graph."""

from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from composition.container import BackendContainer
from shared.infra.settings import Settings


class BackendRuntime:
    """Own the API container when created here; injected containers remain caller-owned."""

    def __init__(
        self,
        settings: Settings | None,
        *,
        engine: AsyncEngine | None = None,
        container: AsyncContainer | None = None,
    ) -> None:
        self.container = (
            container
            or BackendContainer(
                settings if settings is not None else Settings(),  # type: ignore[call-arg]
                engine=engine,
            ).api()
        )
        self._owns_container = container is None

    async def start(self) -> None:
        """Initialize owned backend resources without connecting or applying migrations."""
        if self._owns_container:
            # Creating an AsyncEngine is lazy: it builds the pool configuration but
            # does not open a database connection. The provider owns its shutdown.
            await self.container.get(AsyncEngine)

    async def close(self) -> None:
        if self._owns_container:
            await self.container.close()
