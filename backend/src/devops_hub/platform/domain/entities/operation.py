"""Durable resource operation entity."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

OperationAction = Literal["provision", "delete", "reconcile"]
OperationStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class ResourceOperation:
    id: UUID
    resource_id: UUID
    resource_revision: int
    action: OperationAction
    status: OperationStatus
    attempts: int
    next_attempt_at: datetime
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AcceptedResourceRequest:
    resource_id: UUID
    operation_id: UUID
