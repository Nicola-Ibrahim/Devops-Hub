from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListWorkloadsQuery:
    pass


@dataclass(frozen=True)
class GetWorkloadQuery:
    workload_id: UUID


@dataclass(frozen=True)
class DeploymentHistoryQuery:
    workload_id: UUID
