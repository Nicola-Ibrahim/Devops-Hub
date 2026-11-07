from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AuthenticateApiTokenQuery:
    token: str | None = field(repr=False)
