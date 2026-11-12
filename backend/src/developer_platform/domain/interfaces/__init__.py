"""Domain persistence interfaces; technical provider ports stay in application."""

from developer_platform.domain.interfaces.application_repository import ApplicationRepository

__all__ = [
    "ApplicationRepository",
]
