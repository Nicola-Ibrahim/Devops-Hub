from identity.application.authenticate_session.handler import AuthenticateSessionHandler
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.list_sessions.query import ListSessionsQuery
from identity.application.list_sessions.result import SessionDetails


class ListSessionsHandler:
    def __init__(self, authenticate: AuthenticateSessionHandler) -> None:
        self.authenticate = authenticate

    async def execute(self, command: ListSessionsQuery) -> tuple[SessionDetails, ...]:
        principal = await self.authenticate.execute(AuthenticateSessionQuery(command.session_token))
        sessions = await self.authenticate.repository.list_sessions(
            principal.user_id, principal.session_id, self.authenticate.clock()
        )

        return tuple(
            SessionDetails(
                session.id,
                session.created_at,
                session.last_seen_at,
                session.expiry.idle_at,
                session.expiry.absolute_at,
                session.id == principal.session_id,
            )
            for session in sessions
        )
