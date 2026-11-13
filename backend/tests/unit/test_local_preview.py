"""Local preview registration and immutable local image contracts."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.platform.application_delivery.schemas import LocalPreviewCreate
from devops_platform.application.shared.errors import PlatformRequestError
from devops_platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentSpec,
)
from devops_platform.application.workload_delivery.create_local_preview.command import (
    CreateLocalPreview,
    LocalPreviewRegistration,
)
from devops_platform.application.workload_delivery.create_local_preview.handler import (
    CreateLocalPreviewHandler,
)
from devops_platform.application.workload_delivery.deploy_workload.command import (
    DeployApplication,
    DeploymentSpec,
)
from devops_platform.application.workload_delivery.deploy_workload.handler import (
    DeployApplicationHandler,
)
from devops_platform.authorization import authorize_platform_access, authorize_platform_action
from devops_platform.domain.access import AccessContext
from devops_platform.domain.errors import DomainError
from devops_platform.domain.value_objects.image_digest import ImageDigest
from devops_platform.infra.persistence.delivery import SQLAlchemyApplicationDeliveryRepository


class FakeFingerprint:
    def for_value(self, value: object) -> str:
        return str(value)


class FakeLocalPreviewRepository:
    async def create_local_preview(self, access, command, idempotency_key, request_hash, now):
        return (access, command, idempotency_key, request_hash, now), False


class FakeImages:
    def __init__(self, approved: set[str]) -> None:
        self.approved = approved

    def is_approved(self, digest: str, target_id: str) -> bool:
        return target_id == "local" and digest in self.approved


class FakeDeploymentRepository:
    async def enqueue_deployment(self, *args):
        return args


def test_local_preview_request_has_only_registration_fields() -> None:
    request = LocalPreviewCreate(name="feature-preview", environment_id=uuid4(), ttl_seconds=600)
    assert set(request.model_dump()) == {"name", "environment_id", "ttl_seconds"}
    with pytest.raises(ValidationError):
        LocalPreviewCreate(
            name="feature-preview",
            environment_id=uuid4(),
            ttl_seconds=60,
            image_digest="sha256:" + "a" * 64,
        )


def test_local_preview_authorization_requires_write_scope_and_scoped_project() -> None:
    project_id, actor_id = uuid4(), uuid4()
    request = LocalPreviewRegistration("feature-preview", uuid4(), 600)
    authorized = AccessContext(actor_id, project_id, "developer", frozenset({"resources:write"}))
    authorize_platform_action(CreateLocalPreview(authorized, request, "preview-key"))

    missing_scope = AccessContext(actor_id, project_id, "developer", frozenset())
    with pytest.raises(PlatformRequestError) as forbidden:
        authorize_platform_action(CreateLocalPreview(missing_scope, request, "preview-key"))
    assert (forbidden.value.code, forbidden.value.status) == ("forbidden", 403)

    with pytest.raises(PlatformRequestError) as cross_project:
        authorize_platform_access(
            CreateLocalPreview,
            authorized,
            project_id=uuid4(),
        )
    assert (cross_project.value.code, cross_project.value.status) == ("not_found", 404)


def test_local_preview_handler_validates_name_ttl_and_persists_replay_identity() -> None:
    access = AccessContext(uuid4(), uuid4(), "developer", frozenset({"resources:write"}))
    repository = FakeLocalPreviewRepository()
    handler = CreateLocalPreviewHandler(
        repository,
        FakeFingerprint(),
        lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    command = CreateLocalPreview(
        access, LocalPreviewRegistration("feature-preview", uuid4(), 600), "preview-key"
    )
    result, replayed = asyncio.run(handler.execute(command))
    assert result[0] == access
    assert result[1] == command.request
    assert result[2] == "preview-key"
    assert not replayed
    invalid = CreateLocalPreview(
        access, LocalPreviewRegistration("Bad Name", uuid4(), 600), "another-key"
    )
    with pytest.raises(PlatformRequestError) as error:
        asyncio.run(handler.execute(invalid))
    assert error.value.code == "invalid_workload_name"


def test_immutable_image_digest_accepts_repo_digest_or_local_id_but_not_tags() -> None:
    repo_digest = "registry.example/team/app@sha256:" + "b" * 64
    image_id = "sha256:" + "a" * 64
    assert ImageDigest(repo_digest).value == repo_digest
    assert ImageDigest(image_id).is_local_image_id
    with pytest.raises(DomainError):
        ImageDigest("registry.example/team/app:latest")


def test_bare_image_id_is_local_only_and_requires_exact_approval() -> None:
    access = AccessContext(uuid4(), uuid4(), "developer", frozenset({"resources:write"}))
    digest = "sha256:" + "c" * 64
    handler = DeployApplicationHandler(
        FakeDeploymentRepository(),
        FakeImages({digest}),
        FakeFingerprint(),
        lambda: datetime.now(UTC),
    )
    local = DeployApplication(access, uuid4(), DeploymentSpec(digest, "local"), "local-key")
    assert asyncio.run(handler.execute(local))[2] == local.request
    remote = DeployApplication(access, uuid4(), DeploymentSpec(digest, "remote"), "remote-key")
    with pytest.raises(PlatformRequestError) as error:
        asyncio.run(handler.execute(remote))
    assert error.value.code == "immutable_image_required"


def test_distinct_attachment_key_cannot_enqueue_while_resource_step_is_active() -> None:
    owner_id, project_id, application_id = uuid4(), uuid4(), uuid4()
    access = AccessContext(owner_id, project_id, "developer", frozenset({"resources:write"}))
    app = SimpleNamespace(
        id=application_id,
        project_id=project_id,
        owner_id=owner_id,
        status="pending",
        is_preview=True,
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    class Session:
        calls = 0

        async def scalar(self, _statement):
            self.calls += 1
            if self.calls == 1:  # owned application
                return app
            if self.calls == 2:  # no matching idempotency key
                return None
            return uuid4()  # existing pending/running/succeeded resource step

    session = Session()
    repository = SQLAlchemyApplicationDeliveryRepository(session)  # type: ignore[arg-type]
    with pytest.raises(PlatformRequestError) as error:
        asyncio.run(
            repository.enqueue_resource_attachment(
                access,
                application_id,
                ResourceAttachmentSpec("postgres", "16", "local", "small", 300),
                "distinct-key",
                "request-hash",
                datetime(2025, 12, 31, tzinfo=UTC),
            )
        )
    assert (error.value.code, error.value.status) == ("resource_attachment_in_progress", 409)
    assert session.calls == 3
