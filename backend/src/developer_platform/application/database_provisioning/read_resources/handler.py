"""Read registered projects, resources, and operation projections."""

from developer_platform.application.database_provisioning.read_resources.port import (
    PlatformResourceReadRepository,
)
from developer_platform.application.database_provisioning.read_resources.query import (
    OperationDetails,
    ReadOperation,
    ReadProject,
    ReadProjects,
    ReadResource,
    ReadResources,
    ResourceDetails,
)
from developer_platform.application.projects.result import ProjectRegistrationDetails
from developer_platform.application.shared.errors import PlatformRequestError, resource_not_found


class ReadProjectHandler:
    def __init__(self, repository: PlatformResourceReadRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadProject) -> ProjectRegistrationDetails:
        project = await self.repository.find_project(query.project_id)
        if project is None:
            raise resource_not_found()
        return project


class ReadProjectsHandler:
    def __init__(self, repository: PlatformResourceReadRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadProjects) -> tuple[ProjectRegistrationDetails, ...]:
        results = []
        for access in query.accesses:
            project = await self.repository.find_project(access.project_id)
            if project is None:
                raise resource_not_found()
            results.append(project)
        return tuple(results)


class ReadResourcesHandler:
    def __init__(self, repository: PlatformResourceReadRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadResources) -> tuple[ResourceDetails, ...]:
        if not 1 <= query.limit <= 100:
            raise PlatformRequestError("invalid_page", "Page limit must be between 1 and 100", 422)
        return await self.repository.list_resources(query.project_id, query.after, query.limit)


class ReadResourceHandler:
    def __init__(self, repository: PlatformResourceReadRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadResource) -> ResourceDetails:
        resource = await self.repository.find_resource(query.access.project_id, query.resource_id)
        if resource is None:
            raise resource_not_found()
        return resource


class ReadOperationHandler:
    def __init__(self, repository: PlatformResourceReadRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadOperation) -> OperationDetails:
        operation = await self.repository.find_operation(
            query.access.project_id, query.operation_id
        )
        if operation is None:
            raise resource_not_found()
        return operation
