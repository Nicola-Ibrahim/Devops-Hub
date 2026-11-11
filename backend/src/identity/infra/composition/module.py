"""Explicit identity message registration and lazy module dispatch."""

from dishka import AsyncContainer

from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.browser_login.command import (
    ChangeBrowserPasswordCommand,
    LoginBrowserSessionCommand,
)
from identity.application.browser_sessions.command import (
    LogoutAllBrowserSessionsCommand,
    LogoutBrowserSessionCommand,
    RevokeBrowserSessionCommand,
    RotateBrowserCsrfCommand,
    SelectBrowserProjectCommand,
)
from identity.application.browser_sessions.query import (
    AuthenticateBrowserSessionQuery,
    ListBrowserSessionsQuery,
)
from identity.application.project_memberships.command import ManageProjectMembershipCommand
from identity.application.project_memberships.query import ListProjectMembersQuery
from identity.infra.composition.handlers import (
    AuthenticateBrowserSessionHandler,
    AuthenticateIdentityTokenHandler,
    ChangeBrowserPasswordHandler,
    ListBrowserSessionsHandler,
    ListProjectMembersHandler,
    LoginBrowserSessionHandler,
    LogoutAllBrowserSessionsHandler,
    LogoutBrowserSessionHandler,
    ManageProjectMembershipHandler,
    RevokeBrowserSessionHandler,
    RotateBrowserCsrfHandler,
    SelectBrowserProjectHandler,
)
from shared.dispatch import HandlerRegistry, ModuleDispatcher

IDENTITY_HANDLER_REGISTRY = HandlerRegistry(
    commands=(
        (LoginBrowserSessionCommand, LoginBrowserSessionHandler),
        (RotateBrowserCsrfCommand, RotateBrowserCsrfHandler),
        (SelectBrowserProjectCommand, SelectBrowserProjectHandler),
        (LogoutBrowserSessionCommand, LogoutBrowserSessionHandler),
        (LogoutAllBrowserSessionsCommand, LogoutAllBrowserSessionsHandler),
        (RevokeBrowserSessionCommand, RevokeBrowserSessionHandler),
        (ChangeBrowserPasswordCommand, ChangeBrowserPasswordHandler),
        (ManageProjectMembershipCommand, ManageProjectMembershipHandler),
    ),
    queries=(
        (AuthenticateApiTokenQuery, AuthenticateIdentityTokenHandler),
        (AuthenticateBrowserSessionQuery, AuthenticateBrowserSessionHandler),
        (ListBrowserSessionsQuery, ListBrowserSessionsHandler),
        (ListProjectMembersQuery, ListProjectMembersHandler),
    ),
    required_commands=(
        LoginBrowserSessionCommand,
        RotateBrowserCsrfCommand,
        SelectBrowserProjectCommand,
        LogoutBrowserSessionCommand,
        LogoutAllBrowserSessionsCommand,
        RevokeBrowserSessionCommand,
        ChangeBrowserPasswordCommand,
        ManageProjectMembershipCommand,
    ),
    required_queries=(
        AuthenticateApiTokenQuery,
        AuthenticateBrowserSessionQuery,
        ListBrowserSessionsQuery,
        ListProjectMembersQuery,
    ),
)


class IdentityModuleDispatcher(ModuleDispatcher):
    def __init__(self, container: AsyncContainer) -> None:
        super().__init__(IDENTITY_HANDLER_REGISTRY, container.get)
