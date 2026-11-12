"""Bounded client retry identity."""

import re
from dataclasses import dataclass

from devops_platform.domain.errors import DomainError

_KEY = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.value):
            raise DomainError("Idempotency key is invalid.")

    def __str__(self) -> str:
        return self.value
