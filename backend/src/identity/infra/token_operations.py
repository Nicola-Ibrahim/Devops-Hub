"""Typed execution adapters: transaction and delivery completion live outside use cases."""

from uuid import UUID

from identity.application.issue_api_token.command import IssueApiTokenCommand
from identity.application.issue_api_token.handler import IssueApiTokenHandler
from identity.application.issue_api_token.result import PreparedApiToken
from identity.application.revoke_api_token.command import RevokeApiTokenCommand
from identity.application.revoke_api_token.handler import RevokeApiTokenHandler
from identity.application.shared.errors import IdentityUnavailable
from identity.application.shared.ports import CredentialDelivery, CredentialReceipt
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork


class IssueApiTokenToFile:
    def __init__(self, inner: IssueApiTokenHandler, unit: SqlAlchemyUnitOfWork) -> None:
        self.inner = inner
        self.unit = unit

    async def execute(self, command: IssueApiTokenCommand, delivery: CredentialDelivery) -> UUID:
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


class RevokeApiTokenOperation:
    def __init__(self, inner: RevokeApiTokenHandler, unit: SqlAlchemyUnitOfWork) -> None:
        self.inner = inner
        self.unit = unit

    async def execute(self, token_id: UUID) -> bool:
        try:
            return await self.unit.run(
                lambda: self.inner.execute(RevokeApiTokenCommand(token_id)), lambda value: value
            )
        except DatabaseUnavailable as error:
            raise IdentityUnavailable() from error
