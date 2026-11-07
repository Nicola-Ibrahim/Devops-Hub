"""Normalized internal user name."""

import re
from dataclasses import dataclass

from identity.domain.errors import IdentityValidationError

_USER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")


@dataclass(frozen=True, slots=True)
class UserName:
    value: str

    @classmethod
    def parse(cls, value: str) -> "UserName":
        normalized = value.strip().lower()
        if not _USER_NAME.fullmatch(normalized):
            raise IdentityValidationError(
                "User name must use letters, numbers, dots, underscores or hyphens"
            )
        return cls(normalized)
