"""Outer transaction and security adapter for internal browser identity."""

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity.application.authenticate_session.handler import AuthenticateSessionHandler
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.bootstrap_first_admin.command import BootstrapFirstAdminCommand
from identity.application.bootstrap_first_admin.handler import BootstrapFirstAdminHandler
from identity.application.change_password.command import VerifyPasswordChange
from identity.application.change_password.handler import VerifyPasswordChangeHandler
from identity.application.complete_password_setup.command import CompletePasswordSetupCommand
from identity.application.complete_password_setup.handler import CompletePasswordSetupHandler
from identity.application.create_user.command import CreateUserCommand
from identity.application.create_user.handler import CreateUserHandler
from identity.application.list_project_members.handler import ListProjectMembersHandler
from identity.application.list_project_members.query import ListProjectMembersByActorQuery
from identity.application.list_sessions.handler import ListSessionsHandler
from identity.application.list_sessions.query import ListSessionsQuery
from identity.application.list_sessions.result import SessionDetails
from identity.application.login.command import (
    VerifyLoginCredentials,
)
from identity.application.login.handler import VerifyLoginCredentialsHandler
from identity.application.login.result import LoginResult
from identity.application.logout.command import LogoutCommand
from identity.application.logout.handler import LogoutHandler
from identity.application.logout_all_sessions.command import LogoutAllSessionsCommand
from identity.application.logout_all_sessions.handler import LogoutAllSessionsHandler
from identity.application.manage_project_membership.command import (
    ManageProjectMembershipCommand,
    SetProjectMembershipCommand,
)
from identity.application.manage_project_membership.handler import (
    ManageProjectMembershipHandler,
    SetProjectMembershipHandler,
)
from identity.application.revoke_session.command import RevokeSessionCommand
from identity.application.revoke_session.handler import RevokeSessionHandler
from identity.application.rotate_csrf.command import RotateCsrfCommand
from identity.application.rotate_csrf.handler import RotateCsrfHandler
from identity.application.select_active_project.command import SelectActiveProjectCommand
from identity.application.select_active_project.handler import SelectActiveProjectHandler
from identity.application.set_user_status.command import SetUserStatusCommand
from identity.application.set_user_status.handler import SetUserStatusHandler
from identity.application.shared.errors import IdentityUnavailable
from identity.application.shared.session_security import (
    AuthorizeBrowserMutationHandler,
    require_browser_origin,
)
from identity.application.start_password_setup.command import StartPasswordSetupCommand
from identity.application.start_password_setup.handler import StartPasswordSetupHandler
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.records import ProjectMemberDetails, SessionPrincipal
from identity.infra.persistence.identity_repository import SQLAlchemyIdentityRepository
from identity.infra.security.passwords import (
    OpaqueSecretGenerator,
    ScryptPasswordHasher,
    secret_digest,
)
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
        action: Callable[[SQLAlchemyIdentityRepository], Awaitable[T]],
        present: Callable[[T], R],
    ) -> R:
        try:
            async with self.sessions() as session:
                unit = SqlAlchemyUnitOfWork(session)
                repo = SQLAlchemyIdentityRepository(session)
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
        self, repo: SQLAlchemyIdentityRepository
    ) -> AuthorizeBrowserMutationHandler:
        return AuthorizeBrowserMutationHandler(
            repo, self.clock, self._digest, tuple(self.allowed_origins)
        )

    async def _check_csrf(
        self, repo: SQLAlchemyIdentityRepository, token: str, csrf: str, origin: str | None
    ) -> SessionPrincipal:
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
    ) -> LoginResult:
        self._check_origin(origin)
        login = VerifyLoginCredentialsHandler(self._passwords, self._dummy_password_hash)
        name = login.normalize_user_name(user_name)
        account = await self._run(lambda repo: repo.find_login_account(name), lambda result: result)
        check = await login.execute(VerifyLoginCredentials(name, password, account))
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
        return LoginResult(token, csrf, replace(principal, csrf_token=csrf), expires)

    async def authenticate_session(
        self, session_token: str, project_id: UUID | None = None
    ) -> SessionPrincipal:
        result = await self._run(
            lambda repo: AuthenticateSessionHandler(repo, self.clock, self._digest).execute(
                AuthenticateSessionQuery(session_token, project_id)
            ),
            lambda value: value,
        )
        return result

    async def browser_me(self, session_token: str) -> SessionPrincipal:
        return await self._run(
            lambda repo: RotateCsrfHandler(
                repo, self.clock, self._digest, self._tokens.generate
            ).execute(RotateCsrfCommand(session_token)),
            lambda value: value,
        )

    async def select_project(
        self, session_token: str, project_id: UUID, csrf_token: str, origin: str | None
    ) -> SessionPrincipal:
        return await self._run(
            lambda repo: SelectActiveProjectHandler(
                repo,
                self.clock,
                self._digest,
                self._tokens.generate,
                tuple(self.allowed_origins),
            ).execute(
                SelectActiveProjectCommand(
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
            lambda repo: LogoutHandler(self._session_authorizer(repo)).execute(
                LogoutCommand(session_token, csrf_token, origin)
            ),
            lambda _: None,
        )

    async def logout_all(self, session_token: str, csrf_token: str, origin: str | None) -> int:
        return await self._run(
            lambda repo: LogoutAllSessionsHandler(self._session_authorizer(repo)).execute(
                LogoutAllSessionsCommand(session_token, csrf_token, origin)
            ),
            int,
        )

    async def list_sessions(self, session_token: str) -> tuple[SessionDetails, ...]:
        return await self._run(
            lambda repo: ListSessionsHandler(
                AuthenticateSessionHandler(repo, self.clock, self._digest)
            ).execute(ListSessionsQuery(session_token)),
            tuple,
        )

    async def revoke_session(
        self, session_token: str, session_id: UUID, csrf_token: str, origin: str | None
    ) -> bool:
        return await self._run(
            lambda repo: RevokeSessionHandler(self._session_authorizer(repo)).execute(
                RevokeSessionCommand(
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
        password_change = await VerifyPasswordChangeHandler(self._passwords).execute(
            VerifyPasswordChange(account, current_password, new_password)
        )

        async def action(repo: SQLAlchemyIdentityRepository) -> None:
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
            lambda repo: CreateUserHandler(repo, self._passwords, self.clock).execute(
                CreateUserCommand(user_name, password, actor_id)
            ),
            lambda value: value,
        )

    async def bootstrap_first_project_admin(self, user_id: UUID, project_id: UUID) -> None:
        await self._run(
            lambda repo: BootstrapFirstAdminHandler(repo, self.clock).execute(
                BootstrapFirstAdminCommand(user_id, project_id)
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
    ) -> tuple[ProjectMemberDetails, ...]:
        async def action(
            repo: SQLAlchemyIdentityRepository,
        ) -> tuple[ProjectMemberDetails, ...]:
            principal = await AuthenticateSessionHandler(repo, self.clock, self._digest).execute(
                AuthenticateSessionQuery(session_token, project_id)
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
            lambda repo: SetUserStatusHandler(repo, self.clock).execute(
                SetUserStatusCommand(actor_id, user_id, active)
            ),
            lambda _: None,
        )

    async def issue_password_setup(self, user_id: UUID, actor_id: UUID) -> str:
        return await self._run(
            lambda repo: StartPasswordSetupHandler(
                repo, self.clock, self._tokens.generate, self._digest
            ).execute(StartPasswordSetupCommand(user_id, actor_id)),
            lambda secret: secret,
        )

    async def consume_password_setup(self, secret: str, new_password: str) -> bool:
        return await self._run(
            lambda repo: CompletePasswordSetupHandler(
                repo, self._passwords, self.clock, self._digest
            ).execute(CompletePasswordSetupCommand(secret, new_password)),
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
) -> SessionPrincipal:
    """Validate browser credentials in the platform operation's existing transaction."""
    if mutate and (
        origin is None or origin.rstrip("/") not in {o.rstrip("/") for o in allowed_origins}
    ):
        raise BrowserAuthenticationRejected()
    repo = SQLAlchemyIdentityRepository(session)

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
