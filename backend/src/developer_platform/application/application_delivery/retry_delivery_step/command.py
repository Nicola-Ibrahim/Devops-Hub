from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RetryDeliveryStepCommand:
    application_id: UUID
    step_id: UUID
