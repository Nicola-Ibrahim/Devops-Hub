import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from starlette.requests import Request

from api.core.errors import APIError
from api.identity.authentication.credentials import browser_credentials
from identity.application.change_password.command import VerifyPasswordChange
from identity.application.change_password.handler import VerifyPasswordChangeHandler
from identity.application.login.command import VerifyLoginCredentials
from identity.application.login.handler import VerifyLoginCredentialsHandler
from identity.application.shared.principal import principal_for_project
from identity.domain.browser_credentials import (
    normalize_user_name,
    session_expiry,
    session_is_valid,
    validate_password,
)
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.errors import IdentityValidationError
from identity.domain.records import AccountCredentials, MembershipDetails
from identity.infra.security.passwords import ScryptPasswordHasher


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
    member = MembershipDetails(project_id, "service", "developer")
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


def test_browser_login_uses_dummy_hash_for_missing_user_and_requires_active_account():
    hasher = ScryptPasswordHasher()
    dummy_hash = hasher.hash("devops-hub-dummy-password-value")
    service = VerifyLoginCredentialsHandler(hasher, dummy_hash)

    async def check() -> tuple[object, object]:
        missing = await service.execute(VerifyLoginCredentials("unknown", "wrong-password", None))
        inactive = await service.execute(
            VerifyLoginCredentials(
                " Alice ",
                "correct-horse-battery",
                AccountCredentials(
                    uuid4(), "alice", hasher.hash("correct-horse-battery"), 4, False, ()
                ),
            )
        )
        return missing, inactive

    missing, inactive = asyncio.run(check())

    assert missing.normalized_user_name == "unknown"
    assert not missing.accepted
    assert inactive.normalized_user_name == "alice"
    assert not inactive.accepted


def test_password_change_checks_current_password_and_preserves_version_fence():
    hasher = ScryptPasswordHasher()
    account = AccountCredentials(
        uuid4(), "alice", hasher.hash("current-password-value"), 7, True, ()
    )
    service = VerifyPasswordChangeHandler(hasher)

    async def check() -> None:
        prepared = await service.execute(
            VerifyPasswordChange(account, "current-password-value", "new-password-value")
        )
        assert prepared.credential_version == 7
        assert hasher.verify("new-password-value", prepared.encoded_password)
        with pytest.raises(BrowserAuthenticationRejected):
            await service.execute(
                VerifyPasswordChange(account, "incorrect-current-password", "another-new-password")
            )

    asyncio.run(check())
