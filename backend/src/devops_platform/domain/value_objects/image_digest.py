"""Immutable application image digest."""

import re
from dataclasses import dataclass

from devops_platform.domain.errors import DomainError

_REPOSITORY_DIGEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,250}@sha256:[a-f0-9]{64}\Z")
_IMAGE_ID = re.compile(r"sha256:[a-f0-9]{64}\Z")


@dataclass(frozen=True, slots=True)
class ImageDigest:
    value: str

    def __post_init__(self) -> None:
        if not (_REPOSITORY_DIGEST.fullmatch(self.value) or _IMAGE_ID.fullmatch(self.value)):
            raise DomainError("Application image must be pinned by SHA-256 digest.")

    @property
    def is_local_image_id(self) -> bool:
        return bool(_IMAGE_ID.fullmatch(self.value))

    def __str__(self) -> str:
        return self.value
