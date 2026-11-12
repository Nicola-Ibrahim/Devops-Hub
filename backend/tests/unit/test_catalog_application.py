"""Unit tests for the provisioning catalog use case."""

import asyncio
import unittest
from uuid import UUID

from devops_hub.platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from devops_hub.platform.application.resource_catalog.query import ReadCatalog
from devops_hub.platform.application.shared.dto import AccessContext
from devops_hub.platform.application.shared.errors import CatalogForbidden
from devops_hub.platform.authorization import ALL_SCOPES, authorize_platform_action


class ReadCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = UUID("11111111-1111-4111-8111-111111111111")
        self.access = AccessContext(
            user_id=UUID("22222222-2222-4222-8222-222222222222"),
            project_id=self.project_id,
            role="developer",
            scopes=frozenset({"catalog:read"}),
        )

    def test_returns_disabled_option_for_authorized_project(self) -> None:
        result = asyncio.run(ReadCatalogQueryHandler().execute(ReadCatalog(self.access)))

        self.assertEqual(result.project_id, self.project_id)
        self.assertEqual(len(result.templates), 1)
        self.assertFalse(result.templates[0].requestable)
        self.assertEqual(
            result.message,
            "No verified provisioning provider is enabled; requests are disabled",
        )

    def test_denies_missing_scope_even_for_admin(self) -> None:
        admin = AccessContext(
            user_id=self.access.user_id,
            project_id=self.project_id,
            role="admin",
            scopes=frozenset(),
        )

        with self.assertRaises(CatalogForbidden) as caught:
            authorize_platform_action(ReadCatalog(admin))

        self.assertEqual(caught.exception.code, "forbidden")
        self.assertEqual(caught.exception.message, "The token does not permit this action")

    def test_permission_vocabulary_is_preserved(self) -> None:
        self.assertEqual(
            ALL_SCOPES,
            ("catalog:read", "resources:read", "resources:write", "connections:read"),
        )

    def test_preserves_project_context(self) -> None:
        other_project = UUID("33333333-3333-4333-8333-333333333333")
        access = AccessContext(
            user_id=self.access.user_id,
            project_id=other_project,
            role="developer",
            scopes=frozenset({"catalog:read"}),
        )

        self.assertEqual(
            asyncio.run(ReadCatalogQueryHandler().execute(ReadCatalog(access))).project_id,
            other_project,
        )
