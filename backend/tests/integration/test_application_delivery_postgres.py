"""Durable application idempotency and worker-claim recovery tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from test_foundation_postgres import async_engine_for

from developer_platform.application.delivery import ApplicationCommand
from developer_platform.application.dto import AccessContext
from developer_platform.infra.persistence.delivery import (
    ApplicationDeliveryIdempotencyRow,
    ApplicationDeliveryStepRow,
    ApplicationRow,
    SQLAlchemyApplicationDeliveryRepository,
)
from developer_platform.infra.persistence.models import (
    ProjectEnvironmentRow,
    ProjectRegistrationRow,
)
from identity.infra.persistence.models import InternalUserRow, ProjectRow, TeamRow

pytestmark = pytest.mark.postgres


def test_duplicate_creation_and_expired_worker_claim_recover(postgres_engine) -> None:
    user_id, project_id, team_id, environment_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    project_name = f"delivery-{project_id}"
    with Session(postgres_engine) as session, session.begin():
        session.add_all(
            [
                InternalUserRow(id=user_id, name=f"delivery-user-{user_id}"),
                ProjectRow(id=project_id, name=project_name),
                TeamRow(id=team_id, name=f"delivery-team-{team_id}"),
            ]
        )
        session.flush()
        session.add(
            ProjectRegistrationRow(
                project_id=project_id,
                name=project_name,
                owning_team_id=team_id,
                owning_team_name="delivery-test",
                repository="company/delivery-test",
                configured=True,
            )
        )
        session.flush()
        session.add(ProjectEnvironmentRow(id=environment_id, project_id=project_id, name="dev"))

    async def exercise() -> None:
        engine = async_engine_for(postgres_engine)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            access = AccessContext(user_id, project_id, "developer", frozenset({"resources:write"}))
            command = ApplicationCommand(environment_id, "delivery-demo", "python-fastapi", "1.0.0")
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                first, replayed_first = await repository.create_application(
                    access, command, "create-key", "request-hash", now
                )
                assert not replayed_first
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                second, replayed_second = await repository.create_application(
                    access, command, "create-key", "request-hash", now + timedelta(seconds=1)
                )
                assert replayed_second
                assert second.id == first.id
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                first_claim = await repository.claim_step(now, lease_seconds=15)
                assert first_claim is not None
                assert first_claim.application_id == first.id
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                recovered = await repository.claim_step(now + timedelta(seconds=16), 15)
                assert recovered is not None
                assert recovered.step_id == first_claim.step_id
                assert recovered.claim_token != first_claim.claim_token
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                assert not await repository.effect_is_current(
                    first_claim, now + timedelta(seconds=16)
                )
                assert await repository.effect_is_current(recovered, now + timedelta(seconds=16))
            async with sessions() as session:
                assert await session.scalar(select(func.count()).select_from(ApplicationRow)) == 1
                assert (
                    await session.scalar(
                        select(func.count()).select_from(ApplicationDeliveryIdempotencyRow)
                    )
                    == 1
                )
                step = await session.get(ApplicationDeliveryStepRow, first_claim.step_id)
                assert step is not None and step.attempts == 2
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_preview_close_waits_for_claimed_resource_and_carries_late_resource_id(
    postgres_engine,
) -> None:
    from developer_platform.application.delivery import DeliveryResult
    from developer_platform.infra.persistence.models import Resource

    user_id, project_id, team_id, environment_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    project_name = f"preview-{project_id}"
    with Session(postgres_engine) as session, session.begin():
        session.add_all(
            [
                InternalUserRow(id=user_id, name=f"preview-user-{user_id}"),
                ProjectRow(id=project_id, name=project_name),
                TeamRow(id=team_id, name=f"preview-team-{team_id}"),
            ]
        )
        session.flush()
        session.add(
            ProjectRegistrationRow(
                project_id=project_id,
                name=project_name,
                owning_team_id=team_id,
                owning_team_name="preview-test",
                repository="company/preview-test",
                configured=True,
            )
        )
        session.flush()
        session.add(ProjectEnvironmentRow(id=environment_id, project_id=project_id, name="dev"))

    async def exercise() -> None:
        engine = async_engine_for(postgres_engine)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        app_id, resource_id = uuid4(), uuid4()
        resource_claim = None
        cleanup_claim = None
        try:
            access = AccessContext(user_id, project_id, "developer", frozenset({"resources:write"}))
            command = ApplicationCommand(environment_id, "preview-demo", "python-fastapi", "1.0.0")
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                app, _ = await repository.create_application(
                    access, command, "preview-create", "preview-hash", now
                )
                app_id = app.id
                app_row = await session.get(ApplicationRow, app_id)
                assert app_row is not None
                app_row.is_preview = True
                app_row.source_repository = "company/preview-test"
                app_row.pull_request = 42
                app_row.expires_at = now + timedelta(hours=1)
                repository_step = await session.scalar(
                    select(ApplicationDeliveryStepRow).where(
                        ApplicationDeliveryStepRow.application_id == app_id,
                        ApplicationDeliveryStepRow.kind == "repository",
                    )
                )
                assert repository_step is not None
                repository_step.status = "succeeded"
                session.add(
                    Resource(
                        id=resource_id,
                        environment_id=environment_id,
                        owner_id=user_id,
                        project_id=project_id,
                        display_name="preview-db",
                        template_id="postgres",
                        target_id="local",
                        size_id="small",
                        configuration={},
                        work_reference=None,
                        desired_state="running",
                        status="pending",
                        revision=1,
                        generation=1,
                        installation_id=uuid4(),
                        provider_id="test-provider",
                        endpoint={"host": "127.0.0.1", "port": 54321},
                        created_at=now,
                        expires_at=now + timedelta(hours=1),
                    )
                )
                session.add(
                    ApplicationDeliveryStepRow(
                        id=uuid4(),
                        application_id=app_id,
                        kind="resource",
                        status="pending",
                        idempotency_key="preview-resource-effect",
                        request_payload={},
                        attempts=0,
                        next_attempt_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
            async with sessions() as session, session.begin():
                resource_claim = await SQLAlchemyApplicationDeliveryRepository(session).claim_step(
                    now, lease_seconds=30
                )
                assert resource_claim is not None and resource_claim.kind == "resource"
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                assert (
                    await repository.close_preview(
                        repository="company/preview-test", pull_request=42, now=now
                    )
                    == 1
                )
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                # A close webhook cannot queue cleanup while an external effect is active.
                assert await repository.claim_step(now + timedelta(seconds=1), 30) is None
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                assert await repository.complete_step(
                    resource_claim,
                    DeliveryResult(resource_id=resource_id),
                    now + timedelta(seconds=2),
                )
                app = await session.get(ApplicationRow, app_id)
                assert app is not None and app.status == "deleting"
                assert app.resource_id == resource_id
            async with sessions() as session, session.begin():
                cleanup_claim = await SQLAlchemyApplicationDeliveryRepository(session).claim_step(
                    now + timedelta(seconds=3), 30
                )
                assert cleanup_claim is not None and cleanup_claim.kind == "preview_cleanup"
                assert cleanup_claim.payload["resource_id"] == str(resource_id)

            # Cleanup remains retryable after the ordinary delivery retry limit and
            # close/expiry reuses the durable row instead of violating its unique key.
            for attempt in range(6):
                retry_at = now + timedelta(seconds=10 + attempt * 100)
                async with sessions() as session, session.begin():
                    repository = SQLAlchemyApplicationDeliveryRepository(session)
                    if attempt:
                        cleanup_claim = await repository.claim_step(retry_at, 30)
                        assert cleanup_claim is not None
                        assert cleanup_claim.kind == "preview_cleanup"
                    assert cleanup_claim is not None
                    assert await repository.fail_step(
                        cleanup_claim,
                        "cleanup_temporarily_unavailable",
                        retry_at,
                        retry_after_seconds=1,
                        retryable=False,
                    )
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                assert (
                    await repository.close_preview(
                        repository="company/preview-test", pull_request=42, now=now
                    )
                    == 1
                )
                cleanups = await session.scalars(
                    select(ApplicationDeliveryStepRow).where(
                        ApplicationDeliveryStepRow.application_id == app_id,
                        ApplicationDeliveryStepRow.kind == "preview_cleanup",
                    )
                )
                cleanup_rows = list(cleanups)
                assert len(cleanup_rows) == 1
                assert cleanup_rows[0].status == "pending"
                assert cleanup_rows[0].attempts == 6
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_preview_close_and_worker_claim_use_consistent_lock_order(postgres_engine) -> None:
    user_id, project_id, team_id, environment_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    project_name = f"preview-lock-{project_id}"
    with Session(postgres_engine) as session, session.begin():
        session.add_all(
            [
                InternalUserRow(id=user_id, name=f"preview-lock-user-{user_id}"),
                ProjectRow(id=project_id, name=project_name),
                TeamRow(id=team_id, name=f"preview-lock-team-{team_id}"),
            ]
        )
        session.flush()
        session.add(
            ProjectRegistrationRow(
                project_id=project_id,
                name=project_name,
                owning_team_id=team_id,
                owning_team_name="preview-lock-test",
                repository="company/preview-lock-test",
                configured=True,
            )
        )
        session.flush()
        session.add(ProjectEnvironmentRow(id=environment_id, project_id=project_id, name="dev"))

    async def exercise() -> None:
        engine = async_engine_for(postgres_engine)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            access = AccessContext(user_id, project_id, "developer", frozenset({"resources:write"}))
            command = ApplicationCommand(environment_id, "preview-lock", "python-fastapi", "1.0.0")
            async with sessions() as session, session.begin():
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                app, _ = await repository.create_application(
                    access, command, "preview-lock-create", "preview-lock-hash", now
                )
                app_id = app.id
                app_row = await session.get(ApplicationRow, app_id)
                assert app_row is not None
                app_row.is_preview = True
                app_row.source_repository = "company/preview-lock-test"
                app_row.pull_request = 43

            async def claim_worker_step() -> object:
                async with sessions() as session, session.begin():
                    repository = SQLAlchemyApplicationDeliveryRepository(session)
                    return await repository.claim_step(now, 30)

            async with sessions() as closing_session:
                async with closing_session.begin():
                    # Hold the application lock while a worker discovers its due
                    # step. The worker must wait for app -> step, matching close.
                    await closing_session.scalar(
                        select(ApplicationRow).where(ApplicationRow.id == app_id).with_for_update()
                    )
                    claim_task = asyncio.create_task(claim_worker_step())
                    await asyncio.sleep(0.1)
                    closed = await SQLAlchemyApplicationDeliveryRepository(
                        closing_session
                    ).close_preview(
                        repository="company/preview-lock-test", pull_request=43, now=now
                    )
                    assert closed == 1
                claim = await asyncio.wait_for(claim_task, timeout=5)

            assert claim is None
            async with sessions() as session:
                app_row = await session.get(ApplicationRow, app_id)
                assert app_row is not None and app_row.status == "deleting"
                steps = list(
                    await session.scalars(
                        select(ApplicationDeliveryStepRow).where(
                            ApplicationDeliveryStepRow.application_id == app_id,
                            ApplicationDeliveryStepRow.kind == "repository",
                        )
                    )
                )
                assert len(steps) == 1 and steps[0].status == "failed"
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_reopened_preview_reuses_cleanup_and_keeps_failed_deployment_removal_intent(
    postgres_engine,
):
    from test_resource_worker_postgres import seed_resource

    from developer_platform.infra.persistence.models import Resource

    _, resource_id, _, _ = seed_resource(postgres_engine)
    app_id, cleanup_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    with Session(postgres_engine) as session, session.begin():
        resource = session.get(Resource, resource_id)
        session.add(
            ApplicationRow(
                id=app_id,
                project_id=resource.project_id,
                environment_id=resource.environment_id,
                owner_id=resource.owner_id,
                name="reopened-preview",
                template_id="python-fastapi",
                template_version="1.0.0",
                status="deleting",
                is_preview=True,
                expires_at=now - timedelta(seconds=1),
            )
        )
        session.flush()
        session.add_all(
            [
                ApplicationDeliveryStepRow(
                    id=cleanup_id,
                    application_id=app_id,
                    kind="preview_cleanup",
                    status="succeeded",
                    attempts=1,
                    idempotency_key=f"application:{app_id}:preview-cleanup",
                ),
                ApplicationDeliveryStepRow(
                    application_id=app_id,
                    kind="deployment",
                    status="failed",
                    attempts=5,
                    idempotency_key="failed-deployment",
                    request_payload={},
                ),
            ]
        )
    database = async_engine_for(postgres_engine)

    async def exercise():
        sessions = async_sessionmaker(database, expire_on_commit=False)
        async with sessions() as session, session.begin():
            assert (
                await SQLAlchemyApplicationDeliveryRepository(session).expire_previews(now, 10) == 1
            )
        async with sessions() as session:
            cleanup = await session.get(ApplicationDeliveryStepRow, cleanup_id)
            assert cleanup.status == "pending"
            assert cleanup.request_payload["remove_deployments"] is True
        async with sessions() as session, session.begin():
            from developer_platform.application.errors import PlatformRequestError

            app = await session.get(ApplicationRow, app_id)
            failed = await session.scalar(
                select(ApplicationDeliveryStepRow).where(
                    ApplicationDeliveryStepRow.application_id == app_id,
                    ApplicationDeliveryStepRow.kind == "deployment",
                )
            )
            access = AccessContext(
                app.owner_id, app.project_id, "admin", frozenset({"resources:write"})
            )
            with pytest.raises(PlatformRequestError, match="cleanup"):
                await SQLAlchemyApplicationDeliveryRepository(session).retry_step(
                    access, app_id, failed.id, now
                )
            assert app.status == "deleting"
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ApplicationDeliveryStepRow)
                    .where(
                        ApplicationDeliveryStepRow.application_id == app_id,
                        ApplicationDeliveryStepRow.kind == "preview_cleanup",
                    )
                )
                == 1
            )

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())
