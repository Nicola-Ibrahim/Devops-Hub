"""Safe application-level authorization errors."""


class CatalogForbidden(Exception):
    """The access context cannot read the provisioning catalog."""

    code = "forbidden"
    message = "The token does not permit this action"

    def __init__(self) -> None:
        super().__init__(self.message)
