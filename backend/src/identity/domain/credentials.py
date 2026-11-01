from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from identity.contracts import AuthenticatedPrincipal
from identity.domain.errors import AuthenticationRejected, IdentityValidationError
from identity.domain.records import ProjectMembershipStatus


@dataclass(frozen=True)
class ApiTokenAuthenticationDetails:
    token_id: UUID
    user_id: UUID
    project_id: UUID
    role: str | None
    scopes: tuple[str, ...]
    user_active: bool
    expires_at: datetime
    revoked_at: datetime | None


def authenticate_api_token_credentials(
    snapshot: ApiTokenAuthenticationDetails | None, now: datetime
) -> AuthenticatedPrincipal:
    if (
        snapshot is None
        or not snapshot.user_active
        or snapshot.revoked_at is not None
        or snapshot.expires_at <= now
        or snapshot.role not in {"developer", "admin"}
    ):
        raise AuthenticationRejected()
    return AuthenticatedPrincipal(
        user_id=snapshot.user_id,
        project_id=snapshot.project_id,
        token_id=snapshot.token_id,
        role=snapshot.role,  # type: ignore[arg-type]
        scopes=frozenset(snapshot.scopes),
    )


def require_active_project_member(snapshot: ProjectMembershipStatus) -> None:
    if not snapshot.user_active:
        raise IdentityValidationError("Cannot issue a token for a disabled user")
