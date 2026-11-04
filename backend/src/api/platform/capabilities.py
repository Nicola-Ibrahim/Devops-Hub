"""HTTP capabilities implemented at the outer composition boundary."""

from typing import Protocol
from uuid import UUID

from api.credentials import RequestIdentity
from api.platform.schemas import (
    AcceptedOperation,
    ActivityPage,
    ConnectionView,
    OperationView,
    ProjectRegistrationView,
    RenewRequest,
    ResourcePage,
    ResourceRequest,
    ResourceView,
)


class PlatformRequestQueries(Protocol):
    async def projects(self, token: RequestIdentity) -> list[ProjectRegistrationView]: ...

    async def request_database(
        self, token: RequestIdentity, command: ResourceRequest, key: str
    ) -> AcceptedOperation: ...
    async def project(
        self, token: RequestIdentity, project_id: UUID
    ) -> ProjectRegistrationView: ...
    async def resources(
        self, token: RequestIdentity, project_id: UUID, after: UUID | None, limit: int
    ) -> ResourcePage: ...
    async def resource(self, token: RequestIdentity, resource_id: UUID) -> ResourceView: ...
    async def operation(self, token: RequestIdentity, operation_id: UUID) -> OperationView: ...

    async def renew(
        self, token: RequestIdentity, resource_id: UUID, command: RenewRequest
    ) -> ResourceView: ...
    async def delete(self, token: RequestIdentity, resource_id: UUID) -> AcceptedOperation: ...
    async def connection(self, token: RequestIdentity, resource_id: UUID) -> ConnectionView: ...
    async def activity(self, token: RequestIdentity, project_id: UUID) -> ActivityPage: ...
