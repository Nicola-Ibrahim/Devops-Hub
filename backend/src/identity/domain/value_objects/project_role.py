"""A role a user holds within one project."""

from dataclasses import dataclass
from typing import Literal

from identity.domain.errors import IdentityValidationError

ProjectRoleValue = Literal["developer", "admin"]


@dataclass(frozen=True, slots=True)
class ProjectRole:
    value: ProjectRoleValue

    @classmethod
    def parse(cls, value: str) -> "ProjectRole":
        if value not in {"developer", "admin"}:
            raise IdentityValidationError("Unknown project role")
        return cls(value)  # type: ignore[arg-type]
