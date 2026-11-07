from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IssueApiTokenCommand:
    user_name: str
    project_name: str
    hours: int = 24
    scopes: tuple[str, ...] | None = None
