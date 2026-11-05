"""Application rules and DTO construction for internal browser identity."""

from datetime import datetime
from uuid import UUID

from identity.domain.browser_credentials import (
    normalize_user_name,
    session_expiry,
    validate_password,
)
from identity.domain.browser_identity import BrowserMembership, BrowserPrincipal
from identity.domain.errors import AuthenticationRejected


class BrowserIdentity:
    """Small use-case policy surface; persistence and transaction completion are ports/host work."""

    @staticmethod
    def login_name(value: str) -> str:
        return normalize_user_name(value)

    @staticmethod
    def password(value: str) -> None:
        validate_password(value)

    @staticmethod
    def expiry(now: datetime) -> tuple[datetime, datetime]:
        return session_expiry(now)

    @staticmethod
    def reject_login() -> None:
        raise AuthenticationRejected()


def principal_for_project(
    *,
    user_id: UUID,
    user_name: str,
    session_id: UUID,
    memberships: tuple[BrowserMembership, ...],
    project_id: UUID | None,
    csrf_token: str,
) -> BrowserPrincipal:
    membership = next((item for item in memberships if item.project_id == project_id), None)
    return BrowserPrincipal(
        user_id=user_id,
        user_name=user_name,
        session_id=session_id,
        project_id=membership.project_id if membership else None,
        project_name=membership.project_name if membership else None,
        role=membership.role if membership else None,
        scopes=("catalog:read", "resources:read", "resources:write", "connections:read")
        if membership
        else (),
        memberships=memberships,
        csrf_token=csrf_token,
    )
