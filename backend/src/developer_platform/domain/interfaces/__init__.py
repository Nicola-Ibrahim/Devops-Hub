"""Domain persistence interfaces; technical provider ports stay in application."""

from developer_platform.domain.interfaces.application_repository import ApplicationRepository
from developer_platform.domain.interfaces.project_repository import ProjectRepository
from developer_platform.domain.interfaces.resource_repository import ResourceRepository
from developer_platform.domain.interfaces.resource_request_repository import (
    ResourceRequestRepository,
)

__all__ = [
    "ApplicationRepository",
    "ProjectRepository",
    "ResourceRepository",
    "ResourceRequestRepository",
]
