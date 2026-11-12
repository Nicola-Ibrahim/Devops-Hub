"""Declarative bindings; this is the only layer selecting concrete implementations."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from dishka import AsyncContainer, Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity.application.authenticate_api_token.handler import AuthenticateApiTokenHandler
from identity.application.authorization.port import AuthorizationDecisionPort
from identity.application.issue_api_token.handler import IssueApiTokenHandler
from identity.application.module import IdentityModule
from identity.application.revoke_api_token.handler import RevokeApiTokenHandler
from identity.application.shared.ports import TokenGenerator, TokenHasher
from identity.domain.interfaces.api_token_repository import ApiTokenRepository
from identity.domain.interfaces.project_access_directory import ProjectAccessDirectory
from identity.infra.authorization.opa import OpaAuthorizationClient
from identity.infra.composition.module import IdentityModuleDispatcher
from identity.infra.hosts.api_token_authentication import TokenAuthenticationHost
from identity.infra.hosts.api_token_operations import (
    IssueApiTokenToFile,
    RevokeApiTokenOperation,
)
from identity.infra.hosts.identity_sessions import BrowserIdentityService
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
from identity.infra.persistence.project_directory import SQLAlchemyProjectAccessDirectory
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from identity.infra.security.tokens import PepperedTokenHasher, SecureTokenGenerator
from shared.infra.clock import Clock
from shared.infra.settings import Settings


@dataclass(frozen=True, slots=True)
class IdentityTokenScopePolicy:
    scopes: tuple[str, ...]


class IdentityProvider(Provider):
    token_authentication_host = provide(TokenAuthenticationHost, scope=Scope.APP)

    @provide(scope=Scope.REQUEST)
    def identity_module(self, container: AsyncContainer) -> IdentityModule:
        return IdentityModuleDispatcher(container)

    @provide(scope=Scope.APP)
    async def opa_http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(trust_env=False) as client:
            yield client

    @provide(scope=Scope.REQUEST, provides=AuthorizationDecisionPort)
    def authorization_decisions(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> OpaAuthorizationClient:
        return OpaAuthorizationClient(settings.opa_url, client)

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
    authenticate_browser_session = provide(AuthenticateSessionHandler, scope=Scope.REQUEST)
    login_browser_session = provide(LoginHandler, scope=Scope.REQUEST)
    rotate_browser_csrf = provide(RotateCsrfHandler, scope=Scope.REQUEST)
    select_browser_project = provide(SelectActiveProjectHandler, scope=Scope.REQUEST)
    logout_browser_session = provide(LogoutHandler, scope=Scope.REQUEST)
    logout_all_browser_sessions = provide(LogoutAllSessionsHandler, scope=Scope.REQUEST)
    list_browser_sessions = provide(ListSessionsHandler, scope=Scope.REQUEST)
    revoke_browser_session = provide(RevokeSessionHandler, scope=Scope.REQUEST)
    change_browser_password = provide(ChangePasswordHandler, scope=Scope.REQUEST)
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
