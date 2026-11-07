from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListApplicationsQuery:
    pass


@dataclass(frozen=True)
class GetApplicationQuery:
    application_id: UUID


@dataclass(frozen=True)
class DeploymentHistoryQuery:
    application_id: UUID
