from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from starlette.requests import Request

from api.errors import APIError
from api.identity.browser import browser_credentials
from identity.application.browser_contracts import BrowserMembership
from identity.application.browser_identity import principal_for_project
from identity.domain.browser_credentials import (
    normalize_user_name,
    session_expiry,
    session_is_valid,
    validate_password,
)
from identity.domain.errors import IdentityValidationError
from identity.infra.browser_security import ScryptPasswordHasher


def request(headers=(), cookies=b""):
    raw = [(key.lower().encode(), value.encode()) for key, value in headers]
    if cookies:
        raw.append((b"cookie", cookies))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw})


def test_username_and_password_policy_is_normalized_and_bounded():
    assert normalize_user_name("  Alice.Dev ") == "alice.dev"
    with pytest.raises(IdentityValidationError):
        normalize_user_name("not a valid username")
    validate_password("correct-horse-battery")
    with pytest.raises(IdentityValidationError):
        validate_password("short")


def test_scrypt_hash_verifies_only_matching_password_and_never_embeds_plaintext():
    hasher = ScryptPasswordHasher()
    encoded = hasher.hash("correct-horse-battery")
    assert "correct-horse-battery" not in encoded
    assert hasher.verify("correct-horse-battery", encoded)
    assert not hasher.verify("wrong-password", encoded)


def test_browser_session_expiry_caps_idle_window_and_rejects_disabled_or_revoked_user():
    now = datetime(2026, 11, 1, tzinfo=UTC)
    idle, absolute = session_expiry(now)
    assert idle == now + timedelta(minutes=30)
    assert absolute == now + timedelta(hours=8)
    assert session_is_valid(
        now=now + timedelta(minutes=1),
        last_seen_at=now,
        idle_expires_at=idle,
        absolute_expires_at=absolute,
        revoked_at=None,
        user_active=True,
    )
    assert not session_is_valid(
        now=now + timedelta(minutes=1),
        last_seen_at=now,
        idle_expires_at=idle,
        absolute_expires_at=absolute,
        revoked_at=None,
        user_active=False,
    )
    assert not session_is_valid(
        now=now + timedelta(minutes=1),
        last_seen_at=now,
        idle_expires_at=idle,
        absolute_expires_at=absolute,
        revoked_at=now,
        user_active=True,
    )


def test_browser_principal_has_only_live_selected_project_authority():
    user_id, session_id, project_id = uuid4(), uuid4(), uuid4()
    member = BrowserMembership(project_id, "service", "developer")
    selected = principal_for_project(
        user_id=user_id,
        user_name="alice",
        session_id=session_id,
        memberships=(member,),
        project_id=project_id,
        csrf_token="csrf",
    )
    projectless = principal_for_project(
        user_id=user_id,
        user_name="alice",
        session_id=session_id,
        memberships=(member,),
        project_id=uuid4(),
        csrf_token="csrf",
    )
    assert selected.project_id == project_id
    assert selected.role == "developer"
    assert selected.scopes
    assert "csrf" not in repr(selected)
    assert projectless.project_id is None
    assert projectless.role is None
    assert projectless.scopes == ()


def test_browser_transport_parses_project_header_and_rejects_cookie_bearer_ambiguity():
    parsed = browser_credentials(request(headers=[("X-Project-ID", str(uuid4()))]))
    assert parsed.session_token is None and parsed.project_id is not None
    with pytest.raises(APIError) as error:
        browser_credentials(
            request(headers=[("Authorization", "Bearer token")], cookies=b"devops_session=session")
        )
    assert error.value.status == 400
    assert error.value.code == "ambiguous_credentials"
