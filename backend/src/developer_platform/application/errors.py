"""Safe application-level authorization errors."""


class CatalogForbidden(Exception):
    """The access context cannot read the provisioning catalog."""

    code = "forbidden"
    message = "The token does not permit this action"

    def __init__(self) -> None:
        super().__init__(self.message)


class PlatformRequestError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def resource_not_found() -> PlatformRequestError:
    return PlatformRequestError("not_found", "Resource or project not found", 404)


def ledger_unavailable() -> PlatformRequestError:
    return PlatformRequestError("platform_unavailable", "Platform database unavailable", 503)
