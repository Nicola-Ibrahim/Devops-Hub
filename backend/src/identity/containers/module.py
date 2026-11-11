"""Explicit identity message-to-handler bindings and lazy module dispatch."""

from dishka import AsyncContainer

from identity.application.module_messages import (
    AuthenticateBrowserSessionQuery,
    AuthenticateIdentityTokenQuery,
    ChangeBrowserPasswordCommand,
    ListBrowserSessionsQuery,
    ListProjectMembersQuery,
    LoginBrowserSessionCommand,
    LogoutAllBrowserSessionsCommand,
    LogoutBrowserSessionCommand,
    ManageProjectMembershipCommand,
    ReadBrowserCookiePolicyQuery,
    ReadBrowserPrincipalQuery,
    RevokeBrowserSessionCommand,
    SelectBrowserProjectCommand,
)
from identity.contracts import AuthenticatedPrincipal
from identity.domain.browser_identity import (
    BrowserLogin,
    BrowserPrincipal,
    BrowserProjectMember,
    BrowserSession,
)
from identity.infra.browser_operations import BrowserIdentityService
from identity.infra.token_authentication_host import TokenAuthenticationHost
from shared.dispatch import HandlerRegistry, ModuleDispatcher


class AuthenticateIdentityTokenHandler:
    def __init__(self, host: TokenAuthenticationHost) -> None:
        self.host = host

    async def execute(self, query: AuthenticateIdentityTokenQuery) -> AuthenticatedPrincipal:
        return await self.host.authenticate(query.token)


class AuthenticateBrowserSessionHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, query: AuthenticateBrowserSessionQuery) -> BrowserPrincipal:
        return await self.browser.authenticate_session(query.session_token, query.project_id)


class LoginBrowserSessionHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: LoginBrowserSessionCommand) -> BrowserLogin:
        return await self.browser.login(
            command.user_name, command.password, command.project_id, command.origin
        )


class ReadBrowserPrincipalHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, query: ReadBrowserPrincipalQuery) -> BrowserPrincipal:
        return await self.browser.browser_me(query.session_token)


class ReadBrowserCookiePolicyHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, query: ReadBrowserCookiePolicyQuery) -> bool:
        del query
        return self.browser.cookie_secure


class SelectBrowserProjectHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: SelectBrowserProjectCommand) -> BrowserPrincipal:
        return await self.browser.select_project(
            command.session_token,
            command.project_id,
            command.csrf_token,
            command.origin,
        )


class LogoutBrowserSessionHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: LogoutBrowserSessionCommand) -> None:
        await self.browser.logout(command.session_token, command.csrf_token, command.origin)


class LogoutAllBrowserSessionsHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: LogoutAllBrowserSessionsCommand) -> int:
        return await self.browser.logout_all(
            command.session_token, command.csrf_token, command.origin
        )


class ListBrowserSessionsHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, query: ListBrowserSessionsQuery) -> tuple[BrowserSession, ...]:
        return await self.browser.list_sessions(query.session_token)


class RevokeBrowserSessionHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: RevokeBrowserSessionCommand) -> bool:
        return await self.browser.revoke_session(
            command.session_token,
            command.session_id,
            command.csrf_token,
            command.origin,
        )


class ChangeBrowserPasswordHandler:
    def __init__(self, browser: BrowserIdentityService) -> None:
        self.browser = browser

    async def execute(self, command: ChangeBrowserPasswordCommand) -> None:
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

    async def execute(self, query: ListProjectMembersQuery) -> tuple[BrowserProjectMember, ...]:
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


IDENTITY_HANDLER_REGISTRY = HandlerRegistry(
    commands=(
        (LoginBrowserSessionCommand, LoginBrowserSessionHandler),
        (SelectBrowserProjectCommand, SelectBrowserProjectHandler),
        (LogoutBrowserSessionCommand, LogoutBrowserSessionHandler),
        (LogoutAllBrowserSessionsCommand, LogoutAllBrowserSessionsHandler),
        (RevokeBrowserSessionCommand, RevokeBrowserSessionHandler),
        (ChangeBrowserPasswordCommand, ChangeBrowserPasswordHandler),
        (ManageProjectMembershipCommand, ManageProjectMembershipHandler),
    ),
    queries=(
        (AuthenticateIdentityTokenQuery, AuthenticateIdentityTokenHandler),
        (AuthenticateBrowserSessionQuery, AuthenticateBrowserSessionHandler),
        (ReadBrowserPrincipalQuery, ReadBrowserPrincipalHandler),
        (ReadBrowserCookiePolicyQuery, ReadBrowserCookiePolicyHandler),
        (ListBrowserSessionsQuery, ListBrowserSessionsHandler),
        (ListProjectMembersQuery, ListProjectMembersHandler),
    ),
    required_commands=(
        LoginBrowserSessionCommand,
        SelectBrowserProjectCommand,
        LogoutBrowserSessionCommand,
        LogoutAllBrowserSessionsCommand,
        RevokeBrowserSessionCommand,
        ChangeBrowserPasswordCommand,
        ManageProjectMembershipCommand,
    ),
    required_queries=(
        AuthenticateIdentityTokenQuery,
        AuthenticateBrowserSessionQuery,
        ReadBrowserPrincipalQuery,
        ReadBrowserCookiePolicyQuery,
        ListBrowserSessionsQuery,
        ListProjectMembersQuery,
    ),
)


class IdentityModuleDispatcher(ModuleDispatcher):
    def __init__(self, container: AsyncContainer) -> None:
        super().__init__(IDENTITY_HANDLER_REGISTRY, container.get)
