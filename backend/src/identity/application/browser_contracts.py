"""Compatibility imports for browser HTTP contracts.

Identity-owned records and persistence protocols live in ``identity.domain``.
"""

from identity.application.ports import PasswordHasher
from identity.domain.browser_identity import (
    BrowserAccount,
    BrowserIdentityRepository,
    BrowserLogin,
    BrowserMembership,
    BrowserPrincipal,
    BrowserProjectMember,
    BrowserSession,
)

__all__ = [
    "BrowserAccount",
    "BrowserIdentityRepository",
    "BrowserLogin",
    "BrowserMembership",
    "BrowserPrincipal",
    "BrowserProjectMember",
    "BrowserSession",
    "PasswordHasher",
]
