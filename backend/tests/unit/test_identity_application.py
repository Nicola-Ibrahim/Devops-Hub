from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from identity.application.authenticate import Authenticate
from identity.application.dto import IssueTokenCommand
from identity.application.errors import CredentialDeliveryError
from identity.application.issue_token import IssueToken
from identity.application.revoke_token import RevokeToken
from identity.domain.credentials import CredentialSnapshot
from identity.domain.errors import AuthenticationRejected, IdentityValidationError
from identity.domain.records import IdentitySnapshot, TokenSnapshot
from identity.infra.credential_file import PrivateCredentialFile
from identity.infra.persistence.unit_of_work import SQLIdentityUnitOfWork
from identity.infra.tokens import PepperedTokenHasher, token_digest

NOW = datetime(2026, 1, 1, tzinfo=UTC)
TOKEN = "a" * 40


class Reader:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.calls = []

    def find_by_digest(self, digest):
        self.calls.append(digest)
        return self.snapshot


def snapshot(**changes):
    values = {
        "token_id": uuid4(),
        "user_id": uuid4(),
        "project_id": uuid4(),
        "role": "developer",
        "scopes": ("catalog:read",),
        "user_active": True,
        "expires_at": NOW + timedelta(hours=1),
        "revoked_at": None,
    }
    values.update(changes)
    return CredentialSnapshot(**values)


def test_authenticate_returns_principal_and_rejects_bad_token_before_read():
    reader = Reader(snapshot())
    hasher = PepperedTokenHasher("p" * 32)
    result = Authenticate(reader, hasher, lambda: NOW).execute(TOKEN)
    assert result.role == "developer"
    assert result.scopes == frozenset({"catalog:read"})
    assert reader.calls == [token_digest(TOKEN, "p" * 32)]

    for invalid in (None, "short", "x" * 257):
        with pytest.raises(AuthenticationRejected):
            Authenticate(reader, hasher, lambda: NOW).execute(invalid)
    assert len(reader.calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"user_active": False},
        {"revoked_at": NOW},
        {"expires_at": NOW},
        {"role": None},
    ],
)
def test_authenticate_rejects_invalid_snapshot(changes):
    reader = Reader(snapshot(**changes))
    with pytest.raises(AuthenticationRejected) as error:
        Authenticate(reader, PepperedTokenHasher("p" * 32), lambda: NOW).execute(TOKEN)
    assert error.value.code == "unauthenticated"
    assert error.value.message == "A valid bearer token is required"


class Transaction:
    def __init__(self, issue_id=None, identity_active=True, token=None):
        self.issue_id = issue_id or uuid4()
        self.user_id = uuid4()
        self.project_id = uuid4()
        self.identity_active = identity_active
        self.token = token
        self.calls = []
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.rolled_back = exc_type is not None
        return False

    def ensure_identity(self, **kwargs):
        self.calls.append(("ensure_identity", kwargs))
        return IdentitySnapshot(self.user_id, self.project_id, self.identity_active)

    def add_token(self, **kwargs):
        self.calls.append(("add_token", kwargs))
        return self.issue_id

    def append_audit(self, event):
        self.calls.append(("append_audit", event))

    def find_token(self, token_id):
        self.calls.append(("find_token", token_id))
        return self.token

    def set_revoked(self, token_id, revoked_at):
        self.calls.append(("set_revoked", token_id, revoked_at))


class Delivery:
    def __init__(self, fail=False, fail_cleanup=False):
        self.fail = fail
        self.fail_cleanup = fail_cleanup
        self.secret = None
        self.removed = False

    def write_new(self, secret):
        if self.fail:
            raise CredentialDeliveryError()
        self.secret = secret
        return self

    def remove_owned(self):
        self.removed = True
        if self.fail_cleanup:
            raise OSError("cleanup detail must not escape")


def issue_use_case(tx, generator=None):
    return IssueToken(
        transactions=lambda: tx,
        hasher=PepperedTokenHasher("p" * 32),
        generator=generator or type("Generator", (), {"generate": lambda self: TOKEN})(),
        clock=lambda: NOW,
        allowed_scopes=("catalog:read", "resources:read"),
        default_scopes=("catalog:read",),
    )


def test_issue_token_writes_before_commit_and_rolls_back_on_delivery_error():
    tx = Transaction()
    delivery = Delivery()
    token_id = issue_use_case(tx).execute(IssueTokenCommand("dev", "demo"), delivery)
    assert token_id == tx.issue_id
    assert delivery.secret == TOKEN
    assert tx.rolled_back is False
    assert tx.calls[0] == (
        "ensure_identity",
        {"user_name": "dev", "project_name": "demo", "new_role": "developer"},
    )
    assert tx.calls[1][0] == "add_token"
    assert tx.calls[1][1]["digest"] == token_digest(TOKEN, "p" * 32)
    assert tx.calls[2][1].action == "token_issued"

    failed_tx = Transaction()
    with pytest.raises(CredentialDeliveryError):
        issue_use_case(failed_tx).execute(IssueTokenCommand("dev", "demo"), Delivery(fail=True))
    assert failed_tx.rolled_back is True


def test_issue_token_compensates_failed_commit_and_preserves_primary_error():
    class CommitFailure(Transaction):
        def __exit__(self, exc_type, exc, traceback):
            raise RuntimeError("commit failed")

    delivery = Delivery(fail_cleanup=True)
    with pytest.raises(RuntimeError, match="commit failed") as error:
        issue_use_case(CommitFailure()).execute(IssueTokenCommand("dev", "demo"), delivery)
    assert delivery.removed
    assert error.value.__notes__ == [
        "Credential cleanup failed; the original failure was preserved."
    ]


def test_issue_token_validates_registered_scopes_and_names_before_transaction():
    tx = Transaction()
    with pytest.raises(IdentityValidationError):
        issue_use_case(tx).execute(IssueTokenCommand("bad name", "demo"), Delivery())
    with pytest.raises(IdentityValidationError):
        issue_use_case(tx).execute(
            IssueTokenCommand("dev", "demo", scopes=("admin:*",)), Delivery()
        )
    assert tx.calls == []


def test_revoke_unknown_and_idempotent_policy_is_transaction_delegated():
    token_id = uuid4()
    missing = Transaction(token=None)
    assert RevokeToken(lambda: missing, lambda: NOW).execute(token_id) is False
    repeated = Transaction(token=TokenSnapshot(token_id, uuid4(), uuid4(), NOW))
    assert RevokeToken(lambda: repeated, lambda: NOW).execute(token_id) is True
    assert repeated.calls == [("find_token", token_id)]


def test_issue_rejects_disabled_identity_before_token_or_audit_write():
    tx = Transaction(identity_active=False)
    with pytest.raises(IdentityValidationError):
        issue_use_case(tx).execute(IssueTokenCommand("dev", "demo"), Delivery())
    assert [call[0] for call in tx.calls] == ["ensure_identity"]
    assert tx.rolled_back


def test_revoke_application_owns_unknown_idempotency_and_audit_policy():
    token_id = uuid4()
    missing = Transaction(token=None)
    assert RevokeToken(lambda: missing, lambda: NOW).execute(token_id) is False
    assert [call[0] for call in missing.calls] == ["find_token"]

    already_revoked = Transaction(token=TokenSnapshot(token_id, uuid4(), uuid4(), NOW))
    assert RevokeToken(lambda: already_revoked, lambda: NOW).execute(token_id) is True
    assert [call[0] for call in already_revoked.calls] == ["find_token"]

    active_token = TokenSnapshot(token_id, uuid4(), uuid4(), None)
    active = Transaction(token=active_token)
    assert RevokeToken(lambda: active, lambda: NOW).execute(token_id) is True
    assert [call[0] for call in active.calls] == ["find_token", "set_revoked", "append_audit"]
    assert active.calls[-1][1].action == "token_revoked"


def test_credential_file_is_exclusive_private_and_receipt_does_not_remove_replacement(tmp_path):
    path = tmp_path / "credential.txt"
    delivery = PrivateCredentialFile(path)
    receipt = delivery.write_new(TOKEN)
    assert path.read_text() == TOKEN + "\n"
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(CredentialDeliveryError):
        delivery.write_new("another-secret")

    path.unlink()
    path.write_text("unrelated")
    receipt.remove_owned()
    assert path.read_text() == "unrelated"


def test_peppered_hasher_redacts_key_and_preserves_hmac_output():
    hasher = PepperedTokenHasher("p" * 32)
    assert hasher.digest(TOKEN) == token_digest(TOKEN, "p" * 32)
    assert "p" * 32 not in repr(hasher)


def test_credential_file_cleans_partial_file_on_keyboard_interrupt(tmp_path, monkeypatch):
    path = tmp_path / "credential.txt"

    def interrupt(_descriptor):
        raise KeyboardInterrupt()

    monkeypatch.setattr("identity.infra.credential_file.os.fsync", interrupt)
    with pytest.raises(KeyboardInterrupt):
        PrivateCredentialFile(path).write_new(TOKEN)
    assert not path.exists()


def test_uow_preserves_primary_error_when_rollback_and_close_fail():
    class FailingTransaction:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            raise RuntimeError("unsafe rollback details")

    class FailingSession:
        def begin(self):
            return FailingTransaction()

        def close(self):
            raise RuntimeError("unsafe close details")

    uow = SQLIdentityUnitOfWork(lambda: FailingSession())
    with pytest.raises(ValueError, match="body failure") as error:
        with uow:
            raise ValueError("body failure")
    assert error.value.__notes__ == [
        "Identity transaction cleanup failed; the original failure was preserved.",
        "Identity session cleanup failed; the original failure was preserved.",
    ]
