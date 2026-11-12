from identity.application.logout_all_sessions.command import LogoutAllSessionsCommand
from identity.application.shared.session_security import (
    AuthorizeBrowserMutationCommand,
    AuthorizeBrowserMutationHandler,
)


class LogoutAllSessionsHandler:
    def __init__(self, authorizer: AuthorizeBrowserMutationHandler) -> None:
        self.authorizer = authorizer

    async def execute(self, command: LogoutAllSessionsCommand) -> int:
        principal = await self.authorizer.execute(
            AuthorizeBrowserMutationCommand(
                command.session_token, command.csrf_token, command.origin
            )
        )
        return await self.authorizer.repository.logout_all(
            principal.user_id, self.authorizer.clock()
        )
