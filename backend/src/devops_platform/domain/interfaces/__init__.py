"""Domain persistence interfaces; technical provider ports stay in application."""

from devops_platform.domain.interfaces.application_repository import ApplicationRepository

__all__ = [
    "ApplicationRepository",
]
