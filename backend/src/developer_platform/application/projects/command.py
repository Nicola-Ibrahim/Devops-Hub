from dataclasses import dataclass


@dataclass(frozen=True)
class RegisterProjectCommand:
    name: str
    owning_team: str
    repository: str
    environments: tuple[str, ...]
