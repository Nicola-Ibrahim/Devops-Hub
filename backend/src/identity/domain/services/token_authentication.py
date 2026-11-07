"""Domain policy for authenticating an API token from a persisted snapshot."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from identity.domain.errors import AuthenticationRejected


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    user_id: UUID
    project_id: UUID
    token_id: UUID
    role: Literal["developer", "admin"]
    scopes: frozenset[str]


def authenticate_token(
    *,
    token_id: UUID | None,
    user_id: UUID | None,
    project_id: UUID | None,
    role: str | None,
    scopes: tuple[str, ...],
    user_active: bool,
    expires_at: datetime | None,
    revoked_at: datetime | None,
    now: datetime,
) -> AuthenticatedIdentity:
    if (
        token_id is None
        or user_id is None
        or project_id is None
        or expires_at is None
        or not user_active
        or revoked_at is not None
        or expires_at <= now
        or role not in {"developer", "admin"}
    ):
        raise AuthenticationRejected()
    return AuthenticatedIdentity(
        user_id=user_id,
        project_id=project_id,
        token_id=token_id,
        role=role,  # type: ignore[arg-type]
        scopes=frozenset(scopes),
    )
