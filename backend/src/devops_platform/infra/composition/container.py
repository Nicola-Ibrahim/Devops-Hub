"""Developer Platform-owned registrations for API and worker processes."""

from dishka import Provider

from devops_platform.infra.composition.providers_delivery import ApplicationDeliveryProvider
from devops_platform.infra.composition.providers_platform import PlatformProvider
from devops_platform.infra.composition.providers_worker import ApplicationWorkerProvider


class DeveloperPlatformContainer:
    """Keep Platform DI registrations with the bounded context that owns them."""

    def providers(self) -> tuple[Provider, ...]:
        return PlatformProvider(), ApplicationDeliveryProvider()

    def worker_providers(self) -> tuple[Provider, ...]:
        return (ApplicationWorkerProvider(),)
