from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from identity.application.select_active_project.command import SelectActiveProjectCommand
from identity.application.shared.session_security import (
    AuthorizeBrowserMutationCommand,
    AuthorizeBrowserMutationHandler,
)
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.interfaces.session_repository import SessionRepository
from identity.domain.records import SessionPrincipal

Clock = Callable[[], datetime]

DigestSecret = Callable[[str], str]

GenerateSecret = Callable[[], str]


class SelectActiveProjectHandler:
    def __init__(
        self,
        repository: SessionRepository,
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

    async def execute(self, command: SelectActiveProjectCommand) -> SessionPrincipal:
        await self.authorize.execute(
            AuthorizeBrowserMutationCommand(
                command.session_token, command.csrf_token, command.origin
            )
        )
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
