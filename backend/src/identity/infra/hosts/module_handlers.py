"""Infrastructure adapters from module messages to identity host operations."""

from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.change_password.command import ChangePasswordCommand
from identity.application.list_project_members.query import ListProjectMembersQuery
from identity.application.list_sessions.query import ListSessionsQuery
from identity.application.list_sessions.result import SessionDetails
from identity.application.login.command import (
    LoginCommand,
)
from identity.application.login.result import LoginResult
from identity.application.logout.command import LogoutCommand
from identity.application.logout_all_sessions.command import LogoutAllSessionsCommand
from identity.application.manage_project_membership.command import ManageProjectMembershipCommand
from identity.application.revoke_session.command import RevokeSessionCommand
from identity.application.rotate_csrf.command import RotateCsrfCommand
from identity.application.select_active_project.command import SelectActiveProjectCommand
from identity.contracts import AuthenticatedPrincipal
from identity.domain.records import ProjectMemberDetails, SessionPrincipal
from identity.infra.hosts.api_token_authentication import TokenAuthenticationHost
from identity.infra.hosts.identity_sessions import BrowserIdentityService


class AuthenticateIdentityTokenHandler:
    def __init__(self, host: TokenAuthenticationHost) -> None:
        self.host = host

    async def execute(self, query: AuthenticateApiTokenQuery) -> AuthenticatedPrincipal:
        return await self.host.authenticate(query.token)


class AuthenticateSessionHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, query: AuthenticateSessionQuery) -> SessionPrincipal:
        return await self.browser.authenticate_session(query.session_token, query.project_id)


class LoginHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: LoginCommand) -> LoginResult:
        return await self.browser.login(
            command.user_name, command.password, command.project_id, command.origin
        )


class RotateCsrfHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: RotateCsrfCommand) -> SessionPrincipal:
        return await self.browser.browser_me(command.session_token)


class SelectActiveProjectHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: SelectActiveProjectCommand) -> SessionPrincipal:
        return await self.browser.select_project(
            command.session_token,
            command.project_id,
            command.csrf_token,
            command.origin,
        )


class LogoutHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: LogoutCommand) -> None:
        await self.browser.logout(command.session_token, command.csrf_token, command.origin)


class LogoutAllSessionsHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: LogoutAllSessionsCommand) -> int:
        return await self.browser.logout_all(
            command.session_token, command.csrf_token, command.origin
        )


class ListSessionsHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, query: ListSessionsQuery) -> tuple[SessionDetails, ...]:
        return await self.browser.list_sessions(query.session_token)


class RevokeSessionHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: RevokeSessionCommand) -> bool:
        return await self.browser.revoke_session(
            command.session_token,
            command.session_id,
            command.csrf_token,
            command.origin,
        )


class ChangePasswordHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: ChangePasswordCommand) -> None:
        await self.browser.change_password(
            command.session_token,
            command.current_password,
            command.new_password,
            command.csrf_token,
            command.origin,
        )


class ListProjectMembersHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, query: ListProjectMembersQuery) -> tuple[ProjectMemberDetails, ...]:
        return await self.browser.list_project_members(query.session_token, query.project_id)


class ManageProjectMembershipHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: ManageProjectMembershipCommand) -> None:
        await self.browser.manage_project_membership(
            command.session_token,
            command.project_id,
            command.user_id,
            command.role,
            command.csrf_token,
            command.origin,
        )
