"""The shared action policy covers every dispatch message and fails before DI resolution."""

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from devops_platform.application.database_lifecycle.read_connection.query import (
    ReadDatabaseConnection,
)
from devops_platform.application.database_provisioning.read_resources.query import (
    ReadProject,
    ReadProjects,
)
from devops_platform.application.resource_catalog.query import ReadCatalog
from devops_platform.application.shared.errors import CatalogForbidden, PlatformRequestError
from devops_platform.application.workload_delivery.handle_preview_webhook.command import (
    ProcessGithubPreviewWebhook,
)
from devops_platform.application.workload_delivery.read_templates.query import ReadTemplates
from devops_platform.authorization import ACTION_PERMISSIONS, authorize_platform_action
from devops_platform.domain.access import AccessContext
from devops_platform.domain.errors import DomainError
from devops_platform.domain.services.resource_access import ResourceAccessPolicy, ResourceActor
from devops_platform.infra.composition.module import (
    PLATFORM_HANDLER_REGISTRY,
    DeveloperPlatformModuleDispatcher,
)


def test_every_registered_message_has_an_explicit_policy() -> None:
    registered = set(PLATFORM_HANDLER_REGISTRY.commands) | set(PLATFORM_HANDLER_REGISTRY.queries)
    assert set(ACTION_PERMISSIONS) == registered
    assert ACTION_PERMISSIONS[ReadTemplates].target == "public"
    assert ACTION_PERMISSIONS[ProcessGithubPreviewWebhook].target == "public"


def test_project_and_scope_failures_preserve_existing_error_contract() -> None:
    project_id, other_project, actor_id = uuid4(), uuid4(), uuid4()
    access = AccessContext(actor_id, project_id, "developer", frozenset({"resources:read"}))
    authorize_platform_action(ReadProject(access, project_id))
    with pytest.raises(PlatformRequestError) as mismatch:
        authorize_platform_action(ReadProject(access, other_project))
    assert (mismatch.value.code, mismatch.value.status) == ("not_found", 404)
    with pytest.raises(PlatformRequestError) as zero_project:
        authorize_platform_action(ReadProject(access, UUID(int=0)))
    assert zero_project.value.status == 404
    with pytest.raises(CatalogForbidden):
        authorize_platform_action(ReadDatabaseConnection(access, uuid4()))
    with pytest.raises(CatalogForbidden):
        authorize_platform_action(ReadCatalog(access))
    authorize_platform_action(ReadProjects((access,)))


def test_direct_dispatch_denies_before_resolving_a_handler() -> None:
    resolved: list[type[object]] = []

    async def resolve(handler: type[object]) -> object:
        resolved.append(handler)
        raise AssertionError("denied action resolved a handler")

    access = AccessContext(uuid4(), uuid4(), "developer", frozenset())
    module = DeveloperPlatformModuleDispatcher(resolve)
    with pytest.raises(CatalogForbidden):
        asyncio.run(module.query(ReadDatabaseConnection(access, uuid4())))
    assert resolved == []


def test_unknown_action_fails_closed() -> None:
    with pytest.raises(TypeError, match="Unregistered platform action"):
        authorize_platform_action(object())


def test_loaded_resource_owner_rule_survives_transport_permission_move() -> None:
    project_id, owner_id, other_id = uuid4(), uuid4(), uuid4()
    resource = SimpleNamespace(project_id=project_id, owner_id=owner_id)
    scopes = frozenset({"resources:write"})
    ResourceAccessPolicy.require(
        resource, ResourceActor(owner_id, project_id, "developer", scopes), "resources:write"
    )
    with pytest.raises(DomainError):
        ResourceAccessPolicy.require(
            resource, ResourceActor(other_id, project_id, "developer", scopes), "resources:write"
        )
    ResourceAccessPolicy.require(
        resource, ResourceActor(other_id, project_id, "admin", scopes), "resources:write"
    )
