"""PostgreSQL integration checks for atomic request acceptance and project scoping."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from test_foundation_postgres import async_engine_for

from devops_platform.application.database_provisioning.submit_database_request.command import (
    DatabaseRequest,
)
from devops_platform.application.projects.command import RegisterProjectCommand
from devops_platform.application.resource_catalog.models import PostgresOption, ResourceSize
from devops_platform.application.shared.dto import AccessContext
from devops_platform.application.shared.errors import PlatformRequestError
from devops_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from devops_platform.domain.value_objects.idempotency_key import IdempotencyKey
from devops_platform.domain.value_objects.resource_name import ResourceName
from devops_platform.domain.value_objects.resource_spec import ResourceSpec
from devops_platform.infra.persistence.ledger_projects import (
    SQLAlchemyProjectRegistrationRepository,
)
from devops_platform.infra.persistence.models import (
    IdempotencyRecord,
    Operation,
    ProjectRegistrationRow,
    QuotaBudget,
    Reservation,
    Resource,
    ResourceActivityRow,
)
from devops_platform.infra.persistence.resource_repository import SQLAlchemyResourceRepository
from identity.infra.persistence.models import InternalUserRow, ProjectRow, TeamRow

pytestmark = pytest.mark.postgres


def seed_identity(engine, *, user_id=None, project_id=None, team_id=None, project_name="demo"):
    user_id, project_id, team_id = user_id or uuid4(), project_id or uuid4(), team_id or uuid4()
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                InternalUserRow(id=user_id, name=f"user-{user_id}"),
                ProjectRow(id=project_id, name=project_name),
                TeamRow(id=team_id, name=f"team-{team_id}"),
            ]
        )
    return user_id, project_id, team_id


def access(user_id, project_id):
    return AccessContext(user_id, project_id, "developer", frozenset({"resources:write"}))


def command_for(project_id, environment_id, *, display_name="test-db"):
    return DatabaseRequest(
        project_id, environment_id, display_name, "postgres", "16", "local", "small", 3600
    )


def option(*, cpu=500, memory=512 * 1024 * 1024, storage=1024 * 1024 * 1024):
    return PostgresOption(
        requestable=True,
        unavailable_reason=None,
        size=ResourceSize("small", cpu, memory, storage),
    )


async def register(database, command, project_id, team_id):
    async with AsyncSession(database) as session, session.begin():
        return await SQLAlchemyProjectRegistrationRepository(session).register_project(
            command, project_id, team_id
        )


async def request(
    database, user_id, project_id, environment_id, *, key="same-key", digest="a" * 64
):
    now = datetime.now(UTC)
    selected = option()
    request = command_for(project_id, environment_id)
    lifecycle = ResourceLifecycle.request(
        resource_id=uuid4(),
        project_id=project_id,
        environment_id=environment_id,
        owner_id=user_id,
        installation_id=uuid4(),
        name=ResourceName(request.display_name),
        specification=ResourceSpec(
            request.template_id,
            request.version,
            request.target_id,
            selected.size.id,
            selected.size.cpu_millis,
            selected.size.memory_bytes,
            selected.size.storage_bytes,
            selected.max_lifetime_seconds,
            selected.size.storage_enforcement,
        ),
        now=now,
        ttl_seconds=request.ttl_seconds,
        max_lifetime_seconds=selected.max_lifetime_seconds,
    )
    async with AsyncSession(database) as session, session.begin():
        return await SQLAlchemyResourceRepository(session).accept_database_request(
            access(user_id, project_id), lifecycle, IdempotencyKey(key), digest
        )


def lifecycle_for(user_id, project_id, environment_id, now, ttl_seconds=3600):
    selected = option()
    request = command_for(project_id, environment_id)
    return ResourceLifecycle.request(
        resource_id=uuid4(),
        project_id=project_id,
        environment_id=environment_id,
        owner_id=user_id,
        installation_id=uuid4(),
        name=ResourceName(request.display_name),
        specification=ResourceSpec(
            request.template_id,
            request.version,
            request.target_id,
            selected.size.id,
            selected.size.cpu_millis,
            selected.size.memory_bytes,
            selected.size.storage_bytes,
            selected.max_lifetime_seconds,
            selected.size.storage_enforcement,
        ),
        now=now,
        ttl_seconds=ttl_seconds,
        max_lifetime_seconds=selected.max_lifetime_seconds,
    )


def test_registration_is_idempotent_configurable_and_creates_only_project_quota(postgres_engine):
    user_id, project_id, team_id = seed_identity(postgres_engine)
    database = async_engine_for(postgres_engine)
    registration = RegisterProjectCommand("demo", "platform", "org/demo", ("dev", "test"))
    try:
        first = asyncio.run(register(database, registration, project_id, team_id))
        second = asyncio.run(register(database, registration, project_id, team_id))
        assert first == second
        assert [environment.name for environment in first.environments] == ["dev", "test"]
        with pytest.raises(PlatformRequestError) as conflict:
            asyncio.run(
                register(
                    database,
                    RegisterProjectCommand("demo", "platform", "org/other", ("dev",)),
                    project_id,
                    team_id,
                )
            )
        assert conflict.value.status == 409
        with Session(postgres_engine) as session:
            budget = session.get(QuotaBudget, ("project", str(project_id)))
            assert (budget.max_resources, budget.max_cpu_millis) == (3, 2000)
            assert session.get(QuotaBudget, ("target", "local")) is None
    finally:
        asyncio.run(database.dispose())


def test_legacy_registration_can_be_configured_once(postgres_engine):
    _user_id, project_id, team_id = seed_identity(postgres_engine)
    with Session(postgres_engine) as session, session.begin():
        session.add(
            ProjectRegistrationRow(
                project_id=project_id,
                name="demo",
                owning_team_id=None,
                owning_team_name=None,
                repository=None,
                configured=False,
            )
        )
    database = async_engine_for(postgres_engine)
    try:
        result = asyncio.run(
            register(
                database,
                RegisterProjectCommand("demo", "platform", "org/demo", ("dev",)),
                project_id,
                team_id,
            )
        )
        assert result.configured and result.repository == "org/demo"
    finally:
        asyncio.run(database.dispose())


def test_duplicate_requests_replay_and_concurrent_duplicates_allocate_once(postgres_engine):
    user_id, project_id, team_id = seed_identity(postgres_engine)
    with Session(postgres_engine) as session, session.begin():
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=10,
                max_cpu_millis=10000,
                max_memory_bytes=2**40,
                max_storage_bytes=2**40,
            )
        )
    database = async_engine_for(postgres_engine)
    try:
        registration = asyncio.run(
            register(
                database,
                RegisterProjectCommand("demo", "platform", "org/demo", ("dev",)),
                project_id,
                team_id,
            )
        )
        environment_id = registration.environments[0].id

        async def concurrent():
            return await asyncio.gather(
                request(database, user_id, project_id, environment_id),
                request(database, user_id, project_id, environment_id),
            )

        first, second = asyncio.run(concurrent())
        assert first == second
        with Session(postgres_engine) as session:
            assert session.scalar(select(func.count()).select_from(Resource)) == 1
            assert session.scalar(select(func.count()).select_from(Operation)) == 1
            assert session.scalar(select(func.count()).select_from(Reservation)) == 1
            assert session.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1
            assert session.scalar(select(func.count()).select_from(ResourceActivityRow)) == 1
        with pytest.raises(PlatformRequestError) as conflict:
            asyncio.run(request(database, user_id, project_id, environment_id, digest="b" * 64))
        assert conflict.value.code == "idempotency_conflict"

        async def replay_after_acceptance():
            async with AsyncSession(database) as session:
                repository = SQLAlchemyResourceRepository(session)
                return await repository.replay_request(
                    access(user_id, project_id), IdempotencyKey("same-key"), "a" * 64
                )

        assert asyncio.run(replay_after_acceptance()) == first
    finally:
        asyncio.run(database.dispose())


def test_quota_boundary_counts_unreleased_reservations_and_scopes_reads(postgres_engine):
    user_id, project_id, team_id = seed_identity(postgres_engine)
    _other_user, other_project_id, other_team_id = seed_identity(
        postgres_engine, project_name="other"
    )
    with Session(postgres_engine) as session, session.begin():
        for project in (project_id, other_project_id):
            session.add(
                QuotaBudget(
                    scope="project",
                    scope_id=str(project),
                    max_resources=1,
                    max_cpu_millis=500,
                    max_memory_bytes=512 * 1024 * 1024,
                    max_storage_bytes=2**30,
                )
            )
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=1,
                max_cpu_millis=10000,
                max_memory_bytes=2**40,
                max_storage_bytes=2**40,
            )
        )
    database = async_engine_for(postgres_engine)
    try:
        registrations = [
            asyncio.run(
                register(
                    database,
                    RegisterProjectCommand(name, "platform", f"org/{name}", ("dev",)),
                    project,
                    team,
                )
            )
            for name, project, team in (
                ("demo", project_id, team_id),
                ("other", other_project_id, other_team_id),
            )
        ]
        accepted = asyncio.run(
            request(database, user_id, project_id, registrations[0].environments[0].id)
        )
        with pytest.raises(PlatformRequestError) as over:
            asyncio.run(
                request(
                    database,
                    user_id,
                    project_id,
                    registrations[0].environments[0].id,
                    key="second",
                )
            )
        assert over.value.code == "quota_exceeded"
        with pytest.raises(PlatformRequestError) as target_over:
            asyncio.run(
                request(
                    database,
                    user_id,
                    other_project_id,
                    registrations[1].environments[0].id,
                    key="other-project",
                )
            )
        assert target_over.value.code == "quota_exceeded"

        async def assert_project_scoping():
            async with AsyncSession(database) as session:
                repository = SQLAlchemyResourceRepository(session)
                assert (
                    await repository.find_resource(other_project_id, accepted.resource_id) is None
                )
                assert (
                    await repository.find_operation(other_project_id, accepted.operation_id) is None
                )
                assert await repository.list_resources(other_project_id, None, 20) == ()

        asyncio.run(assert_project_scoping())
    finally:
        asyncio.run(database.dispose())


def test_concurrent_distinct_keys_respect_project_quota(postgres_engine):
    user_id, project_id, team_id = seed_identity(postgres_engine)
    with Session(postgres_engine) as session, session.begin():
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=10,
                max_cpu_millis=10000,
                max_memory_bytes=2**40,
                max_storage_bytes=2**40,
            )
        )
    database = async_engine_for(postgres_engine)
    try:
        registration = asyncio.run(
            register(
                database,
                RegisterProjectCommand("demo", "platform", "org/demo", ("dev",)),
                project_id,
                team_id,
            )
        )
        with Session(postgres_engine) as session, session.begin():
            budget = session.get(QuotaBudget, ("project", str(project_id)))
            budget.max_resources = 1

        async def concurrent():
            return await asyncio.gather(
                request(
                    database,
                    user_id,
                    project_id,
                    registration.environments[0].id,
                    key="project-capacity-a",
                    digest="a" * 64,
                ),
                request(
                    database,
                    user_id,
                    project_id,
                    registration.environments[0].id,
                    key="project-capacity-b",
                    digest="b" * 64,
                ),
                return_exceptions=True,
            )

        outcomes = asyncio.run(concurrent())
        accepted = [result for result in outcomes if not isinstance(result, Exception)]
        rejected = [result for result in outcomes if isinstance(result, PlatformRequestError)]
        assert len(accepted) == len(rejected) == 1
        assert rejected[0].code == "quota_exceeded"
        with Session(postgres_engine) as session:
            for model in (Resource, Operation, Reservation):
                assert session.scalar(select(func.count()).select_from(model)) == 1
    finally:
        asyncio.run(database.dispose())


def test_concurrent_projects_respect_shared_target_quota(postgres_engine):
    first_user, first_project, first_team = seed_identity(postgres_engine)
    second_user, second_project, second_team = seed_identity(postgres_engine, project_name="other")
    with Session(postgres_engine) as session, session.begin():
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=1,
                max_cpu_millis=10000,
                max_memory_bytes=2**40,
                max_storage_bytes=2**40,
            )
        )
    database = async_engine_for(postgres_engine)
    try:
        registrations = [
            asyncio.run(
                register(
                    database,
                    RegisterProjectCommand(name, "platform", f"org/{name}", ("dev",)),
                    project,
                    team,
                )
            )
            for name, project, team in (
                ("demo", first_project, first_team),
                ("other", second_project, second_team),
            )
        ]

        async def concurrent():
            return await asyncio.gather(
                request(
                    database,
                    first_user,
                    first_project,
                    registrations[0].environments[0].id,
                    key="target-capacity-a",
                    digest="a" * 64,
                ),
                request(
                    database,
                    second_user,
                    second_project,
                    registrations[1].environments[0].id,
                    key="target-capacity-b",
                    digest="b" * 64,
                ),
                return_exceptions=True,
            )

        outcomes = asyncio.run(concurrent())
        accepted = [result for result in outcomes if not isinstance(result, Exception)]
        rejected = [result for result in outcomes if isinstance(result, PlatformRequestError)]
        assert len(accepted) == len(rejected) == 1
        assert rejected[0].code == "quota_exceeded"
        with Session(postgres_engine) as session:
            for model in (Resource, Operation, Reservation):
                assert session.scalar(select(func.count()).select_from(model)) == 1
    finally:
        asyncio.run(database.dispose())


def test_lease_starts_after_quota_lock_wait(postgres_engine):
    user_id, project_id, team_id = seed_identity(postgres_engine)
    with Session(postgres_engine) as session, session.begin():
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=10,
                max_cpu_millis=10000,
                max_memory_bytes=2**40,
                max_storage_bytes=2**40,
            )
        )
    database = async_engine_for(postgres_engine)
    try:
        registration = asyncio.run(
            register(
                database,
                RegisterProjectCommand("demo", "platform", "org/demo", ("dev",)),
                project_id,
                team_id,
            )
        )
        environment_id = registration.environments[0].id
        app_name = "ledger-lease-lock-test"

        async def submit_after_lock_wait():
            async with AsyncSession(database) as lock_holder:
                async with lock_holder.begin():
                    accepted_at = await lock_holder.scalar(select(func.clock_timestamp()))
                    assert accepted_at is not None
                    old_expiry = accepted_at + timedelta(seconds=1)
                    for scope, scope_id in sorted(
                        (("project", str(project_id)), ("target", "local"))
                    ):
                        await lock_holder.scalar(
                            select(QuotaBudget)
                            .where(
                                QuotaBudget.scope == scope,
                                QuotaBudget.scope_id == scope_id,
                            )
                            .with_for_update()
                        )

                    async def accept_blocked_request():
                        async with (
                            AsyncSession(database) as request_session,
                            request_session.begin(),
                        ):
                            await request_session.execute(
                                text(f"SET application_name = '{app_name}'")
                            )
                            return await SQLAlchemyResourceRepository(
                                request_session
                            ).accept_database_request(
                                access(user_id, project_id),
                                lifecycle_for(user_id, project_id, environment_id, accepted_at, 1),
                                IdempotencyKey("lease-after-lock"),
                                "e" * 64,
                            )

                    request_task = asyncio.create_task(accept_blocked_request())
                    try:
                        async with asyncio.timeout(5):
                            while True:
                                await lock_holder.execute(text("SELECT pg_stat_clear_snapshot()"))
                                waiting = await lock_holder.scalar(
                                    text(
                                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                        "WHERE application_name = :app_name "
                                        "AND wait_event_type = 'Lock')"
                                    ),
                                    {"app_name": app_name},
                                )
                                if waiting:
                                    break
                                await asyncio.sleep(0.01)
                            while (
                                await lock_holder.scalar(select(func.clock_timestamp()))
                                < old_expiry
                            ):
                                await asyncio.sleep(0.01)
                    except BaseException:
                        request_task.cancel()
                        await asyncio.gather(request_task, return_exceptions=True)
                        raise
                return await request_task, old_expiry

        accepted, previous_expiry = asyncio.run(submit_after_lock_wait())
        with Session(postgres_engine) as session:
            resource = session.get(Resource, accepted.resource_id)
            assert resource.created_at >= previous_expiry
            assert resource.expires_at - resource.created_at == timedelta(seconds=1)
    finally:
        asyncio.run(database.dispose())


def test_acceptance_rolls_back_all_ledger_rows_with_outer_transaction(postgres_engine):
    user_id, project_id, team_id = seed_identity(postgres_engine)
    with Session(postgres_engine) as session, session.begin():
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=10,
                max_cpu_millis=10000,
                max_memory_bytes=2**40,
                max_storage_bytes=2**40,
            )
        )
    database = async_engine_for(postgres_engine)
    try:
        registration = asyncio.run(
            register(
                database,
                RegisterProjectCommand("demo", "platform", "org/demo", ("dev",)),
                project_id,
                team_id,
            )
        )

        async def rolled_back():
            async with AsyncSession(database) as session:
                async with session.begin():
                    await SQLAlchemyResourceRepository(session).accept_database_request(
                        access(user_id, project_id),
                        lifecycle_for(
                            user_id,
                            project_id,
                            registration.environments[0].id,
                            datetime.now(UTC),
                        ),
                        IdempotencyKey("rolled-back"),
                        "c" * 64,
                    )
                    raise RuntimeError("force caller rollback")

        with pytest.raises(RuntimeError):
            asyncio.run(rolled_back())
        with Session(postgres_engine) as session:
            for model in (Resource, Operation, Reservation, IdempotencyRecord, ResourceActivityRow):
                assert session.scalar(select(func.count()).select_from(model)) == 0
    finally:
        asyncio.run(database.dispose())


def test_request_requires_registered_environment_and_target_quota(postgres_engine):
    user_id, project_id, team_id = seed_identity(postgres_engine)
    database = async_engine_for(postgres_engine)
    try:
        registration = asyncio.run(
            register(
                database,
                RegisterProjectCommand("demo", "platform", "org/demo", ("dev",)),
                project_id,
                team_id,
            )
        )
        now = datetime.now(UTC)
        with pytest.raises(PlatformRequestError) as missing_target:
            asyncio.run(request(database, user_id, project_id, registration.environments[0].id))
        assert missing_target.value.code == "quota_unconfigured"
        with Session(postgres_engine) as session, session.begin():
            session.add(
                QuotaBudget(
                    scope="target",
                    scope_id="local",
                    max_resources=10,
                    max_cpu_millis=10000,
                    max_memory_bytes=2**40,
                    max_storage_bytes=2**40,
                )
            )
        with pytest.raises(PlatformRequestError) as wrong_environment:

            async def invalid_environment():
                async with AsyncSession(database) as session, session.begin():
                    await SQLAlchemyResourceRepository(session).accept_database_request(
                        access(user_id, project_id),
                        lifecycle_for(user_id, project_id, uuid4(), now),
                        IdempotencyKey("invalid-env"),
                        "d" * 64,
                    )

            asyncio.run(invalid_environment())
        assert wrong_environment.value.status == 404
    finally:
        asyncio.run(database.dispose())
