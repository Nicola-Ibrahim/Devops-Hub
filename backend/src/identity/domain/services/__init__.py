"""Identity domain services for rules spanning multiple identity records."""

from identity.domain.services.token_authentication import AuthenticatedIdentity, authenticate_token

__all__ = ["AuthenticatedIdentity", "authenticate_token"]
