"""Lifecycle application actions keep authorization and secrets out of ordinary views."""

import asyncio
from uuid import uuid4

import pytest

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import CatalogForbidden, PlatformRequestError
from developer_platform.application.lifecycle import DatabaseCredentials
from developer_platform.application.manage_databases import ManageDatabases
from developer_platform.domain.resource_lifecycle_repository import ResourceConnectionSecret


def test_connection_requires_scope_and_cipher_before_sensitive_read():
    class Repository:
        async def connection(self, **_kwargs):
            raise AssertionError("Unauthorized connection read reached persistence")

    project_id, user_id, resource_id = uuid4(), uuid4(), uuid4()
    forbidden = AccessContext(user_id, project_id, "developer", frozenset())
    allowed = AccessContext(user_id, project_id, "developer", frozenset({"connections:read"}))

    with pytest.raises(CatalogForbidden):
        asyncio.run(ManageDatabases(Repository(), None).connection(forbidden, resource_id))
    with pytest.raises(PlatformRequestError) as error:
        asyncio.run(ManageDatabases(Repository(), None).connection(allowed, resource_id))
    assert error.value.code == "credentials_unavailable"


def test_connection_encodes_credential_components_without_exposing_repr():
    resource_id, project_id, user_id = uuid4(), uuid4(), uuid4()

    class Repository:
        async def connection(self, **kwargs):
            assert kwargs["resource_id"] == resource_id
            assert kwargs["project_id"] == project_id
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
    result = asyncio.run(ManageDatabases(Repository(), Cipher()).connection(access, resource_id))
    assert result.connection_string == ("postgresql://user%40name:pass%3Aword@[::1]:5432/db%2Fname")
    assert "pass:word" not in repr(result)
