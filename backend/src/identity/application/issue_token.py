import re
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from identity.application.dto import IssueTokenCommand
from identity.application.ports import (
    CredentialDelivery,
    TokenGenerator,
    TokenHasher,
    TransactionFactory,
)
from identity.domain.credentials import require_active_identity
from identity.domain.errors import IdentityValidationError
from identity.domain.records import AuditRecord

_NAME = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


class IssueToken:
    def __init__(
        self,
        transactions: TransactionFactory,
        hasher: TokenHasher,
        generator: TokenGenerator,
        clock: Callable[[], datetime],
        allowed_scopes: tuple[str, ...],
        default_scopes: tuple[str, ...],
    ) -> None:
        self.transactions = transactions
        self.hasher = hasher
        self.generator = generator
        self.clock = clock
        self.allowed_scopes = frozenset(allowed_scopes)
        self.default_scopes = default_scopes

    def execute(self, command: IssueTokenCommand, delivery: CredentialDelivery) -> UUID:
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
        token = self.generator.generate()
        receipt = None
        try:
            with self.transactions() as tx:
                identity = tx.ensure_identity(
                    user_name=command.user_name,
                    project_name=command.project_name,
                    new_role="developer",
                )
                require_active_identity(identity)
                token_id = tx.add_token(
                    user_id=identity.user_id,
                    project_id=identity.project_id,
                    digest=self.hasher.digest(token),
                    scopes=scopes,
                    expires_at=now + timedelta(hours=command.hours),
                    created_at=now,
                )
                tx.append_audit(
                    AuditRecord(
                        actor_id=identity.user_id,
                        project_id=identity.project_id,
                        action="token_issued",
                        outcome="succeeded",
                        request_id=token_id,
                    )
                )
                receipt = delivery.write_new(token)
            return token_id
        except BaseException as primary:
            if receipt is not None:
                try:
                    receipt.remove_owned()
                except BaseException:
                    try:
                        primary.add_note(
                            "Credential cleanup failed; the original failure was preserved."
                        )
                    except AttributeError:
                        pass
            raise
