"""Capacity admission decision after repositories lock quota snapshots."""

from dataclasses import dataclass

from developer_platform.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class CapacitySnapshot:
    resources: int
    cpu_millis: int
    memory_bytes: int
    storage_bytes: int


class ResourceAdmissionPolicy:
    @staticmethod
    def require_capacity(
        usage: CapacitySnapshot, limit: CapacitySnapshot, requested: CapacitySnapshot
    ) -> None:
        values = (
            (usage.resources, limit.resources, requested.resources),
            (usage.cpu_millis, limit.cpu_millis, requested.cpu_millis),
            (usage.memory_bytes, limit.memory_bytes, requested.memory_bytes),
            (usage.storage_bytes, limit.storage_bytes, requested.storage_bytes),
        )
        if any(current + addition > maximum for current, maximum, addition in values):
            raise DomainError("Resource quota would be exceeded.")
