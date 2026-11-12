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

from devops_platform.application.workload_delivery.shared.models import (
    GeneratedFile,
    TemplateVersion,
)
from devops_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    ApprovedImageCatalog,
    RequestFingerprint,
    TemplateCatalog,
    WebhookSignatureVerifier,
)


class StaticApprovedImageCatalog(ApprovedImageCatalog):
    """Exact allowlist for immutable digest references."""

    def __init__(self, approved: dict[str, frozenset[str]]) -> None:
        self.approved = approved

    def is_approved(self, digest: str, target_id: str) -> bool:
        return digest in self.approved.get(target_id, frozenset())
