"""Developer-visible temporary resource name."""

from dataclasses import dataclass

from developer_platform.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class ResourceName:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized or len(normalized) > 100:
            raise DomainError("Resource name must contain between 1 and 100 characters.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
