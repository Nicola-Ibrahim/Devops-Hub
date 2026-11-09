from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProcessGithubPreviewWebhookCommand:
    raw_body: bytes = field(repr=False)
    signature: str | None = field(repr=False)
    delivery_id: str
    event: str
