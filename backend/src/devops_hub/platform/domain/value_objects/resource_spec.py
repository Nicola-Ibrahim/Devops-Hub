"""Approved resource catalog selection."""

from dataclasses import dataclass

from devops_hub.platform.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    template_id: str
    version: str
    target_id: str
    size_id: str
    cpu_millis: int = 0
    memory_bytes: int = 0
    storage_bytes: int = 0
    max_lifetime_seconds: int = 86400
    storage_enforcement: str = "reservation_only"

    def __post_init__(self) -> None:
        if not all(
            value and len(value) <= 100
            for value in (self.template_id, self.version, self.target_id, self.size_id)
        ):
            raise DomainError("Resource specification is invalid.")
        if (
            any(
                isinstance(value, bool) or value < 0
                for value in (self.cpu_millis, self.memory_bytes, self.storage_bytes)
            )
            or self.max_lifetime_seconds <= 0
        ):
            raise DomainError("Resource capacity is invalid.")
