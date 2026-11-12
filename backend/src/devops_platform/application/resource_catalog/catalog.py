"""Approved PostgreSQL options and availability policy."""

from devops_platform.application.database_provisioning.submit_database_request.command import (
    DatabaseRequest,
)
from devops_platform.application.resource_catalog.models import PostgresOption
from devops_platform.application.shared.errors import PlatformRequestError


class ApprovedPostgresCatalog:
    def __init__(self, options: tuple[PostgresOption, ...] = (PostgresOption(),)) -> None:
        self.options = options

    def require_option(self, command: DatabaseRequest) -> PostgresOption:
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
