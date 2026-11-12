"""Outer transaction boundary and durable worker for application delivery."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from developer_platform.application.shared.errors import PlatformRequestError
from developer_platform.application.workload_delivery.execute_delivery_step.handler import (
    ExecuteDeliveryStepHandler,
)
from developer_platform.application.workload_delivery.shared.models import (
    DeliveryClaim,
    DeliveryResult,
)
from developer_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    ApplicationDeployer,
    ApprovedImageCatalog,
    RepositoryProvisioner,
    ResourceProvisioner,
    TemplateCatalog,
)
from developer_platform.infra.persistence.delivery import SQLAlchemyApplicationDeliveryRepository
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork

T = TypeVar("T")
R = TypeVar("R")
Clock = Callable[[], datetime]


class ApplicationDeliveryHost:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
        templates: TemplateCatalog,
        images: ApprovedImageCatalog,
        repositories: RepositoryProvisioner | None = None,
        resources: ResourceProvisioner | None = None,
        deployer: ApplicationDeployer | None = None,
        *,
        effect_guard: Callable[[UUID], AbstractAsyncContextManager[bool]],
    ) -> None:
        self.effect_guard = effect_guard
        self.sessions = sessions
        self.clock = clock
        self.template_catalog = templates
        self.images = images
        self.repositories = repositories
        self.resources = resources
        self.deployer = deployer

    async def tick(self) -> bool:
        now = self.clock()
        claim = await self._worker_transaction(
            lambda repo: self._claim(repo, now), lambda result: result
        )
        if claim is None:
            return False
        heartbeat = asyncio.create_task(self._heartbeat(claim))
        try:
            async with self.effect_guard(claim.application_id) as acquired:
                if not acquired:
                    await self._record_failure(claim, "application_busy", True)
                    return True
                current = await self._worker_transaction(
                    lambda repo: repo.effect_is_current(claim, self.clock()), bool
                )
                if not current:
                    return True
                # Keep ownership through completion writes, so another deployment
                # cannot remove this effect while its result is still uncertain.
                await self._execute_and_complete(claim)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        return True

    async def _execute_and_complete(self, claim: DeliveryClaim) -> None:
        try:
            result = await self._effect_executor().execute(claim)
        except ApplicationDeliveryFailure as error:
            await self._record_failure(claim, error.code, error.retryable)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._record_failure(claim, "delivery_provider_failure", True)
        else:
            await self._record_success(claim, result)

    async def _claim(
        self, repository: SQLAlchemyApplicationDeliveryRepository, now: datetime
    ) -> DeliveryClaim | None:
        await repository.expire_previews(now, 100)
        return await repository.claim_step(now, 30)

    async def _heartbeat(self, claim: DeliveryClaim) -> None:
        while True:
            await asyncio.sleep(8)
            alive = await self._worker_transaction(
                lambda repo: repo.heartbeat_step(claim, self.clock(), 30), bool
            )
            if not alive:
                return

    async def _record_success(self, claim: DeliveryClaim, result: DeliveryResult) -> None:
        await self._worker_transaction(
            lambda repo: repo.complete_step(claim, result, self.clock()), bool
        )

    async def _record_failure(self, claim: DeliveryClaim, code: str, retryable: bool) -> None:
        backoff = min(300, 2 ** min(claim.attempts, 8))
        await self._worker_transaction(
            lambda repo: repo.fail_step(claim, code, self.clock(), backoff, retryable),
            bool,
        )

    async def _worker_transaction(
        self,
        action: Callable[[SQLAlchemyApplicationDeliveryRepository], Awaitable[T]],
        present: Callable[[T], R],
    ) -> R:
        try:
            async with self.sessions() as session:
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                return await SqlAlchemyUnitOfWork(session).run(lambda: action(repository), present)
        except DatabaseUnavailable as error:
            raise PlatformRequestError(
                "delivery_unavailable", "Application delivery database is unavailable", 503
            ) from error

    def _effect_executor(self) -> ExecuteDeliveryStepHandler:
        return ExecuteDeliveryStepHandler(
            self.template_catalog,
            self.images,
            self.repositories,
            self.resources,
            self.deployer,
        )


async def run_application_worker(
    service: ApplicationDeliveryHost, *, once: bool = False, poll_seconds: float = 1
) -> None:
    while True:
        worked = await service.tick()
        if once:
            return
        if not worked:
            await asyncio.sleep(poll_seconds)
