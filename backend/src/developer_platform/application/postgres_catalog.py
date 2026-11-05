"""Approved PostgreSQL options and availability policy."""

from developer_platform.application.errors import PlatformRequestError
from developer_platform.domain.ledger import PostgresOption, RequestDatabaseCommand


class ApprovedPostgresCatalog:
    def __init__(self, options: tuple[PostgresOption, ...] = (PostgresOption(),)) -> None:
        self.options = options

    def require_option(self, command: RequestDatabaseCommand) -> PostgresOption:
        for option in self.options:
            if (option.template_id, option.version, option.target_id, option.size.id) == (
                command.template_id,
                command.version,
                command.target_id,
                command.size_id,
            ):
                if not option.requestable:
                    raise PlatformRequestError(
                        "provider_unavailable", "Provisioning is not enabled for this option", 503
                    )
                return option
        raise PlatformRequestError("unsupported_option", "Unsupported catalog option", 422)
