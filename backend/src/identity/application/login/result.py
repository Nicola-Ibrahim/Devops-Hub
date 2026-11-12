from dataclasses import dataclass, field
from datetime import datetime

from identity.domain.records import SessionPrincipal


@dataclass(frozen=True)
class LoginResult:
    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    principal: SessionPrincipal
    absolute_expires_at: datetime
