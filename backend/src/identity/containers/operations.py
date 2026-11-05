"""Typed execution adapters: transaction and delivery completion live outside use cases."""

from uuid import UUID

from identity.application.dto import IssueTokenCommand, PreparedApiToken
from identity.application.errors import IdentityUnavailable
from identity.application.issue_token import IssueApiToken
from identity.application.ports import CredentialDelivery, CredentialReceipt
from identity.application.revoke_token import RevokeApiToken
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork


class IssueApiTokenToFile:
    def __init__(self, inner: IssueApiToken, unit: SqlAlchemyUnitOfWork) -> None:
        self.inner = inner
        self.unit = unit

    async def execute(self, command: IssueTokenCommand, delivery: CredentialDelivery) -> UUID:
        receipt: CredentialReceipt | None = None

        def deliver(prepared: PreparedApiToken) -> UUID:
            nonlocal receipt
            receipt = delivery.write_new(prepared.secret)
            return prepared.token_id

        try:
            return await self.unit.run(lambda: self.inner.execute(command), deliver)
        except BaseException as primary:
            if receipt is not None and not self.unit.committed:
                try:
                    receipt.remove_owned()
                except BaseException:
                    primary.add_note(
                        "Credential cleanup failed; the original failure was preserved."
                    )
            if isinstance(primary, DatabaseUnavailable):
                raise IdentityUnavailable() from primary
            raise


class RevokeApiTokenCommand:
    def __init__(self, inner: RevokeApiToken, unit: SqlAlchemyUnitOfWork) -> None:
        self.inner = inner
        self.unit = unit

    async def execute(self, token_id: UUID) -> bool:
        try:
            return await self.unit.run(lambda: self.inner.execute(token_id), lambda value: value)
        except DatabaseUnavailable as error:
            raise IdentityUnavailable() from error
