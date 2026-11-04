"""Password and opaque-secret primitives for the internal identity adapter."""

import hashlib
import hmac
import secrets

_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1


class ScryptPasswordHasher:
    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        value = hashlib.scrypt(
            password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
        )
        return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${value.hex()}"

    def verify(self, password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$", 5)
            if (
                algorithm != "scrypt"
                or int(n) != _SCRYPT_N
                or int(r) != _SCRYPT_R
                or int(p) != _SCRYPT_P
            ):
                return False
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(expected_hex)
            if len(salt) != 16 or len(expected) != 32:
                return False
            candidate = hashlib.scrypt(
                password.encode(),
                salt=salt,
                n=_SCRYPT_N,
                r=_SCRYPT_R,
                p=_SCRYPT_P,
                dklen=len(expected),
            )
            return hmac.compare_digest(candidate, expected)
        except (ValueError, TypeError, MemoryError):
            return False


class OpaqueSecretGenerator:
    def generate(self) -> str:
        return secrets.token_urlsafe(32)


def secret_digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()
