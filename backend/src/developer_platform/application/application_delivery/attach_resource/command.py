from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceAttachmentCommand:
    template_id: str
    version: str
    target_id: str
    size_id: str
    ttl_seconds: int
