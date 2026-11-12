from dataclasses import dataclass, field

from identity.application.list_sessions.result import SessionDetails
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class ListSessionsQuery(Query[tuple[SessionDetails, ...]]):
    session_token: str = field(repr=False)
