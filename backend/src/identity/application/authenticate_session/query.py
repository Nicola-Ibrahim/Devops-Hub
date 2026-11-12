from dataclasses import dataclass, field
from uuid import UUID

from identity.domain.records import SessionPrincipal
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class AuthenticateSessionQuery(Query[SessionPrincipal]):
    session_token: str = field(repr=False)
    project_id: UUID | None = None
