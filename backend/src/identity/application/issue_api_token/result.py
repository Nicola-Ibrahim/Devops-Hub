from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PreparedApiToken:
    """Private completion result, never an HTTP inventory response."""

    token_id: UUID
    secret: str = field(repr=False)
