"""HTTP composition across identity and developer platform capabilities."""

from dishka import AsyncContainer, Provider, Scope, provide
from fastapi import Request

from api.health.metrics import OperationalMetrics
from api.health.metrics_adapter import DatabaseOperationalMetrics
from api.platform.module import PlatformRequestModule
from api.settings.config import BrowserCookiePolicy
from devops_hub.platform.application.module import DeveloperPlatformModule
from shared.infra.clock import Clock
from shared.infra.settings import Settings


class ApiCompositionProvider(Provider):
    """Adapt context capabilities to HTTP contracts at the process boundary."""

    metrics = provide(DatabaseOperationalMetrics, provides=OperationalMetrics, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def browser_cookie_policy(self, settings: Settings) -> BrowserCookiePolicy:
        return BrowserCookiePolicy(secure=settings.cookie_secure)

    @provide(scope=Scope.REQUEST)
    def platform_module(
        self, container: AsyncContainer, request: Request, settings: Settings, clock: Clock
    ) -> DeveloperPlatformModule:
        return PlatformRequestModule(container, request, settings, clock)
