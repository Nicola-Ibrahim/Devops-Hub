"""Optimistic resource revision."""

from dataclasses import dataclass

from devops_hub.platform.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class ResourceRevision:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or self.value < 1:
            raise DomainError("Resource revision must be a positive integer.")
