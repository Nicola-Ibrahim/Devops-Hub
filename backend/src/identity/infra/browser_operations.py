"""Outer transaction and security adapter for internal browser identity."""

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity.application.browser_login.command import (
    CheckBrowserLoginCommand,
    VerifyBrowserPasswordChangeCommand,
)
from identity.application.browser_login.handler import (
    CheckBrowserLoginHandler,
    VerifyBrowserPasswordChangeHandler,
)
from identity.application.browser_sessions.command import (
    LogoutAllBrowserSessionsCommand,
    LogoutBrowserSessionCommand,
    RefreshBrowserSessionCommand,
    RevokeBrowserSessionCommand,
    RotateBrowserCsrfCommand,
    SelectBrowserProjectCommand,
)
from identity.application.browser_sessions.handler import (
    AuthorizeBrowserMutationHandler,
    ListBrowserSessionsHandler,
    LogoutAllBrowserSessionsHandler,
    LogoutBrowserSessionHandler,
    RefreshBrowserSessionHandler,
    RevokeBrowserSessionHandler,
    RotateBrowserCsrfHandler,
    SelectBrowserProjectHandler,
    require_browser_origin,
)
from identity.application.browser_sessions.query import (
    ListBrowserSessionsQuery,
)
from identity.application.internal_users.command import (
    BootstrapFirstProjectAdminCommand,
    ConsumePasswordSetupCommand,
    CreateInternalUserCommand,
    IssuePasswordSetupCommand,
    SetInternalUserActiveCommand,
)
from identity.application.internal_users.handler import (
    BootstrapFirstProjectAdminHandler,
    ConsumePasswordSetupHandler,
    CreateInternalUserHandler,
    IssuePasswordSetupHandler,
    SetInternalUserActiveHandler,
)
from identity.application.project_memberships.command import (
    ManageProjectMembershipCommand,
    SetProjectMembershipCommand,
)
from identity.application.project_memberships.handler import (
    ListProjectMembersHandler,
    ManageProjectMembershipHandler,
    SetProjectMembershipHandler,
)
from identity.application.project_memberships.query import ListProjectMembersByActorQuery
from identity.application.shared.errors import IdentityUnavailable
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.browser_identity import (
    BrowserLogin,
    BrowserPrincipal,
    BrowserProjectMember,
    BrowserSession,
)
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
        require_browser_origin(origin, tuple(self.allowed_origins))

    def _session_authorizer(
        self, repo: SQLAlchemyBrowserIdentityRepository
    ) -> AuthorizeBrowserMutationHandler:
        return AuthorizeBrowserMutationHandler(
            repo, self.clock, self._digest, tuple(self.allowed_origins)
        )

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
        login = CheckBrowserLoginHandler(self._passwords, self._dummy_password_hash)
        name = login.normalize_user_name(user_name)
        account = await self._run(lambda repo: repo.find_login_account(name), lambda result: result)
        check = await login.execute(CheckBrowserLoginCommand(name, password, account))
        name = check.normalized_user_name
        token, csrf, now = self._tokens.generate(), self._tokens.generate(), self.clock()
        result = await self._run(
            lambda repo: repo.complete_login(
                user_name=name,
                username_digest=self._digest(name),
                expected_version=check.credential_version,
                accepted=check.accepted,
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
            lambda repo: RefreshBrowserSessionHandler(repo, self.clock, self._digest).execute(
                RefreshBrowserSessionCommand(session_token, project_id)
            ),
            lambda value: value,
        )
        return result

    async def browser_me(self, session_token: str) -> BrowserPrincipal:
        return await self._run(
            lambda repo: RotateBrowserCsrfHandler(
                repo, self.clock, self._digest, self._tokens.generate
            ).execute(RotateBrowserCsrfCommand(session_token)),
            lambda value: value,
        )

    async def select_project(
        self, session_token: str, project_id: UUID, csrf_token: str, origin: str | None
    ) -> BrowserPrincipal:
        return await self._run(
            lambda repo: SelectBrowserProjectHandler(
                repo,
                self.clock,
                self._digest,
                self._tokens.generate,
                tuple(self.allowed_origins),
            ).execute(
                SelectBrowserProjectCommand(
                    session_token=session_token,
                    project_id=project_id,
                    csrf_token=csrf_token,
                    origin=origin,
                )
            ),
            lambda value: value,
        )

    async def logout(self, session_token: str, csrf_token: str, origin: str | None) -> None:
        await self._run(
            lambda repo: LogoutBrowserSessionHandler(self._session_authorizer(repo)).execute(
                LogoutBrowserSessionCommand(session_token, csrf_token, origin)
            ),
            lambda _: None,
        )

    async def logout_all(self, session_token: str, csrf_token: str, origin: str | None) -> int:
        return await self._run(
            lambda repo: LogoutAllBrowserSessionsHandler(self._session_authorizer(repo)).execute(
                LogoutAllBrowserSessionsCommand(session_token, csrf_token, origin)
            ),
            int,
        )

    async def list_sessions(self, session_token: str) -> tuple[BrowserSession, ...]:
        return await self._run(
            lambda repo: ListBrowserSessionsHandler(
                RefreshBrowserSessionHandler(repo, self.clock, self._digest)
            ).execute(ListBrowserSessionsQuery(session_token)),
            tuple,
        )

    async def revoke_session(
        self, session_token: str, session_id: UUID, csrf_token: str, origin: str | None
    ) -> bool:
        return await self._run(
            lambda repo: RevokeBrowserSessionHandler(self._session_authorizer(repo)).execute(
                RevokeBrowserSessionCommand(
                    session_token=session_token,
                    session_id=session_id,
                    csrf_token=csrf_token,
                    origin=origin,
                )
            ),
            bool,
        )

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
        password_change = await VerifyBrowserPasswordChangeHandler(self._passwords).execute(
            VerifyBrowserPasswordChangeCommand(account, current_password, new_password)
        )

        async def action(repo: SQLAlchemyBrowserIdentityRepository) -> None:
            await self._check_csrf(repo, session_token, csrf_token, origin)
            if not await repo.change_password(
                user_id=principal.user_id,
                expected_version=password_change.credential_version,
                password_hash=password_change.encoded_password,
                now=self.clock(),
            ):
                raise BrowserAuthenticationRejected()

        await self._run(action, lambda _: None)

    # Trusted operator/CLI capabilities; deliberately absent from the HTTP protocol.
    async def create_user(
        self, user_name: str, password: str, actor_id: UUID | None = None
    ) -> UUID:
        return await self._run(
            lambda repo: CreateInternalUserHandler(repo, self._passwords, self.clock).execute(
                CreateInternalUserCommand(user_name, password, actor_id)
            ),
            lambda value: value,
        )

    async def bootstrap_first_project_admin(self, user_id: UUID, project_id: UUID) -> None:
        await self._run(
            lambda repo: BootstrapFirstProjectAdminHandler(repo, self.clock).execute(
                BootstrapFirstProjectAdminCommand(user_id, project_id)
            ),
            lambda _: None,
        )

    async def set_project_membership(
        self, actor_id: UUID, user_id: UUID, project_id: UUID, role: str | None
    ) -> None:
        await self._run(
            lambda repo: SetProjectMembershipHandler(repo, self.clock).execute(
                SetProjectMembershipCommand(actor_id, user_id, project_id, role)
            ),
            lambda _: None,
        )

    async def list_project_members(
        self, session_token: str, project_id: UUID
    ) -> tuple[BrowserProjectMember, ...]:
        async def action(
            repo: SQLAlchemyBrowserIdentityRepository,
        ) -> tuple[BrowserProjectMember, ...]:
            principal = await RefreshBrowserSessionHandler(repo, self.clock, self._digest).execute(
                RefreshBrowserSessionCommand(session_token, project_id)
            )
            return await ListProjectMembersHandler(repo).execute(
                ListProjectMembersByActorQuery(principal.user_id, project_id)
            )

        return await self._run(
            action,
            tuple,
        )

    async def manage_project_membership(
        self,
        session_token: str,
        project_id: UUID,
        user_id: UUID,
        role: str | None,
        csrf_token: str,
        origin: str | None,
    ) -> None:
        await self._run(
            lambda repo: ManageProjectMembershipHandler(
                repo, self.clock, self._digest, tuple(self.allowed_origins)
            ).execute(
                ManageProjectMembershipCommand(
                    session_token, project_id, user_id, role, csrf_token, origin
                )
            ),
            lambda _: None,
        )

    async def set_user_active(self, actor_id: UUID, user_id: UUID, active: bool) -> None:
        await self._run(
            lambda repo: SetInternalUserActiveHandler(repo, self.clock).execute(
                SetInternalUserActiveCommand(actor_id, user_id, active)
            ),
            lambda _: None,
        )

    async def issue_password_setup(self, user_id: UUID, actor_id: UUID) -> str:
        return await self._run(
            lambda repo: IssuePasswordSetupHandler(
                repo, self.clock, self._tokens.generate, self._digest
            ).execute(IssuePasswordSetupCommand(user_id, actor_id)),
            lambda secret: secret,
        )

    async def consume_password_setup(self, secret: str, new_password: str) -> bool:
        return await self._run(
            lambda repo: ConsumePasswordSetupHandler(
                repo, self._passwords, self.clock, self._digest
            ).execute(ConsumePasswordSetupCommand(secret, new_password)),
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
