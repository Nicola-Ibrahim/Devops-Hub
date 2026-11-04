"""Outer transaction and security adapter for internal browser identity."""

import asyncio
import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timedelta
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity.application.browser_contracts import (
    BrowserLogin,
    BrowserPrincipal,
    BrowserProjectMember,
    BrowserSession,
)
from identity.application.browser_identity import BrowserIdentity
from identity.application.errors import IdentityUnavailable
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.infra.browser_security import (
    OpaqueSecretGenerator,
    ScryptPasswordHasher,
    secret_digest,
)
from identity.infra.persistence.browser_identity import SQLAlchemyBrowserIdentityRepository
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork

T = TypeVar("T")
R = TypeVar("R")
Clock = Callable[[], datetime]


class BrowserIdentityService:
    """Composes identity-owned repository calls with short, single-use transactions."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
        cookie_secure: bool = True,
        allowed_origins: tuple[str, ...] = (),
        token_pepper: str = "",
    ) -> None:
        self.sessions = sessions
        self.clock = clock
        self.cookie_secure = cookie_secure
        self.allowed_origins = frozenset(origin.rstrip("/") for origin in allowed_origins)
        self._pepper = token_pepper.encode()
        self._passwords = ScryptPasswordHasher()
        self._tokens = OpaqueSecretGenerator()
        self._dummy_password_hash = self._passwords.hash("devops-hub-dummy-password-value")

    async def _run(
        self,
        action: Callable[[SQLAlchemyBrowserIdentityRepository], Awaitable[T]],
        present: Callable[[T], R],
    ) -> R:
        try:
            async with self.sessions() as session:
                unit = SqlAlchemyUnitOfWork(session)
                repo = SQLAlchemyBrowserIdentityRepository(session)
                return await unit.run(lambda: action(repo), present)
        except DatabaseUnavailable as error:
            raise IdentityUnavailable() from error

    def _digest(self, secret: str) -> str:
        if self._pepper:
            return hmac.new(self._pepper, secret.encode(), hashlib.sha256).hexdigest()
        return secret_digest(secret)

    def _check_origin(self, origin: str | None) -> None:
        if origin is None or origin.rstrip("/") not in self.allowed_origins:
            raise BrowserAuthenticationRejected()

    async def _check_csrf(
        self, repo: SQLAlchemyBrowserIdentityRepository, token: str, csrf: str, origin: str | None
    ) -> BrowserPrincipal:
        self._check_origin(origin)
        principal = await repo.authorize_browser_operation(
            self._digest(token), None, self.clock(), lock_for_mutation=True
        )
        if principal is None or not await repo.validate_csrf(
            self._digest(token), self._digest(csrf)
        ):
            raise BrowserAuthenticationRejected()
        return principal

    async def login(
        self, user_name: str, password: str, project_id: UUID | None, origin: str | None
    ) -> BrowserLogin:
        self._check_origin(origin)
        name = BrowserIdentity.login_name(user_name)
        account = await self._run(lambda repo: repo.find_login_account(name), lambda result: result)
        encoded = account.password_hash if account is not None else self._dummy_password_hash
        matches = await asyncio.to_thread(self._passwords.verify, password, encoded)
        accepted = account is not None and account.active and matches
        token, csrf, now = self._tokens.generate(), self._tokens.generate(), self.clock()
        result = await self._run(
            lambda repo: repo.complete_login(
                user_name=name,
                username_digest=self._digest(name),
                expected_version=account.credential_version if account else None,
                accepted=accepted,
                token_digest=self._digest(token),
                csrf_digest=self._digest(csrf),
                now=now,
            ),
            lambda value: value,
        )
        if result is None:
            raise BrowserAuthenticationRejected()
        principal, _, expires = result
        if project_id is not None:
            selected = await self._run(
                lambda repo: repo.select_project(
                    token_digest=self._digest(token), project_id=project_id, now=self.clock()
                ),
                lambda value: value,
            )
            if selected is None:
                await self._run(
                    lambda repo: repo.logout(self._digest(token), self.clock()), lambda _: None
                )
                raise BrowserAuthenticationRejected()
            principal = selected
        return BrowserLogin(token, csrf, replace(principal, csrf_token=csrf), expires)

    async def authenticate_session(
        self, session_token: str, project_id: UUID | None = None
    ) -> BrowserPrincipal:
        result = await self._run(
            lambda repo: repo.authenticate_session(
                token_digest=self._digest(session_token), project_id=project_id, now=self.clock()
            ),
            lambda value: value,
        )
        if result is None:
            raise BrowserAuthenticationRejected()
        return result[0]

    async def browser_me(self, session_token: str) -> BrowserPrincipal:
        csrf = self._tokens.generate()

        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> BrowserPrincipal:
            result = await repo.authenticate_session(
                token_digest=self._digest(session_token), project_id=None, now=self.clock()
            )
            if result is None or not await repo.rotate_csrf(
                self._digest(session_token), self._digest(csrf), self.clock()
            ):
                raise BrowserAuthenticationRejected()
            return result[0]

        return replace(await self._run(action, lambda value: value), csrf_token=csrf)

    async def select_project(
        self, session_token: str, project_id: UUID, csrf_token: str, origin: str | None
    ) -> BrowserPrincipal:
        next_csrf_token = self._tokens.generate()

        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> BrowserPrincipal:
            await self._check_csrf(repo, session_token, csrf_token, origin)
            principal = await repo.select_project(
                token_digest=self._digest(session_token), project_id=project_id, now=self.clock()
            )
            if principal is None or not await repo.rotate_csrf(
                self._digest(session_token), self._digest(next_csrf_token), self.clock()
            ):
                raise BrowserAuthenticationRejected()
            return replace(principal, csrf_token=next_csrf_token)

        return await self._run(action, lambda value: value)

    async def logout(self, session_token: str, csrf_token: str, origin: str | None) -> None:
        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> None:
            await self._check_csrf(repo, session_token, csrf_token, origin)
            await repo.logout(self._digest(session_token), self.clock())

        await self._run(action, lambda _: None)

    async def logout_all(self, session_token: str, csrf_token: str, origin: str | None) -> int:
        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> int:
            principal = await self._check_csrf(repo, session_token, csrf_token, origin)
            return await repo.logout_all(principal.user_id, self.clock())

        return await self._run(action, int)

    async def list_sessions(self, session_token: str) -> tuple[BrowserSession, ...]:
        async def action(
            repo: SQLAlchemyBrowserIdentityRepository,
        ) -> tuple[BrowserSession, ...]:
            result = await repo.authenticate_session(
                token_digest=self._digest(session_token), project_id=None, now=self.clock()
            )
            if result is None:
                raise BrowserAuthenticationRejected()
            return await repo.list_sessions(result[0].user_id, result[0].session_id, self.clock())

        return await self._run(action, tuple)

    async def revoke_session(
        self, session_token: str, session_id: UUID, csrf_token: str, origin: str | None
    ) -> bool:
        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> bool:
            principal = await self._check_csrf(repo, session_token, csrf_token, origin)
            return await repo.revoke_session(principal.user_id, session_id, self.clock())

        return await self._run(action, bool)

    async def change_password(
        self,
        session_token: str,
        current_password: str,
        new_password: str,
        csrf_token: str,
        origin: str | None,
    ) -> None:
        self._check_origin(origin)
        principal = await self.authenticate_session(session_token)
        account = await self._run(
            lambda repo: repo.find_login_account(principal.user_name), lambda result: result
        )
        if account is None or not await asyncio.to_thread(
            self._passwords.verify, current_password, account.password_hash
        ):
            raise BrowserAuthenticationRejected()
        BrowserIdentity.password(new_password)
        encoded = await asyncio.to_thread(self._passwords.hash, new_password)

        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> None:
            await self._check_csrf(repo, session_token, csrf_token, origin)
            if not await repo.change_password(
                user_id=principal.user_id,
                expected_version=account.credential_version,
                password_hash=encoded,
                now=self.clock(),
            ):
                raise BrowserAuthenticationRejected()

        await self._run(action, lambda _: None)

    # Trusted operator/CLI capabilities; deliberately absent from the HTTP protocol.
    async def create_user(
        self, user_name: str, password: str, actor_id: UUID | None = None
    ) -> UUID:
        name = BrowserIdentity.login_name(user_name)
        BrowserIdentity.password(password)
        encoded = await asyncio.to_thread(self._passwords.hash, password)
        return await self._run(
            lambda repo: repo.create_user(name, encoded, actor_id, self.clock()),
            lambda value: value,
        )

    async def bootstrap_first_project_admin(self, user_id: UUID, project_id: UUID) -> None:
        await self._run(
            lambda repo: repo.bootstrap_first_project_admin(
                user_id=user_id, project_id=project_id, now=self.clock()
            ),
            lambda _: None,
        )

    async def set_project_membership(
        self, actor_id: UUID, user_id: UUID, project_id: UUID, role: str | None
    ) -> None:
        await self._run(
            lambda repo: repo.set_membership(
                actor_id=actor_id,
                user_id=user_id,
                project_id=project_id,
                role=role,
                now=self.clock(),
            ),
            lambda _: None,
        )

    async def list_project_members(
        self, session_token: str, project_id: UUID
    ) -> tuple[BrowserProjectMember, ...]:
        async def action(
            repo: SQLAlchemyBrowserIdentityRepository,
        ) -> tuple[BrowserProjectMember, ...]:
            principal = await repo.authorize_browser_operation(
                self._digest(session_token), project_id, self.clock()
            )
            if principal is None:
                raise BrowserAuthenticationRejected()
            return await repo.list_project_members(
                actor_id=principal.user_id, project_id=project_id
            )

        return await self._run(action, tuple)

    async def manage_project_membership(
        self,
        session_token: str,
        project_id: UUID,
        user_id: UUID,
        role: str | None,
        csrf_token: str,
        origin: str | None,
    ) -> None:
        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> None:
            await repo.lock_project_membership_admin_scope(project_id)
            principal = await self._check_csrf(repo, session_token, csrf_token, origin)
            await repo.set_membership(
                actor_id=principal.user_id,
                user_id=user_id,
                project_id=project_id,
                role=role,
                now=self.clock(),
            )

        await self._run(action, lambda _: None)

    async def set_user_active(self, actor_id: UUID, user_id: UUID, active: bool) -> None:
        await self._run(
            lambda repo: repo.set_user_active(
                actor_id=actor_id, user_id=user_id, active=active, now=self.clock()
            ),
            lambda _: None,
        )

    async def issue_password_setup(self, user_id: UUID, actor_id: UUID) -> str:
        secret, now = self._tokens.generate(), self.clock()
        await self._run(
            lambda repo: repo.issue_password_setup(
                user_id=user_id,
                digest=self._digest(secret),
                expires_at=now + timedelta(hours=1),
                actor_id=actor_id,
                now=now,
            ),
            lambda _: None,
        )
        return secret

    async def consume_password_setup(self, secret: str, new_password: str) -> bool:
        BrowserIdentity.password(new_password)
        encoded = await asyncio.to_thread(self._passwords.hash, new_password)
        return await self._run(
            lambda repo: repo.consume_password_setup(
                digest=self._digest(secret), password_hash=encoded, now=self.clock()
            ),
            bool,
        )


async def authenticate_browser_operation(
    session: AsyncSession,
    token: str,
    project_id: UUID | None,
    clock: Clock,
    csrf_token: str | None = None,
    origin: str | None = None,
    allowed_origins: tuple[str, ...] = (),
    mutate: bool = False,
    token_pepper: str = "",
) -> BrowserPrincipal:
    """Validate browser credentials in the platform operation's existing transaction."""
    if mutate and (
        origin is None or origin.rstrip("/") not in {o.rstrip("/") for o in allowed_origins}
    ):
        raise BrowserAuthenticationRejected()
    repo = SQLAlchemyBrowserIdentityRepository(session)

    def digest(value: str) -> str:
        if token_pepper:
            return hmac.new(token_pepper.encode(), value.encode(), hashlib.sha256).hexdigest()
        return secret_digest(value)

    principal = await repo.authorize_browser_operation(
        digest(token), project_id, clock(), lock_for_mutation=mutate
    )
    if principal is None:
        raise BrowserAuthenticationRejected()
    if mutate and (
        csrf_token is None or not await repo.validate_csrf(digest(token), digest(csrf_token))
    ):
        raise BrowserAuthenticationRejected()
    return principal
