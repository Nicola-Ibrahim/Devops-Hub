"""Approved API token capabilities."""

from dataclasses import dataclass

from identity.domain.errors import IdentityValidationError


@dataclass(frozen=True, slots=True)
class TokenScopes:
    values: tuple[str, ...]

    @classmethod
    def select(
        cls,
        requested: tuple[str, ...] | None,
        *,
        allowed: tuple[str, ...],
        defaults: tuple[str, ...],
    ) -> "TokenScopes":
        values = defaults if requested is None else requested
        if not values or not set(values) <= set(allowed):
            raise IdentityValidationError("Invalid token scopes")
        return cls(tuple(values))
