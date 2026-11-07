"""Compatibility composition of browser account/session/membership capabilities."""

from typing import Protocol

from identity.domain.interfaces.account_repository import BrowserAccountRepository
from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.interfaces.password_setup_repository import PasswordSetupRepository
from identity.domain.interfaces.session_repository import BrowserSessionRepository


class BrowserIdentityRepository(
    BrowserAccountRepository,
    BrowserSessionRepository,
    ProjectMembershipRepository,
    PasswordSetupRepository,
    Protocol,
):
    """Legacy aggregate protocol retained for the SQL adapter during migration."""
