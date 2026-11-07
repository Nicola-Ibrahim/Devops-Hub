from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from identity.domain.errors import IdentityValidationError
from identity.domain.records import ProjectMembershipStatus
from identity.domain.services.token_authentication import AuthenticatedIdentity, authenticate_token


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
) -> AuthenticatedIdentity:
    return authenticate_token(
        token_id=snapshot.token_id if snapshot else None,
        user_id=snapshot.user_id if snapshot else None,
        project_id=snapshot.project_id if snapshot else None,
        role=snapshot.role if snapshot else None,
        scopes=snapshot.scopes if snapshot else (),
        user_active=snapshot.user_active if snapshot else False,
        expires_at=snapshot.expires_at if snapshot else None,
        revoked_at=snapshot.revoked_at if snapshot else None,
        now=now,
    )


def require_active_project_member(snapshot: ProjectMembershipStatus) -> None:
    if not snapshot.user_active:
        raise IdentityValidationError("Cannot issue a token for a disabled user")
