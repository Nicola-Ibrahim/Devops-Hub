"""Durable worker orchestration through queue/provider/guard interfaces."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from devops_hub.platform.application.database_lifecycle.ports import (
    LocalDatabaseProvider,
    ProviderFailure,
    ProvisioningJob,
    ProvisioningQueue,
)


class ResourceWorkerHandler:
    def __init__(
        self,
        queue: ProvisioningQueue,
        provider: LocalDatabaseProvider,
        guard: Callable[[UUID], AbstractAsyncContextManager[bool]],
    ) -> None:
        self.queue = queue
        self.provider = provider
        self.guard = guard

    async def _heartbeat(self, job: ProvisioningJob) -> None:
        while True:
            await asyncio.sleep(5)
            if not await self.queue.heartbeat(job):
                return

    async def tick(self) -> bool:
        await self.queue.sweep()
        job = await self.queue.claim()
        if job is None:
            return False
        pulse = asyncio.create_task(self._heartbeat(job))
        try:
            async with self.guard(job.resource_id) as acquired:
                if not acquired:
                    raise ProviderFailure("resource_busy", True)
                if not await self.queue.should_execute(job):
                    return True
                if job.action == "delete":
                    await self.queue.deleted(job, await self.provider.delete(job))
                else:
                    if job.action == "reconcile":
                        endpoint = await self.provider.inspect(job)
                        if endpoint is None:
                            raise ProviderFailure("resource_missing", False)
                    else:
                        endpoint = await self.provider.provision(job)
                    await self.queue.ready(job, endpoint)
        except ProviderFailure as error:
            await self.queue.failed(job, error)
        finally:
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)
        return True
