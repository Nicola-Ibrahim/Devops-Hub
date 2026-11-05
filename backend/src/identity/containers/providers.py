"""Declarative bindings; this is the only layer selecting concrete implementations."""

from dataclasses import dataclass

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.identity.browser import BrowserIdentityOperations
from identity.application.authenticate import AuthenticateApiToken
from identity.application.issue_token import IssueApiToken
from identity.application.ports import TokenGenerator, TokenHasher
from identity.application.revoke_token import RevokeApiToken
from identity.containers.operations import (
    IssueApiTokenToFile,
    RevokeApiTokenCommand,
)
from identity.domain.api_tokens import ApiTokenRepository
from identity.domain.project_access import ProjectAccessDirectory
from identity.infra.browser_operations import BrowserIdentityService
from identity.infra.persistence.project_directory import SQLAlchemyProjectAccessDirectory
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from identity.infra.tokens import PepperedTokenHasher, SecureTokenGenerator
from shared.infra.clock import Clock
from shared.infra.settings import Settings


@dataclass(frozen=True)
class IdentityTokenScopePolicy:
    scopes: tuple[str, ...]


class IdentityProvider(Provider):
    @provide(scope=Scope.APP)
    def browser(
        self, sessions: async_sessionmaker[AsyncSession], clock: Clock, settings: Settings
    ) -> BrowserIdentityOperations:
        return BrowserIdentityService(
            sessions,
            clock,
            settings.cookie_secure,
            settings.browser_allowed_origins,
            settings.token_pepper.get_secret_value(),
        )

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
    authenticate = provide(AuthenticateApiToken, scope=Scope.REQUEST)
    revoke = provide(RevokeApiToken, scope=Scope.REQUEST)
    revoke_command = provide(RevokeApiTokenCommand, scope=Scope.REQUEST)
    issue_command = provide(IssueApiTokenToFile, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def issue(
        self,
        repository: ApiTokenRepository,
        hasher: TokenHasher,
        generator: TokenGenerator,
        clock: Clock,
        scope_policy: IdentityTokenScopePolicy,
    ) -> IssueApiToken:
        return IssueApiToken(
            repository, hasher, generator, clock, scope_policy.scopes, scope_policy.scopes
        )
