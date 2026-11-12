"""Reachable provider endpoint without credentials."""

from dataclasses import dataclass

from devops_platform.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class ResourceEndpoint:
    host: str
    port: int

    def __post_init__(self) -> None:
        if not self.host or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise DomainError("Resource endpoint is invalid.")
