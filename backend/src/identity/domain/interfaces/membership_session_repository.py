"""Combined capabilities for session-authorized membership administration."""

from typing import Protocol

from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.interfaces.session_repository import BrowserSessionRepository


class MembershipSessionRepository(ProjectMembershipRepository, BrowserSessionRepository, Protocol):
    """Membership persistence plus session authorization for one use case."""
