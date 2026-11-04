"""Competing application steps cannot race Docker replacement or completion."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from containers.application_operations import ApplicationDeliveryService
from developer_platform.application.delivery import DeliveryClaim, DeliveryResult


def test_application_effect_and_completion_keep_exclusive_ownership():
    async def exercise():
        application_id = uuid4()
        claims = [
            DeliveryClaim(
                uuid4(),
                application_id,
                uuid4(),
                uuid4(),
                uuid4(),
                "app",
                "python-fastapi",
                "1.0.0",
                "deployment",
                "key",
                uuid4(),
                1,
                {},
            )
            for _ in range(2)
        ]
        locked, effects_started, finish = False, asyncio.Event(), asyncio.Event()
        failures, completions = [], []

        @asynccontextmanager
        async def guard(_application_id):
            nonlocal locked
            if locked:
                yield False
            else:
                locked = True
                try:
                    yield True
                finally:
                    locked = False

        class Repository:
            async def expire_previews(self, *_args):
                return 0

            async def claim_step(self, *_args):
                return claims.pop(0)

            async def effect_is_current(self, *_args):
                assert locked
                return True

            async def fail_step(self, claim, code, *_args):
                failures.append(code)
                return True

            async def complete_step(self, claim, result, now):
                assert locked
                completions.append(claim.step_id)
                return True

        class UseCase:
            async def execute_claim(self, *_args):
                assert locked
                effects_started.set()
                await finish.wait()
                return DeliveryResult()

        class Service(ApplicationDeliveryService):
            async def _worker_transaction(self, action, present):
                return present(await action(Repository()))

            def _use_case(self, _repository):
                return UseCase()

        service = Service(
            None, lambda: datetime.now(UTC), None, None, None, None, effect_guard=guard
        )
        first = asyncio.create_task(service.tick())
        await asyncio.wait_for(effects_started.wait(), timeout=1)
        assert await service.tick()
        assert failures == ["application_busy"]
        assert not completions
        finish.set()
        assert await first
        assert len(completions) == 1
        assert not locked

    asyncio.run(exercise())
