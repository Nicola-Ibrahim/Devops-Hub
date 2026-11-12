from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceSize:
    id: str
    cpu_millis: int
    memory_bytes: int
    storage_bytes: int
    storage_enforcement: str = "reservation_only"


@dataclass(frozen=True)
class PostgresOption:
    template_id: str = "postgres"
    version: str = "16"
    target_id: str = "local"
    size: ResourceSize = ResourceSize("small", 500, 536870912, 1073741824)
    max_lifetime_seconds: int = 86400
    requestable: bool = False
    unavailable_reason: str | None = "provider_not_implemented"
