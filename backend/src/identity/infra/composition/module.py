"""Explicit identity message registration and lazy module dispatch."""

from dishka import AsyncContainer

from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.change_password.command import ChangePasswordCommand
from identity.application.list_project_members.query import ListProjectMembersQuery
from identity.application.list_sessions.query import ListSessionsQuery
from identity.application.login.command import LoginCommand
from identity.application.logout.command import LogoutCommand
from identity.application.logout_all_sessions.command import LogoutAllSessionsCommand
from identity.application.manage_project_membership.command import ManageProjectMembershipCommand
from identity.application.revoke_session.command import RevokeSessionCommand
from identity.application.rotate_csrf.command import RotateCsrfCommand
from identity.application.select_active_project.command import SelectActiveProjectCommand
from identity.infra.hosts.module_handlers import (
    AuthenticateIdentityTokenHandler,
    AuthenticateSessionHandler,
    ChangePasswordHandler,
    ListProjectMembersHandler,
    ListSessionsHandler,
    LoginHandler,
    LogoutAllSessionsHandler,
    LogoutHandler,
    ManageProjectMembershipHandler,
    RevokeSessionHandler,
    RotateCsrfHandler,
    SelectActiveProjectHandler,
)
from shared.dispatch import HandlerRegistry, ModuleDispatcher

IDENTITY_HANDLER_REGISTRY = HandlerRegistry(
    commands=(
        (LoginCommand, LoginHandler),
        (RotateCsrfCommand, RotateCsrfHandler),
        (SelectActiveProjectCommand, SelectActiveProjectHandler),
        (LogoutCommand, LogoutHandler),
        (LogoutAllSessionsCommand, LogoutAllSessionsHandler),
        (RevokeSessionCommand, RevokeSessionHandler),
        (ChangePasswordCommand, ChangePasswordHandler),
        (ManageProjectMembershipCommand, ManageProjectMembershipHandler),
    ),
    queries=(
        (AuthenticateApiTokenQuery, AuthenticateIdentityTokenHandler),
        (AuthenticateSessionQuery, AuthenticateSessionHandler),
        (ListSessionsQuery, ListSessionsHandler),
        (ListProjectMembersQuery, ListProjectMembersHandler),
    ),
    required_commands=(
        LoginCommand,
        RotateCsrfCommand,
        SelectActiveProjectCommand,
        LogoutCommand,
        LogoutAllSessionsCommand,
        RevokeSessionCommand,
        ChangePasswordCommand,
        ManageProjectMembershipCommand,
    ),
    required_queries=(
        AuthenticateApiTokenQuery,
        AuthenticateSessionQuery,
        ListSessionsQuery,
        ListProjectMembersQuery,
    ),
)


class IdentityModuleDispatcher(ModuleDispatcher):
    def __init__(self, container: AsyncContainer) -> None:
        super().__init__(IDENTITY_HANDLER_REGISTRY, container.get)
