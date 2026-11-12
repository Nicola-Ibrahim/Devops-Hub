# ruff: noqa: F401
"""Safe local adapters for approved templates and explicitly configured providers."""

import base64
import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from devops_hub.platform.application.workload_delivery.shared.models import (
    GeneratedFile,
    TemplateVersion,
)
from devops_hub.platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    ApprovedImageCatalog,
    RequestFingerprint,
    TemplateCatalog,
    WebhookSignatureVerifier,
)


class HmacGitHubWebhookVerifier(WebhookSignatureVerifier):
    """Authenticates GitHub's raw-body signature before parsing its JSON payload."""

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("GitHub webhook secret must not be empty")
        self._secret = secret.encode()

    def verify(self, raw_body: bytes, signature: str | None) -> tuple[dict[str, object], str]:
        if not signature or not signature.startswith("sha256="):
            raise ApplicationDeliveryFailure("webhook_signature_invalid", retryable=False)
        expected = hmac.new(self._secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature[7:], expected):
            raise ApplicationDeliveryFailure("webhook_signature_invalid", retryable=False)
        try:
            payload = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError):
            raise ApplicationDeliveryFailure("webhook_payload_invalid", retryable=False) from None
        if not isinstance(payload, dict):
            raise ApplicationDeliveryFailure("webhook_payload_invalid", retryable=False)
        return payload, hashlib.sha256(raw_body).hexdigest()
