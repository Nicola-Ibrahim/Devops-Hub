"""Validation shared by application delivery commands."""

import re

from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError

APP_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
DIGEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,250}@sha256:[a-f0-9]{64}\Z")
IDEMPOTENCY = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


def require_delivery_scope(access: AccessContext, scope: str) -> None:
    if access.project_id is None or scope not in access.scopes:
        raise PlatformRequestError("forbidden", "Application access is not permitted", 403)


def validate_delivery_key(value: str) -> None:
    if not IDEMPOTENCY.fullmatch(value):
        raise PlatformRequestError("invalid_idempotency_key", "Idempotency-Key is invalid", 422)
