"""Repository capabilities owned by the identity domain."""

from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.interfaces.membership_session_repository import MembershipSessionRepository
from identity.domain.interfaces.password_setup_repository import PasswordSetupRepository
from identity.domain.interfaces.session_repository import SessionRepository
from identity.domain.interfaces.user_repository import UserRepository

__all__ = [
    "UserRepository",
    "SessionRepository",
    "MembershipSessionRepository",
    "PasswordSetupRepository",
    "ProjectMembershipRepository",
]
