import re
from collections.abc import Callable
from datetime import datetime, timedelta

from identity.application.dto import IssueTokenCommand, PreparedApiToken
from identity.application.ports import TokenGenerator, TokenHasher
from identity.domain.api_tokens import ApiTokenRepository
from identity.domain.credentials import require_active_project_member
from identity.domain.errors import IdentityValidationError
from identity.domain.records import ApiTokenAuditEvent

_NAME = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


class IssueApiToken:
    def __init__(
        self,
        repository: ApiTokenRepository,
        hasher: TokenHasher,
        generator: TokenGenerator,
        clock: Callable[[], datetime],
        allowed_scopes: tuple[str, ...],
        default_scopes: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.hasher = hasher
        self.generator = generator
        self.clock = clock
        self.allowed_scopes = frozenset(allowed_scopes)
        self.default_scopes = default_scopes

    async def execute(self, command: IssueTokenCommand) -> PreparedApiToken:
        if not _NAME.fullmatch(command.user_name) or not _NAME.fullmatch(command.project_name):
            raise IdentityValidationError(
                "Names must contain only letters, numbers, underscores and hyphens"
            )
        if not 1 <= command.hours <= 720:
            raise IdentityValidationError("Token duration must be between 1 and 720 hours")
        scopes = self.default_scopes if command.scopes is None else command.scopes
        if not scopes or not set(scopes) <= self.allowed_scopes:
            raise IdentityValidationError("Invalid token scopes")

        now = self.clock()
        secret = self.generator.generate()
        identity = await self.repository.ensure_developer_membership(
            user_name=command.user_name,
            project_name=command.project_name,
            new_role="developer",
        )
        require_active_project_member(identity)
        token_id = await self.repository.insert_api_token(
            user_id=identity.user_id,
            project_id=identity.project_id,
            digest=self.hasher.digest(secret),
            scopes=scopes,
            expires_at=now + timedelta(hours=command.hours),
            created_at=now,
        )
        await self.repository.record_token_audit(
            ApiTokenAuditEvent(
                actor_id=identity.user_id,
                project_id=identity.project_id,
                action="token_issued",
                outcome="succeeded",
                request_id=token_id,
            )
        )
        return PreparedApiToken(token_id, secret)
