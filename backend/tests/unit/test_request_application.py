"""Pure application tests for registration, request acceptance, and scoped reads."""

import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID

from developer_platform.application.project_registration.command import RegisterProjectCommand
from developer_platform.application.project_registration.handler import RegisterProjectHandler
from developer_platform.application.project_registration.result import (
    EnvironmentDetails,
    ProjectRegistrationDetails,
)
from developer_platform.application.resource_requests.read_resources.handler import (
    ReadOperationHandler,
    ReadProjectHandler,
    ReadResourceHandler,
    ReadResourcesHandler,
)
from developer_platform.application.resource_requests.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from developer_platform.application.resource_requests.submit_database_request.command import (
    DatabaseRequest,
)
from developer_platform.application.resource_requests.submit_database_request.handler import (
    RequestTemporaryDatabaseHandler,
)
from developer_platform.application.resource_requests.submit_database_request.result import (
    AcceptedDatabaseRequest,
)

from developer_platform.application.database_provisioning.read_resources.query import (
    ReadOperation,
    ReadProject,
    ReadResource,
    ReadResources,
)
from developer_platform.application.database_provisioning.submit_database_request.command import (
    RequestTemporaryDatabase,
)
from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from developer_platform.application.resource_catalog.models import PostgresOption, ResourceSize
from developer_platform.application.resource_catalog.query import ReadCatalog
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import CatalogForbidden, PlatformRequestError
from developer_platform.authorization import authorize_platform_action

PROJECT_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_PROJECT_ID = UUID("22222222-2222-4222-8222-222222222222")
USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TEAM_ID = UUID("44444444-4444-4444-8444-444444444444")
ENVIRONMENT_ID = UUID("55555555-5555-4555-8555-555555555555")
RESOURCE_ID = UUID("66666666-6666-4666-8666-666666666666")
OPERATION_ID = UUID("77777777-7777-4777-8777-777777777777")
INSTALLATION_ID = UUID("88888888-8888-4888-8888-888888888888")
NOW = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


class FakePlatformLedgerRepository:
    """Record application calls without a database or provisioning provider."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.replay: AcceptedDatabaseRequest | None = None
        self.replay_error: Exception | None = None
        self.accepted = AcceptedDatabaseRequest(RESOURCE_ID, OPERATION_ID)
        self.project: ProjectRegistrationDetails | None = None
        self.resource: ResourceDetails | None = None
        self.operation: OperationDetails | None = None

    async def register_project(self, command, project_id, team_id):
        self.calls.append(("register_project", command, project_id, team_id))
        return self.project or ProjectRegistrationDetails(
            project_id,
            command.name,
            team_id,
            command.owning_team,
            command.repository,
            True,
            tuple(
                EnvironmentDetails(UUID(int=index + 1), name)
                for index, name in enumerate(command.environments)
            ),
        )

    async def find_project(self, project_id):
        self.calls.append(("find_project", project_id))
        return self.project

    async def replay_request(self, access, key, request_hash):
        self.calls.append(("replay_request", access, key, request_hash))
        if self.replay_error is not None:
            raise self.replay_error
        return self.replay

    async def accept_database_request(self, access, lifecycle, key, request_hash):
        self.calls.append(
            (
                "accept_database_request",
                access,
                lifecycle,
                key,
                request_hash,
            )
        )
        return self.accepted

    async def list_resources(self, project_id, after, limit):
        self.calls.append(("list_resources", project_id, after, limit))
        return ()

    async def find_resource(self, project_id, resource_id):
        self.calls.append(("find_resource", project_id, resource_id))
        return self.resource

    async def find_operation(self, project_id, operation_id):
        self.calls.append(("find_operation", project_id, operation_id))
        return self.operation


def _access(*scopes: str, project_id: UUID = PROJECT_ID) -> AccessContext:
    return AccessContext(USER_ID, project_id, "developer", frozenset(scopes))


def _command(**overrides) -> DatabaseRequest:
    values = {
        "project_id": PROJECT_ID,
        "environment_id": ENVIRONMENT_ID,
        "display_name": "feature-db",
        "template_id": "postgres",
        "version": "16",
        "target_id": "local",
        "size_id": "small",
        "ttl_seconds": 1800,
    }
    values.update(overrides)
    return DatabaseRequest(**values)


class RequestApplicationTests(unittest.IsolatedAsyncioTestCase):
    def test_action_policy_hides_cross_project_and_denies_missing_scope(self) -> None:
        with self.assertRaises(PlatformRequestError) as hidden:
            authorize_platform_action(ReadProject(_access("resources:read"), OTHER_PROJECT_ID))
        self.assertEqual(hidden.exception.status, 404)

        with self.assertRaises(CatalogForbidden) as forbidden:
            authorize_platform_action(RequestTemporaryDatabase(_access(), _command(), "key"))
        self.assertEqual(forbidden.exception.code, "forbidden")

    async def test_registration_rejects_invalid_registration_values(self) -> None:
        invalid_commands = (
            RegisterProjectCommand("demo", "", "org/repo", ("dev",)),
            RegisterProjectCommand("demo", "team", "not-a-repository", ("dev",)),
            RegisterProjectCommand("demo", "team", "org/repo", ()),
            RegisterProjectCommand("demo", "team", "org/repo", ("dev", "dev")),
            RegisterProjectCommand("demo", "team", "org/repo", ("Dev",)),
        )
        for command in invalid_commands:
            repository = FakePlatformLedgerRepository()
            with self.subTest(command=command), self.assertRaises(PlatformRequestError) as caught:
                await RegisterProjectHandler(repository).execute(command, PROJECT_ID, TEAM_ID)
            self.assertEqual(caught.exception.status, 422)
            self.assertEqual(repository.calls, [])

    async def test_valid_registration_passes_canonical_project_and_team_references(self) -> None:
        repository = FakePlatformLedgerRepository()
        command = RegisterProjectCommand("demo", "platform", "org/demo", ("dev", "test"))

        result = await RegisterProjectHandler(repository).execute(command, PROJECT_ID, TEAM_ID)

        self.assertTrue(result.configured)
        self.assertEqual(repository.calls, [("register_project", command, PROJECT_ID, TEAM_ID)])

    async def test_request_policy_rejects_scope_and_project_mismatch_before_repository_calls(
        self,
    ) -> None:
        repository = FakePlatformLedgerRepository()
        with self.assertRaises(CatalogForbidden):
            authorize_platform_action(
                RequestTemporaryDatabase(_access(), _command(), "request-key")
            )
        with self.assertRaises(PlatformRequestError) as caught:
            authorize_platform_action(
                RequestTemporaryDatabase(
                    _access("resources:write"), _command(project_id=OTHER_PROJECT_ID), "request-key"
                )
            )
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(repository.calls, [])

    async def test_request_rejects_malformed_key_or_display_name_without_lookup(self) -> None:
        repository = FakePlatformLedgerRepository()
        service = RequestTemporaryDatabaseHandler(
            repository,
            ApprovedPostgresCatalog(),
            lambda: NOW,
            lambda command: "fingerprint",
            INSTALLATION_ID,
        )
        invalid = (("bad key", _command()), ("valid-key", _command(display_name="  ")))
        for key, command in invalid:
            with self.subTest(key=key), self.assertRaises(PlatformRequestError) as caught:
                await service.execute(
                    RequestTemporaryDatabase(_access("resources:write"), command, key)
                )
            self.assertEqual(caught.exception.status, 422)
        self.assertEqual(repository.calls, [])

    async def test_default_catalog_is_unavailable_and_never_accepts_request(self) -> None:
        repository = FakePlatformLedgerRepository()
        service = RequestTemporaryDatabaseHandler(
            repository,
            ApprovedPostgresCatalog(),
            lambda: NOW,
            lambda command: "fingerprint",
            INSTALLATION_ID,
        )

        with self.assertRaises(PlatformRequestError) as caught:
            await service.execute(
                RequestTemporaryDatabase(_access("resources:write"), _command(), "request-key")
            )

        self.assertEqual(caught.exception.status, 503)
        self.assertEqual([call[0] for call in repository.calls], ["replay_request"])

    async def test_supported_option_uses_catalog_limits_and_acceptance_expiry(self) -> None:
        option = PostgresOption(
            version="16",
            size=ResourceSize("small", 250, 512, 1024),
            max_lifetime_seconds=7200,
            requestable=True,
            unavailable_reason=None,
        )
        repository = FakePlatformLedgerRepository()
        service = RequestTemporaryDatabaseHandler(
            repository,
            ApprovedPostgresCatalog((option,)),
            lambda: NOW,
            lambda command: "stable-fingerprint",
            INSTALLATION_ID,
        )

        result = await service.execute(
            RequestTemporaryDatabase(
                _access("resources:write"), _command(ttl_seconds=3600), "key-1"
            )
        )

        self.assertEqual(result, repository.accepted)
        accepted = next(call for call in repository.calls if call[0] == "accept_database_request")
        lifecycle = accepted[2]
        self.assertEqual(lifecycle.resource.specification.max_lifetime_seconds, 7200)
        self.assertEqual(lifecycle.resource.specification.cpu_millis, 250)
        self.assertEqual(lifecycle.resource.lease.expires_at, NOW + timedelta(seconds=3600))
        self.assertEqual(lifecycle.resource.installation_id, INSTALLATION_ID)

    async def test_unsupported_version_is_422_without_acceptance(self) -> None:
        option = PostgresOption(requestable=True, unavailable_reason=None)
        repository = FakePlatformLedgerRepository()
        service = RequestTemporaryDatabaseHandler(
            repository,
            ApprovedPostgresCatalog((option,)),
            lambda: NOW,
            lambda command: "fingerprint",
            INSTALLATION_ID,
        )

        with self.assertRaises(PlatformRequestError) as caught:
            await service.execute(
                RequestTemporaryDatabase(
                    _access("resources:write"), _command(version="99"), "key-1"
                )
            )

        self.assertEqual(caught.exception.status, 422)
        self.assertNotIn("accept_database_request", [call[0] for call in repository.calls])

    async def test_replay_returns_original_ids_before_disabled_catalog_check(self) -> None:
        original = AcceptedDatabaseRequest(UUID(int=101), UUID(int=102))
        repository = FakePlatformLedgerRepository()
        repository.replay = original
        service = RequestTemporaryDatabaseHandler(
            repository,
            ApprovedPostgresCatalog(),
            lambda: NOW,
            lambda command: "same-fingerprint",
            INSTALLATION_ID,
        )

        result = await service.execute(
            RequestTemporaryDatabase(_access("resources:write"), _command(), "key-1")
        )

        self.assertEqual(result, original)
        self.assertEqual([call[0] for call in repository.calls], ["replay_request"])

    async def test_idempotency_conflict_propagates_without_acceptance(self) -> None:
        repository = FakePlatformLedgerRepository()
        repository.replay_error = PlatformRequestError("idempotency_conflict", "Conflict", 409)
        service = RequestTemporaryDatabaseHandler(
            repository,
            ApprovedPostgresCatalog(),
            lambda: NOW,
            lambda command: "different-fingerprint",
            INSTALLATION_ID,
        )

        with self.assertRaises(PlatformRequestError) as caught:
            await service.execute(
                RequestTemporaryDatabase(_access("resources:write"), _command(), "key-1")
            )

        self.assertEqual(caught.exception.status, 409)
        self.assertNotIn("accept_database_request", [call[0] for call in repository.calls])

    async def test_read_policy_requires_scope_and_handler_bounds_pagination(self) -> None:
        repository = FakePlatformLedgerRepository()
        service = ReadResourcesHandler(repository)
        for message in (
            ReadProject(_access(), PROJECT_ID),
            ReadResources(_access(), PROJECT_ID, None, 10),
            ReadResource(_access(), RESOURCE_ID),
            ReadOperation(_access(), OPERATION_ID),
        ):
            with self.assertRaises(CatalogForbidden):
                authorize_platform_action(message)
        for invalid_limit in (0, 101):
            with self.assertRaises(PlatformRequestError) as caught:
                await service.execute(
                    ReadResources(_access("resources:read"), PROJECT_ID, None, invalid_limit)
                )
            self.assertEqual(caught.exception.status, 422)
        self.assertEqual(repository.calls, [])

    async def test_project_and_resource_reads_hide_other_project_or_missing_records(self) -> None:
        repository = FakePlatformLedgerRepository()
        access = _access("resources:read")

        with self.assertRaises(PlatformRequestError) as project_error:
            authorize_platform_action(ReadProject(access, OTHER_PROJECT_ID))
        with self.assertRaises(PlatformRequestError):
            await ReadProjectHandler(repository).execute(ReadProject(access, PROJECT_ID))
        with self.assertRaises(PlatformRequestError) as resource_error:
            await ReadResourceHandler(repository).execute(ReadResource(access, RESOURCE_ID))
        with self.assertRaises(PlatformRequestError) as operation_error:
            await ReadOperationHandler(repository).execute(ReadOperation(access, OPERATION_ID))

        self.assertEqual(
            (
                project_error.exception.status,
                resource_error.exception.status,
                operation_error.exception.status,
            ),
            (404, 404, 404),
        )
        self.assertEqual(
            repository.calls,
            [
                ("find_project", PROJECT_ID),
                ("find_resource", PROJECT_ID, RESOURCE_ID),
                ("find_operation", PROJECT_ID, OPERATION_ID),
            ],
        )

    async def test_list_resources_forwards_only_bounded_page(self) -> None:
        repository = FakePlatformLedgerRepository()

        result = await ReadResourcesHandler(repository).execute(
            ReadResources(_access("resources:read"), PROJECT_ID, RESOURCE_ID, 100)
        )

        self.assertEqual(result, ())
        self.assertEqual(repository.calls, [("list_resources", PROJECT_ID, RESOURCE_ID, 100)])


class CatalogApplicationTests(unittest.TestCase):
    def test_catalog_exposes_default_postgres_as_not_requestable(self) -> None:
        result = asyncio.run(
            ReadCatalogQueryHandler().execute(ReadCatalog(_access("catalog:read")))
        )

        self.assertEqual(result.project_id, PROJECT_ID)
        self.assertEqual(len(result.templates), 1)
        self.assertFalse(result.templates[0].requestable)
        self.assertEqual(result.templates[0].template_id, "postgres")

    def test_catalog_requires_catalog_scope(self) -> None:
        with self.assertRaises(CatalogForbidden):
            authorize_platform_action(ReadCatalog(_access()))


if __name__ == "__main__":
    unittest.main()
