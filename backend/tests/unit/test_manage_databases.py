"""Lifecycle application actions keep authorization and secrets out of ordinary views."""

import asyncio
from uuid import uuid4

import pytest
from developer_platform.application.resource_lifecycle.ports import DatabaseCredentials

from developer_platform.application.database_lifecycle.read_connection.handler import (
    GetDatabaseConnectionQueryHandler,
)
from developer_platform.application.database_lifecycle.read_connection.query import (
    ReadDatabaseConnection,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import CatalogForbidden, PlatformRequestError
from developer_platform.application.shared.resource_repository import ResourceConnectionSecret
from developer_platform.authorization import authorize_platform_action


def test_connection_requires_scope_and_cipher_before_sensitive_read():
    class Repository:
        async def connection(self, **_kwargs):
            raise AssertionError("Unauthorized connection read reached persistence")

    project_id, user_id, resource_id = uuid4(), uuid4(), uuid4()
    forbidden = AccessContext(user_id, project_id, "developer", frozenset())
    allowed = AccessContext(user_id, project_id, "developer", frozenset({"connections:read"}))

    with pytest.raises(CatalogForbidden):
        authorize_platform_action(ReadDatabaseConnection(forbidden, resource_id))
    with pytest.raises(PlatformRequestError) as error:
        asyncio.run(
            GetDatabaseConnectionQueryHandler(Repository(), None).execute(
                ReadDatabaseConnection(allowed, resource_id)
            )
        )
    assert error.value.code == "credentials_unavailable"


def test_connection_encodes_credential_components_without_exposing_repr():
    resource_id, project_id, user_id = uuid4(), uuid4(), uuid4()

    class Repository:
        async def connection(self, **kwargs):
            assert kwargs["resource_id"] == resource_id
            assert kwargs["access"].project_id == project_id
            return ResourceConnectionSecret(resource_id, "::1", 5432, b"encrypted", "key-1")

    class Cipher:
        def decrypt(self, actual_id, ciphertext, key_id):
            assert (actual_id, ciphertext, key_id) == (resource_id, b"encrypted", "key-1")
            return DatabaseCredentials(
                user="user@name",
                database="db/name",
                password="pass:word",
                administrator_password="private-admin",
            )

    access = AccessContext(user_id, project_id, "developer", frozenset({"connections:read"}))
    result = asyncio.run(
        GetDatabaseConnectionQueryHandler(Repository(), Cipher()).execute(
            ReadDatabaseConnection(access, resource_id)
        )
    )
    assert result.connection_string == ("postgresql://user%40name:pass%3Aword@[::1]:5432/db%2Fname")
    assert "pass:word" not in repr(result)
