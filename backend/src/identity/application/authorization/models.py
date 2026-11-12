"""Typed input and output for policy decisions."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    subject_id: UUID
    action: str
    resource_kind: str
    resource_id: UUID | None = None
    project_id: UUID | None = None
    subject_project_id: UUID | None = None
    role: str | None = None
    scopes: tuple[str, ...] = ()
    owner_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    policy_revision: str | None = None
