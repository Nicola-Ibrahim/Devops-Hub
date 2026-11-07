"""Repository capabilities owned by the identity domain."""

from identity.domain.interfaces.account_repository import BrowserAccountRepository
from identity.domain.interfaces.browser_identity_repository import BrowserIdentityRepository
from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.interfaces.membership_session_repository import MembershipSessionRepository
from identity.domain.interfaces.password_setup_repository import PasswordSetupRepository
from identity.domain.interfaces.session_repository import BrowserSessionRepository

__all__ = [
    "BrowserAccountRepository",
    "BrowserIdentityRepository",
    "BrowserSessionRepository",
    "MembershipSessionRepository",
    "PasswordSetupRepository",
    "ProjectMembershipRepository",
]
