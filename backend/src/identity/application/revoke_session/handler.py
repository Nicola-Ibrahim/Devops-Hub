from identity.application.revoke_session.command import RevokeSessionCommand
from identity.application.shared.session_security import (
    AuthorizeBrowserMutationCommand,
    AuthorizeBrowserMutationHandler,
)


class RevokeSessionHandler:
    def __init__(self, authorizer: AuthorizeBrowserMutationHandler) -> None:
        self.authorizer = authorizer

    async def execute(self, command: RevokeSessionCommand) -> bool:
        principal = await self.authorizer.execute(
            AuthorizeBrowserMutationCommand(
                command.session_token, command.csrf_token, command.origin
            )
        )
        return await self.authorizer.repository.revoke_session(
            principal.user_id, command.session_id, self.authorizer.clock()
        )
