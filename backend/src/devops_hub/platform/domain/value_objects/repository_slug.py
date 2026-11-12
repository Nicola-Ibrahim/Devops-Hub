"""Canonical owner/repository identity."""

import re
from dataclasses import dataclass

from devops_hub.platform.domain.errors import DomainError

_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")


@dataclass(frozen=True, slots=True)
class RepositorySlug:
    value: str

    def __post_init__(self) -> None:
        canonical = self.value.casefold()
        if not _REPOSITORY.fullmatch(self.value) or ".." in self.value:
            raise DomainError("Repository identity is invalid.")
        object.__setattr__(self, "value", canonical)

    def __str__(self) -> str:
        return self.value
