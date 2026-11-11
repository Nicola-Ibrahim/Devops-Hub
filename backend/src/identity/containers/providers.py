"""Declarative bindings; this is the only layer selecting concrete implementations."""

from dataclasses import dataclass

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity.application.authenticate_api_token.handler import AuthenticateApiTokenHandler
from identity.application.issue_api_token.handler import IssueApiTokenHandler
from identity.application.revoke_api_token.handler import RevokeApiTokenHandler
from identity.application.shared.ports import TokenGenerator, TokenHasher
from identity.containers.module import (
    AuthenticateBrowserSessionHandler,
    AuthenticateIdentityTokenHandler,
    ChangeBrowserPasswordHandler,
    ListBrowserSessionsHandler,
    ListProjectMembersHandler,
    LoginBrowserSessionHandler,
    LogoutAllBrowserSessionsHandler,
    LogoutBrowserSessionHandler,
    ManageProjectMembershipHandler,
    ReadBrowserCookiePolicyHandler,
    ReadBrowserPrincipalHandler,
    RevokeBrowserSessionHandler,
    SelectBrowserProjectHandler,
)
from identity.containers.operations import (
    IssueApiTokenToFile,
    RevokeApiTokenOperation,
)
from identity.domain.api_tokens import ApiTokenRepository
from identity.domain.project_access import ProjectAccessDirectory
from identity.infra.browser_operations import BrowserIdentityService
from identity.infra.persistence.project_directory import SQLAlchemyProjectAccessDirectory
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from identity.infra.token_authentication_host import TokenAuthenticationHost
from identity.infra.tokens import PepperedTokenHasher, SecureTokenGenerator
from shared.infra.clock import Clock
from shared.infra.settings import Settings


@dataclass(frozen=True)
class IdentityTokenScopePolicy:
    scopes: tuple[str, ...]


class IdentityProvider(Provider):
    token_authentication_host = provide(TokenAuthenticationHost, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def browser(
        self, sessions: async_sessionmaker[AsyncSession], clock: Clock, settings: Settings
    ) -> BrowserIdentityService:
        return BrowserIdentityService(
            sessions,
            clock,
            settings.cookie_secure,
            settings.browser_allowed_origins,
            settings.token_pepper.get_secret_value(),
        )

    authenticate_identity_token = provide(AuthenticateIdentityTokenHandler, scope=Scope.REQUEST)
    authenticate_browser_session = provide(AuthenticateBrowserSessionHandler, scope=Scope.REQUEST)
    login_browser_session = provide(LoginBrowserSessionHandler, scope=Scope.REQUEST)
    read_browser_principal = provide(ReadBrowserPrincipalHandler, scope=Scope.REQUEST)
    read_browser_cookie_policy = provide(ReadBrowserCookiePolicyHandler, scope=Scope.REQUEST)
    select_browser_project = provide(SelectBrowserProjectHandler, scope=Scope.REQUEST)
    logout_browser_session = provide(LogoutBrowserSessionHandler, scope=Scope.REQUEST)
    logout_all_browser_sessions = provide(LogoutAllBrowserSessionsHandler, scope=Scope.REQUEST)
    list_browser_sessions = provide(ListBrowserSessionsHandler, scope=Scope.REQUEST)
    revoke_browser_session = provide(RevokeBrowserSessionHandler, scope=Scope.REQUEST)
    change_browser_password = provide(ChangeBrowserPasswordHandler, scope=Scope.REQUEST)
    list_project_members = provide(ListProjectMembersHandler, scope=Scope.REQUEST)
    manage_project_membership = provide(ManageProjectMembershipHandler, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def hasher(self, settings: Settings) -> TokenHasher:
        return PepperedTokenHasher(settings.token_pepper.get_secret_value())

    @provide(scope=Scope.APP)
    def generator(self) -> TokenGenerator:
        return SecureTokenGenerator()

    project_directory = provide(
        SQLAlchemyProjectAccessDirectory, provides=ProjectAccessDirectory, scope=Scope.REQUEST
    )

    repository = provide(
        SQLAlchemyApiTokenRepository, provides=ApiTokenRepository, scope=Scope.REQUEST
    )
    authenticate = provide(AuthenticateApiTokenHandler, scope=Scope.REQUEST)
    revoke = provide(RevokeApiTokenHandler, scope=Scope.REQUEST)
    revoke_command = provide(RevokeApiTokenOperation, scope=Scope.REQUEST)
    issue_command = provide(IssueApiTokenToFile, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def issue(
        self,
        repository: ApiTokenRepository,
        hasher: TokenHasher,
        generator: TokenGenerator,
        clock: Clock,
        scope_policy: IdentityTokenScopePolicy,
    ) -> IssueApiTokenHandler:
        return IssueApiTokenHandler(
            repository, hasher, generator, clock, scope_policy.scopes, scope_policy.scopes
        )
