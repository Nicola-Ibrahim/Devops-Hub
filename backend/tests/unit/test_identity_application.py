import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from identity.application.authenticate_api_token.handler import AuthenticateApiTokenHandler
from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.issue_api_token.command import IssueApiTokenCommand
from identity.application.issue_api_token.handler import IssueApiTokenHandler
from identity.application.issue_api_token.result import PreparedApiToken
from identity.application.revoke_api_token.command import RevokeApiTokenCommand
from identity.application.revoke_api_token.handler import RevokeApiTokenHandler
from identity.domain.credentials import ApiTokenAuthenticationDetails
from identity.domain.errors import AuthenticationRejected, IdentityValidationError
from identity.domain.records import ApiTokenStatus, ProjectMembershipStatus
from identity.infra.credential_file import PrivateCredentialFile
from identity.infra.tokens import PepperedTokenHasher, token_digest

NOW = datetime(2026, 1, 1, tzinfo=UTC)
TOKEN = "a" * 40


class FakeRepository:
    def __init__(self, credential=None, identity_active=True, token=None):
        self.credential = credential
        self.identity_active = identity_active
        self.token = token
        self.user_id = uuid4()
        self.project_id = uuid4()
        self.issue_id = uuid4()
        self.calls = []

    async def find_token_credential(self, digest):
        self.calls.append(("find_token_credential", digest))
        return self.credential

    async def ensure_developer_membership(self, **kwargs):
        self.calls.append(("ensure_developer_membership", kwargs))
        return ProjectMembershipStatus(self.user_id, self.project_id, self.identity_active)

    async def insert_api_token(self, **kwargs):
        self.calls.append(("insert_api_token", kwargs))
        return self.issue_id

    async def record_token_audit(self, event):
        self.calls.append(("record_token_audit", event))

    async def find_api_token(self, token_id):
        self.calls.append(("find_api_token", token_id))
        return self.token

    async def revoke_api_token(self, token_id, revoked_at):
        self.calls.append(("revoke_api_token", token_id, revoked_at))


class FakeHasher:
    def digest(self, token):
        return "synthetic-digest"


class FakeGenerator:
    def generate(self):
        return TOKEN


def issue_service(repository):
    return IssueApiTokenHandler(
        repository=repository,
        hasher=PepperedTokenHasher("p" * 32),
        generator=FakeGenerator(),
        clock=lambda: NOW,
        allowed_scopes=("catalog:read", "resources:read"),
        default_scopes=("catalog:read",),
    )


def test_authenticate_api_token_reads_repository_and_rejects_malformed_before_query():
    snapshot = ApiTokenAuthenticationDetails(
        uuid4(),
        uuid4(),
        uuid4(),
        "developer",
        ("catalog:read",),
        True,
        NOW + timedelta(hours=1),
        None,
    )
    repository = FakeRepository(credential=snapshot)
    result = asyncio.run(
        AuthenticateApiTokenHandler(repository, PepperedTokenHasher("p" * 32), lambda: NOW).execute(
            AuthenticateApiTokenQuery(TOKEN)
        )
    )
    assert result.role == "developer"
    assert result.scopes == frozenset({"catalog:read"})
    assert repository.calls == [("find_token_credential", token_digest(TOKEN, "p" * 32))]

    for invalid in (None, "short", "x" * 257):
        with pytest.raises(AuthenticationRejected):
            asyncio.run(
                AuthenticateApiTokenHandler(
                    repository, PepperedTokenHasher("p" * 32), lambda: NOW
                ).execute(AuthenticateApiTokenQuery(invalid))
            )
    assert len(repository.calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"user_active": False},
        {"revoked_at": NOW},
        {"expires_at": NOW},
        {"role": None},
    ],
)
def test_authenticate_api_token_rejects_invalid_repository_snapshot(changes):
    values = dict(
        token_id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        role="developer",
        scopes=("catalog:read",),
        user_active=True,
        expires_at=NOW + timedelta(hours=1),
        revoked_at=None,
    )
    values.update(changes)
    repository = FakeRepository(credential=ApiTokenAuthenticationDetails(**values))
    with pytest.raises(AuthenticationRejected):
        asyncio.run(
            AuthenticateApiTokenHandler(repository, FakeHasher(), lambda: NOW).execute(
                AuthenticateApiTokenQuery(TOKEN)
            )
        )


def test_issue_api_token_returns_private_completion_result_and_records_writes():
    repository = FakeRepository()
    prepared = asyncio.run(issue_service(repository).execute(IssueApiTokenCommand("dev", "demo")))
    assert isinstance(prepared, PreparedApiToken)
    assert prepared.token_id == repository.issue_id
    assert prepared.secret == TOKEN
    assert TOKEN not in repr(prepared)
    assert [call[0] for call in repository.calls] == [
        "ensure_developer_membership",
        "insert_api_token",
        "record_token_audit",
    ]
    assert repository.calls[0][1] == {
        "user_name": "dev",
        "project_name": "demo",
        "new_role": "developer",
    }
    assert repository.calls[1][1]["digest"] == token_digest(TOKEN, "p" * 32)
    assert repository.calls[2][1].action == "token_issued"


@pytest.mark.parametrize(
    "command",
    [
        IssueApiTokenCommand("bad name", "demo"),
        IssueApiTokenCommand("dev", "demo", hours=0),
        IssueApiTokenCommand("dev", "demo", scopes=("admin:*",)),
    ],
)
def test_issue_api_token_validates_before_repository_calls(command):
    repository = FakeRepository()
    with pytest.raises(IdentityValidationError):
        asyncio.run(issue_service(repository).execute(command))
    assert repository.calls == []


def test_issue_api_token_rejects_disabled_user_before_token_or_audit():
    repository = FakeRepository(identity_active=False)
    with pytest.raises(IdentityValidationError):
        asyncio.run(issue_service(repository).execute(IssueApiTokenCommand("dev", "demo")))
    assert [call[0] for call in repository.calls] == ["ensure_developer_membership"]


def test_revoke_api_token_is_idempotent_and_audits_only_first_revoke():
    token_id = uuid4()
    missing = FakeRepository(token=None)
    assert (
        asyncio.run(
            RevokeApiTokenHandler(missing, lambda: NOW).execute(RevokeApiTokenCommand(token_id))
        )
        is False
    )
    assert [call[0] for call in missing.calls] == ["find_api_token"]

    existing = ApiTokenStatus(token_id, uuid4(), uuid4(), None)
    repository = FakeRepository(token=existing)
    assert (
        asyncio.run(
            RevokeApiTokenHandler(repository, lambda: NOW).execute(RevokeApiTokenCommand(token_id))
        )
        is True
    )
    assert [call[0] for call in repository.calls] == [
        "find_api_token",
        "revoke_api_token",
        "record_token_audit",
    ]
    assert repository.calls[-1][1].action == "token_revoked"

    repository.calls.clear()
    repository.token = ApiTokenStatus(token_id, existing.user_id, existing.project_id, NOW)
    assert (
        asyncio.run(
            RevokeApiTokenHandler(repository, lambda: NOW).execute(RevokeApiTokenCommand(token_id))
        )
        is True
    )
    assert [call[0] for call in repository.calls] == ["find_api_token"]


def test_private_credential_file_remains_exclusive_and_replacement_safe(tmp_path):
    path = tmp_path / "credential.txt"
    delivery = PrivateCredentialFile(path)
    receipt = delivery.write_new(TOKEN)
    assert path.read_text() == TOKEN + "\n"
    assert path.stat().st_mode & 0o777 == 0o600
    path.unlink()
    path.write_text("unrelated")
    receipt.remove_owned()
    assert path.read_text() == "unrelated"
