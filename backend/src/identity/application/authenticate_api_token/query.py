from dataclasses import dataclass, field

from identity.contracts import AuthenticatedPrincipal
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class AuthenticateApiTokenQuery(Query[AuthenticatedPrincipal]):
    token: str | None = field(repr=False)
