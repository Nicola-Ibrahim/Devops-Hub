"""Authorized actor within a registered project."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccessContext:
    user_id: UUID
    project_id: UUID
    role: Literal["developer", "admin"]
    scopes: frozenset[str]
