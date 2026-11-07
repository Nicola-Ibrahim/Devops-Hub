from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from identity.domain.aggregates.identity_account import IdentityAccount
from identity.domain.entities.internal_user import InternalUser
from identity.domain.errors import AuthenticationRejected
from identity.domain.services.token_authentication import authenticate_token
from identity.domain.value_objects.credential_version import CredentialVersion
from identity.domain.value_objects.user_name import UserName


def test_identity_account_preserves_active_and_credential_version_fence() -> None:
    account = IdentityAccount.from_user(
        InternalUser(
            id=uuid4(),
            user_name=UserName.parse(" Developer "),
            credential_version=CredentialVersion(3),
            active=True,
        )
    )

    assert account.accepts_credentials(password_matches=True)
    assert not account.accepts_credentials(password_matches=False)
    assert account.login_fence() == 3
    assert account.next_credential_version() == CredentialVersion(4)


def test_token_authentication_returns_identity_owned_result() -> None:
    user_id, project_id, token_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)

    identity = authenticate_token(
        token_id=token_id,
        user_id=user_id,
        project_id=project_id,
        role="admin",
        scopes=("resource:read",),
        user_active=True,
        expires_at=now + timedelta(minutes=5),
        revoked_at=None,
        now=now,
    )

    assert (identity.user_id, identity.project_id, identity.token_id) == (
        user_id,
        project_id,
        token_id,
    )
    assert identity.scopes == frozenset({"resource:read"})


@pytest.mark.parametrize(
    ("user_active", "revoked_at", "expires_at"),
    [
        (False, None, datetime(2030, 1, 1, tzinfo=UTC)),
        (True, datetime(2025, 1, 1, tzinfo=UTC), datetime(2030, 1, 1, tzinfo=UTC)),
        (True, None, datetime(2025, 1, 1, tzinfo=UTC)),
    ],
)
def test_token_authentication_rejects_unusable_credentials(
    user_active: bool, revoked_at: datetime | None, expires_at: datetime
) -> None:
    with pytest.raises(AuthenticationRejected):
        authenticate_token(
            token_id=uuid4(),
            user_id=uuid4(),
            project_id=uuid4(),
            role="developer",
            scopes=(),
            user_active=user_active,
            expires_at=expires_at,
            revoked_at=revoked_at,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
