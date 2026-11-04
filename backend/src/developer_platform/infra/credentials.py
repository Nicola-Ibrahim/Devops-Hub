"""Authenticated encrypted credentials bound to their resource and key identity."""

import json
from dataclasses import asdict
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from developer_platform.application.lifecycle import DatabaseCredentials, ProviderFailure


class FernetResourceCredentialCipher:
    def __init__(self, key: str, key_id: str) -> None:
        self._cipher = Fernet(key.encode())
        self.key_id = key_id

    def encrypt(self, resource_id: UUID, credentials: DatabaseCredentials) -> bytes:
        return self._cipher.encrypt(
            json.dumps(
                {"resource_id": str(resource_id), "credentials": asdict(credentials)}
            ).encode()
        )

    def decrypt(self, resource_id: UUID, ciphertext: bytes, key_id: str) -> DatabaseCredentials:
        if key_id != self.key_id:
            raise ProviderFailure("credential_key_unavailable", False)
        try:
            data = json.loads(self._cipher.decrypt(ciphertext))
            if data["resource_id"] != str(resource_id):
                raise ProviderFailure("credential_invalid", False)
            return DatabaseCredentials(**data["credentials"])
        except (InvalidToken, ValueError, KeyError, TypeError) as error:
            raise ProviderFailure("credential_invalid", False) from error
