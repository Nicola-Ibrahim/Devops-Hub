"""Operation HTTP response models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from api.core.schemas import Contract


class OperationView(Contract):
    id: UUID
    resource_id: UUID
    action: Literal["provision", "delete", "reconcile"]
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    attempts: int
    next_attempt_at: datetime
    error_code: str | None = None
