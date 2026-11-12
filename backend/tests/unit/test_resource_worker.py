"""Worker orchestration checks with isolated queue/provider fakes."""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from devops_platform.application.resource_lifecycle.ports import (
    DatabaseCredentials,
    DatabaseEndpoint,
    DeletionObservation,
    ProviderFailure,
    ProvisioningJob,
)
from devops_platform.application.resource_worker.handler import ResourceWorkerHandler


def job(action: str = "provision") -> ProvisioningJob:
    return ProvisioningJob(
        operation_id=uuid4(),
        resource_id=uuid4(),
        installation_id=uuid4(),
        generation=1,
        claim_token=uuid4(),
        action=action,
        cpu_millis=500,
        memory_bytes=512 * 1024 * 1024,
        credentials=DatabaseCredentials("user", "database", "secret", "admin-secret"),
    )


class Queue:
    def __init__(self, claimed: ProvisioningJob | None) -> None:
        self.claimed = claimed
        self.calls: list[tuple] = []

    async def sweep(self) -> None:
        self.calls.append(("sweep",))

    async def claim(self) -> ProvisioningJob | None:
        self.calls.append(("claim",))
        return self.claimed

    async def heartbeat(self, claimed: ProvisioningJob) -> bool:
        self.calls.append(("heartbeat", claimed))
        return True

    async def should_execute(self, claimed: ProvisioningJob) -> bool:
        self.calls.append(("should_execute", claimed))
        return True

    async def ready(self, claimed: ProvisioningJob, endpoint: DatabaseEndpoint) -> None:
        self.calls.append(("ready", claimed, endpoint))

    async def deleted(self, claimed: ProvisioningJob, observation: DeletionObservation) -> None:
        self.calls.append(("deleted", claimed, observation))

    async def failed(self, claimed: ProvisioningJob, error: ProviderFailure) -> None:
        self.calls.append(("failed", claimed, error))


class Provider:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.endpoint = DatabaseEndpoint("127.0.0.1", 54321)
        self.observation = DeletionObservation(absent=True, observed_owned_object=True)
        self.error: ProviderFailure | None = None

    async def provision(self, claimed: ProvisioningJob) -> DatabaseEndpoint:
        self.calls.append(("provision", claimed))
        if self.error:
            raise self.error
        return self.endpoint

    async def inspect(self, claimed: ProvisioningJob) -> DatabaseEndpoint | None:
        self.calls.append(("inspect", claimed))
        return self.endpoint

    async def delete(self, claimed: ProvisioningJob) -> DeletionObservation:
        self.calls.append(("delete", claimed))
        return self.observation

    async def discover(self, installation_id):
        self.calls.append(("discover", installation_id))
        return ()


def allow_guard():
    @asynccontextmanager
    async def guard(_resource_id):
        yield True

    return guard


def test_tick_sweeps_and_provisions_only_after_claim_and_fence():
    claimed = job()
    queue = Queue(claimed)
    provider = Provider()

    assert asyncio.run(ResourceWorkerHandler(queue, provider, allow_guard()).tick())
    assert [call[0] for call in queue.calls] == [
        "sweep",
        "claim",
        "should_execute",
        "ready",
    ]
    assert [call[0] for call in provider.calls] == ["provision"]
    assert queue.calls[-1][2] == provider.endpoint


def test_reconcile_is_observational_and_delete_records_provider_observation():
    reconcile = job("reconcile")
    queue = Queue(reconcile)
    provider = Provider()
    worker = ResourceWorkerHandler(queue, provider, allow_guard())

    assert asyncio.run(worker.tick())
    assert [call[0] for call in provider.calls] == ["inspect"]
    assert queue.calls[-1][0] == "ready"

    deletion = job("delete")
    queue = Queue(deletion)
    provider = Provider()
    assert asyncio.run(ResourceWorkerHandler(queue, provider, allow_guard()).tick())
    assert [call[0] for call in provider.calls] == ["delete"]
    assert queue.calls[-1] == ("deleted", deletion, provider.observation)


def test_busy_guard_and_provider_errors_are_persisted_without_leaking_details():
    claimed = job()
    queue = Queue(claimed)
    provider = Provider()

    @asynccontextmanager
    async def busy_guard(_resource_id):
        yield False

    assert asyncio.run(ResourceWorkerHandler(queue, provider, busy_guard).tick())
    assert provider.calls == []
    failed = queue.calls[-1]
    assert failed[0] == "failed"
    assert failed[2].code == "resource_busy"
    assert failed[2].uncertain is True

    queue = Queue(claimed)
    provider = Provider()
    provider.error = ProviderFailure("sanitized", uncertain=True)
    assert asyncio.run(ResourceWorkerHandler(queue, provider, allow_guard()).tick())
    assert queue.calls[-1][0] == "failed"
    assert queue.calls[-1][2].code == "sanitized"


def test_empty_queue_still_sweeps_and_does_not_start_provider():
    queue = Queue(None)
    provider = Provider()
    assert not asyncio.run(ResourceWorkerHandler(queue, provider, allow_guard()).tick())
    assert [call[0] for call in queue.calls] == ["sweep", "claim"]
    assert provider.calls == []
