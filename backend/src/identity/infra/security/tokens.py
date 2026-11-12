"""Token fingerprinting and generation adapters."""

import hashlib
import hmac
import secrets


def token_digest(token: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


class PepperedTokenHasher:
    def __init__(self, pepper: str) -> None:
        if len(pepper) < 32:
            raise ValueError("Token pepper must have at least 32 characters")
        self._pepper = pepper

    def __repr__(self) -> str:
        return f"{type(self).__name__}(pepper=<redacted>)"

    def digest(self, token: str) -> str:
        return token_digest(token, self._pepper)


class SecureTokenGenerator:
    def generate(self) -> str:
        return secrets.token_urlsafe(32)
