import hmac

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.errors import APIError
from developer_platform.infra.observability.metrics import render_metrics
from shared.infra.settings import Settings


class DatabaseOperationalMetrics:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self.sessions = sessions
        self.settings = settings

    async def render(self, authorization: str | None, client_host: str) -> str:
        if self.settings.metrics_token is not None:
            expected = "Bearer " + self.settings.metrics_token.get_secret_value()
            if authorization is None or not hmac.compare_digest(authorization, expected):
                raise APIError(
                    401, "metrics_authentication_required", "Metrics authentication required"
                )
        elif self.settings.environment == "server" or client_host not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            raise APIError(403, "metrics_forbidden", "Metrics are private")
        async with self.sessions() as session:
            return await render_metrics(session)
