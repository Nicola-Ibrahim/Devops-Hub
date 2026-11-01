"""Stable values exposed to trusted host boundaries."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: UUID
    project_id: UUID
    token_id: UUID
    role: Literal["developer", "admin"]
    scopes: frozenset[str]
