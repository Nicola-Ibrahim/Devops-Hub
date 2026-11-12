from identity.application.logout.command import LogoutCommand
from identity.application.shared.session_security import (
    AuthorizeBrowserMutationCommand,
    AuthorizeBrowserMutationHandler,
)


class LogoutHandler:
    def __init__(self, authorizer: AuthorizeBrowserMutationHandler) -> None:
        self.authorizer = authorizer

    async def execute(self, command: LogoutCommand) -> None:
        await self.authorizer.execute(
            AuthorizeBrowserMutationCommand(
                command.session_token, command.csrf_token, command.origin
            )
        )
        await self.authorizer.repository.logout(
            self.authorizer.digest_secret(command.session_token), self.authorizer.clock()
        )
