from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from identity.application.ports import TransactionFactory
from identity.domain.records import AuditRecord


class RevokeToken:
    def __init__(self, transactions: TransactionFactory, clock: Callable[[], datetime]) -> None:
        self.transactions = transactions
        self.clock = clock

    def execute(self, token_id: UUID) -> bool:
        with self.transactions() as tx:
            token = tx.find_token(token_id)
            if token is None:
                return False
            if token.revoked_at is None:
                tx.set_revoked(token_id, self.clock())
                tx.append_audit(
                    AuditRecord(
                        actor_id=token.user_id,
                        project_id=token.project_id,
                        action="token_revoked",
                        outcome="succeeded",
                        request_id=token.token_id,
                    )
                )
            return True
