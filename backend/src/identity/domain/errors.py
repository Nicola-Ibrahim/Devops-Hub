class AuthenticationRejected(Exception):
    code = "unauthenticated"
    message = "A valid bearer token is required"

    def __init__(self) -> None:
        super().__init__(self.message)


class IdentityValidationError(Exception):
    code = "invalid_identity_input"

    def __init__(self, message: str = "Invalid identity input") -> None:
        self.message = message
        super().__init__(message)
