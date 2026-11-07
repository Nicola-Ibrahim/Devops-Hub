class IdentityUnavailable(Exception):
    code = "database_unavailable"
    message = "Database unavailable"

    def __init__(self) -> None:
        super().__init__(self.message)


class CredentialDeliveryError(Exception):
    code = "credential_delivery_failed"

    def __init__(self) -> None:
        self.message = "Credential delivery failed"
        super().__init__(self.message)
