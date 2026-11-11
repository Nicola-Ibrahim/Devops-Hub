"""Real PostgreSQL verification for durable browser authentication and recovery."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from test_foundation_postgres import async_engine_for

from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.errors import IdentityValidationError
from identity.infra.browser_operations import BrowserIdentityService
from identity.infra.browser_security import ScryptPasswordHasher
from identity.infra.persistence.browser_identity import SQLAlchemyBrowserIdentityRepository
from identity.infra.persistence.models import (
    BrowserLoginThrottleRow,
    BrowserSessionRow,
    IdentityActivityRow,
    InternalUserRow,
    ProjectMembershipRow,
    ProjectRow,
)

pytestmark = pytest.mark.postgres

PEPPER = "browser-test-pepper-" * 3
ORIGIN = "http://localhost:3000"
PASSWORD = "local-safe-test-password"


def seed_user(engine, role="admin"):
    user_id, project_id = uuid4(), uuid4()
    user = InternalUserRow(
        id=user_id,
        name=f"operator-{user_id}",
        active=True,
        password_hash=ScryptPasswordHasher().hash(PASSWORD),
        credential_version=1,
    )
    user_name = user.name
    project = ProjectRow(id=project_id, name=f"project-{project_id}")
    with Session(engine) as session, session.begin():
        session.add_all([user, project])
        session.flush()
        session.add(ProjectMembershipRow(user_id=user_id, project_id=project_id, role=role))
    return user_id, project_id, user_name


def test_browser_session_survives_service_restart_and_revokes_on_password_reset(postgres_engine):
    user_id, project_id, user_name = seed_user(postgres_engine)
    database = async_engine_for(postgres_engine)
    now = datetime(2026, 11, 1, tzinfo=UTC)
    current_time = [now]
    sessions = async_sessionmaker(database, expire_on_commit=False)
    first_service = BrowserIdentityService(
        sessions, lambda: current_time[0], False, (ORIGIN,), PEPPER
    )

    async def exercise():
        login = await first_service.login(user_name, PASSWORD, project_id, ORIGIN)
        assert login.principal.user_id == user_id
        assert login.principal.role == "admin"
        assert login.session_token not in repr(login)
        with pytest.raises(IdentityValidationError):
            await first_service.set_project_membership(user_id, user_id, project_id, "developer")
        members = await first_service.list_project_members(login.session_token, project_id)
        assert len(members) == 1 and members[0].user_id == user_id
        added_id = await first_service.create_user(
            f"member-{uuid4()}", "a-different-safe-password", user_id
        )
        await first_service.set_project_membership(user_id, added_id, project_id, "developer")
        members = await first_service.list_project_members(login.session_token, project_id)
        assert {member.user_id for member in members} == {user_id, added_id}

        # A newly composed service can authenticate the digest persisted by the first.
        restarted = BrowserIdentityService(
            sessions, lambda: current_time[0], False, (ORIGIN,), PEPPER
        )
        principal = await restarted.authenticate_session(login.session_token)
        assert principal.session_id == login.principal.session_id
        assert principal.project_id == project_id

        current = await restarted.browser_me(login.session_token)
        with pytest.raises(BrowserAuthenticationRejected):
            await restarted.logout(login.session_token, login.csrf_token, ORIGIN)
        await restarted.logout(login.session_token, current.csrf_token, ORIGIN)
        with pytest.raises(BrowserAuthenticationRejected):
            await restarted.authenticate_session(login.session_token)

        login = await restarted.login(user_name, PASSWORD, project_id, ORIGIN)
        reset = await restarted.issue_password_setup(user_id, user_id)
        assert await restarted.consume_password_setup(reset, "new-local-safe-password")
        assert not await restarted.consume_password_setup(reset, "another-local-safe-password")
        with pytest.raises(BrowserAuthenticationRejected):
            await restarted.authenticate_session(login.session_token)
        changed = await restarted.login(user_name, "new-local-safe-password", project_id, ORIGIN)
        assert changed.principal.user_id == user_id

        with Session(postgres_engine) as session:
            stored = (
                session.query(BrowserSessionRow).filter_by(id=changed.principal.session_id).one()
            )
            throttle = session.get(BrowserLoginThrottleRow, restarted._digest(user_name))
            assert stored.token_digest != changed.session_token
            assert stored.csrf_digest != changed.csrf_token
            assert throttle is not None and throttle.failures == 0
            assert session.query(IdentityActivityRow).filter_by(subject_id=user_id).count() >= 4

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())


def test_persistent_username_throttle_blocks_retries_without_revealing_account(postgres_engine):
    _user_id, _project_id, user_name = seed_user(postgres_engine, role="developer")
    database = async_engine_for(postgres_engine)
    sessions = async_sessionmaker(database, expire_on_commit=False)
    service = BrowserIdentityService(sessions, lambda: datetime.now(UTC), False, (ORIGIN,), PEPPER)

    async def exercise():
        for _ in range(6):
            with pytest.raises(BrowserAuthenticationRejected):
                await service.login(user_name, "incorrect password", None, ORIGIN)
        # The correct password remains blocked during the persisted lockout interval.
        with pytest.raises(BrowserAuthenticationRejected):
            await service.login(user_name, PASSWORD, None, ORIGIN)
        with Session(postgres_engine) as session:
            throttle = session.get(BrowserLoginThrottleRow, service._digest(user_name))
            assert throttle is not None
            assert throttle.failures == 6
            assert throttle.locked_until is not None
            assert session.query(BrowserSessionRow).count() == 0

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())


def test_session_idle_and_absolute_expiry_and_disabled_user_rejection(postgres_engine):
    user_id, project_id, user_name = seed_user(postgres_engine, role="developer")
    database = async_engine_for(postgres_engine)
    sessions = async_sessionmaker(database, expire_on_commit=False)
    now = [datetime(2026, 11, 1, tzinfo=UTC)]
    service = BrowserIdentityService(sessions, lambda: now[0], False, (ORIGIN,), PEPPER)

    async def exercise():
        login = await service.login(user_name, PASSWORD, project_id, ORIGIN)
        now[0] += timedelta(minutes=31)
        with pytest.raises(BrowserAuthenticationRejected):
            await service.authenticate_session(login.session_token)

        now[0] = datetime(2026, 11, 1, tzinfo=UTC)
        login = await service.login(user_name, PASSWORD, project_id, ORIGIN)
        now[0] += timedelta(hours=8, seconds=1)
        with pytest.raises(BrowserAuthenticationRejected):
            await service.authenticate_session(login.session_token)

        now[0] = datetime(2026, 11, 1, tzinfo=UTC)
        login = await service.login(user_name, PASSWORD, project_id, ORIGIN)
        await service.set_user_active(user_id, user_id, False)
        with pytest.raises(BrowserAuthenticationRejected):
            await service.authenticate_session(login.session_token)

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())


def test_authorized_browser_activity_refreshes_idle_expiry(postgres_engine):
    _user_id, project_id, user_name = seed_user(postgres_engine)
    database = async_engine_for(postgres_engine)
    sessions = async_sessionmaker(database, expire_on_commit=False)
    now = [datetime(2026, 11, 1, tzinfo=UTC)]
    service = BrowserIdentityService(sessions, lambda: now[0], False, (ORIGIN,), PEPPER)

    async def exercise():
        login = await service.login(user_name, PASSWORD, project_id, ORIGIN)
        now[0] += timedelta(minutes=20)
        members = await service.list_project_members(login.session_token, project_id)
        assert len(members) == 1

        with Session(postgres_engine) as session:
            stored = session.get(BrowserSessionRow, login.principal.session_id)
            assert stored is not None
            assert stored.last_seen_at == now[0]
            assert stored.idle_expires_at == now[0] + timedelta(minutes=30)

        # Activity at minute 20 keeps the session usable after its original
        # minute-30 idle deadline while the absolute expiry stays unchanged.
        now[0] += timedelta(minutes=20)
        assert (await service.authenticate_session(login.session_token)).user_id == _user_id

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())


def test_membership_update_and_session_authorization_share_lock_order(postgres_engine):
    user_id, project_id, user_name = seed_user(postgres_engine)
    second_admin_id = uuid4()
    with Session(postgres_engine) as session, session.begin():
        session.add(
            InternalUserRow(
                id=second_admin_id,
                name=f"second-admin-{second_admin_id}",
                active=True,
                password_hash=ScryptPasswordHasher().hash("another-safe-test-password"),
                credential_version=1,
            )
        )
        session.flush()
        session.add(
            ProjectMembershipRow(user_id=second_admin_id, project_id=project_id, role="admin")
        )

    database = async_engine_for(postgres_engine)
    sessions = async_sessionmaker(database, expire_on_commit=False)
    service = BrowserIdentityService(sessions, lambda: datetime.now(UTC), False, (ORIGIN,), PEPPER)

    async def exercise():
        login = await service.login(user_name, PASSWORD, project_id, ORIGIN)
        digest = service._digest(login.session_token)

        async def authorize():
            async with sessions() as session, session.begin():
                principal = await SQLAlchemyBrowserIdentityRepository(
                    session
                ).authorize_browser_operation(digest, project_id, datetime.now(UTC))
                assert principal is not None

        async def update_membership(role: str):
            await service.set_project_membership(second_admin_id, user_id, project_id, role)

        # Repeated simultaneous reads and membership writes would form a
        # user/project lock cycle if authorization acquired session/user first.
        for index in range(12):
            await asyncio.wait_for(
                asyncio.gather(
                    authorize(), update_membership("developer" if index % 2 == 0 else "admin")
                ),
                timeout=10,
            )

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())


@pytest.mark.parametrize("operation", ["authorize", "select_project"])
def test_revocation_during_authority_lock_wait_is_revalidated(postgres_engine, operation):
    _user_id, project_id, user_name = seed_user(postgres_engine)
    database = async_engine_for(postgres_engine)
    sessions = async_sessionmaker(database, expire_on_commit=False)
    service = BrowserIdentityService(sessions, lambda: datetime.now(UTC), False, (ORIGIN,), PEPPER)

    async def exercise():
        login = await service.login(user_name, PASSWORD, project_id, ORIGIN)
        digest = service._digest(login.session_token)
        discovered, resume = asyncio.Event(), asyncio.Event()

        async def authorize():
            async with sessions() as session, session.begin():
                repository = SQLAlchemyBrowserIdentityRepository(session)
                original = repository._lock_user_projects

                async def paused_lookup(user_id, extra=()):
                    discovered.set()
                    await resume.wait()
                    return await original(user_id, extra)

                repository._lock_user_projects = paused_lookup
                if operation == "authorize":
                    return await repository.authorize_browser_operation(
                        digest, project_id, datetime.now(UTC)
                    )
                return await repository.select_project(
                    token_digest=digest, project_id=project_id, now=datetime.now(UTC)
                )

        pending = asyncio.create_task(authorize())
        await asyncio.wait_for(discovered.wait(), timeout=5)
        await service.logout(login.session_token, login.csrf_token, ORIGIN)
        resume.set()
        assert await asyncio.wait_for(pending, timeout=5) is None

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())
