"""Command/query handlers for internal browser-session lifecycle."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from identity.application.browser_sessions.command import (
    AuthorizeBrowserMutationCommand,
    ListBrowserSessionsCommand,
    LogoutAllBrowserSessionsCommand,
    LogoutBrowserSessionCommand,
    RefreshBrowserSessionCommand,
    RevokeBrowserSessionCommand,
    RotateBrowserCsrfCommand,
    SelectBrowserProjectCommand,
)
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.browser_identity import BrowserPrincipal, BrowserSession
from identity.domain.interfaces.session_repository import BrowserSessionRepository

Clock = Callable[[], datetime]
DigestSecret = Callable[[str], str]
GenerateSecret = Callable[[], str]


def require_browser_origin(origin: str | None, allowed_origins: tuple[str, ...]) -> None:
    allowed = {value.rstrip("/") for value in allowed_origins}
    if origin is None or origin.rstrip("/") not in allowed:
        raise BrowserAuthenticationRejected()


class AuthorizeBrowserMutationHandler:
    def __init__(
        self,
        repository: BrowserSessionRepository,
        clock: Clock,
        digest_secret: DigestSecret,
        allowed_origins: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret
        self.allowed_origins = allowed_origins

    async def execute(self, command: AuthorizeBrowserMutationCommand) -> BrowserPrincipal:
        require_browser_origin(command.origin, self.allowed_origins)
        token_digest = self.digest_secret(command.session_token)
        principal = await self.repository.authorize_browser_operation(
            token_digest, None, self.clock(), lock_for_mutation=True
        )
        if principal is None or not await self.repository.validate_csrf(
            token_digest, self.digest_secret(command.csrf_token)
        ):
            raise BrowserAuthenticationRejected()
        return principal


class RefreshBrowserSessionHandler:
    def __init__(
        self, repository: BrowserSessionRepository, clock: Clock, digest_secret: DigestSecret
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret

    async def execute(self, command: RefreshBrowserSessionCommand) -> BrowserPrincipal:
        result = await self.repository.authenticate_session(
            token_digest=self.digest_secret(command.session_token),
            project_id=command.project_id,
            now=self.clock(),
        )
        if result is None:
            raise BrowserAuthenticationRejected()
        return result[0]


class RotateBrowserCsrfHandler:
    def __init__(
        self,
        repository: BrowserSessionRepository,
        clock: Clock,
        digest_secret: DigestSecret,
        generate_secret: GenerateSecret,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret
        self.generate_secret = generate_secret

    async def execute(self, command: RotateBrowserCsrfCommand) -> BrowserPrincipal:
        csrf = self.generate_secret()
        token_digest = self.digest_secret(command.session_token)
        result = await self.repository.authenticate_session(
            token_digest=token_digest, project_id=None, now=self.clock()
        )
        if result is None or not await self.repository.rotate_csrf(
            token_digest, self.digest_secret(csrf), self.clock()
        ):
            raise BrowserAuthenticationRejected()
        return replace(result[0], csrf_token=csrf)


class SelectBrowserProjectHandler:
    def __init__(
        self,
        repository: BrowserSessionRepository,
        clock: Clock,
        digest_secret: DigestSecret,
        generate_secret: GenerateSecret,
        allowed_origins: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret
        self.generate_secret = generate_secret
        self.authorize = AuthorizeBrowserMutationHandler(
            repository, clock, digest_secret, allowed_origins
        )

    async def execute(self, command: SelectBrowserProjectCommand) -> BrowserPrincipal:
        await self.authorize.execute(command)
        csrf = self.generate_secret()
        token_digest = self.digest_secret(command.session_token)
        principal = await self.repository.select_project(
            token_digest=token_digest, project_id=command.project_id, now=self.clock()
        )
        if principal is None or not await self.repository.rotate_csrf(
            token_digest, self.digest_secret(csrf), self.clock()
        ):
            raise BrowserAuthenticationRejected()
        return replace(principal, csrf_token=csrf)


class LogoutBrowserSessionHandler:
    def __init__(self, authorizer: AuthorizeBrowserMutationHandler) -> None:
        self.authorizer = authorizer

    async def execute(self, command: LogoutBrowserSessionCommand) -> None:
        await self.authorizer.execute(command)
        await self.authorizer.repository.logout(
            self.authorizer.digest_secret(command.session_token), self.authorizer.clock()
        )


class LogoutAllBrowserSessionsHandler:
    def __init__(self, authorizer: AuthorizeBrowserMutationHandler) -> None:
        self.authorizer = authorizer

    async def execute(self, command: LogoutAllBrowserSessionsCommand) -> int:
        principal = await self.authorizer.execute(command)
        return await self.authorizer.repository.logout_all(
            principal.user_id, self.authorizer.clock()
        )


class ListBrowserSessionsHandler:
    def __init__(self, authenticate: RefreshBrowserSessionHandler) -> None:
        self.authenticate = authenticate

    async def execute(self, command: ListBrowserSessionsCommand) -> tuple[BrowserSession, ...]:
        principal = await self.authenticate.execute(
            RefreshBrowserSessionCommand(command.session_token)
        )
        return await self.authenticate.repository.list_sessions(
            principal.user_id, principal.session_id, self.authenticate.clock()
        )


class RevokeBrowserSessionHandler:
    def __init__(self, authorizer: AuthorizeBrowserMutationHandler) -> None:
        self.authorizer = authorizer

    async def execute(self, command: RevokeBrowserSessionCommand) -> bool:
        principal = await self.authorizer.execute(command)
        return await self.authorizer.repository.revoke_session(
            principal.user_id, command.session_id, self.authorizer.clock()
        )
