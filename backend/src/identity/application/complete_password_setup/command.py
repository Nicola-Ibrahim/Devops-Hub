from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CompletePasswordSetupCommand:
    secret: str = field(repr=False)
    new_password: str = field(repr=False)
