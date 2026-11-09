from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RetryDeliveryStepCommand:
    workload_id: UUID
    step_id: UUID

    @property
    def application_id(self) -> UUID:
        return self.workload_id
