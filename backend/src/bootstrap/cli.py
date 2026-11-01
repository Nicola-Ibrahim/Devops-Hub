"""Administrative host: arguments and presentation, with explicitly wired use cases."""

import argparse
import sys
from pathlib import Path
from uuid import UUID

from bootstrap.composition import build_services
from bootstrap.settings import Settings
from developer_platform.application.permissions import ALL_SCOPES
from identity.application.dto import IssueTokenCommand
from identity.application.errors import CredentialDeliveryError, IdentityUnavailable
from identity.domain.errors import IdentityValidationError
from identity.infra.credential_file import PrivateCredentialFile
from shared.infra.persistence.database import create_database_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Restricted local identity administration.")
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("issue-token")
    issue.add_argument("--user", required=True)
    issue.add_argument("--project", required=True)
    issue.add_argument("--output", required=True, type=Path)
    issue.add_argument("--hours", type=int, default=24)
    issue.add_argument("--scope", choices=ALL_SCOPES, action="append")
    revoke = commands.add_parser("revoke-token")
    revoke.add_argument("token_id", type=UUID)
    args = parser.parse_args()
    try:
        config = Settings()  # type: ignore[call-arg]
        engine = create_database_engine(
            config.database_url.get_secret_value(), config.database_connect_timeout
        )
        try:
            services = build_services(config, engine)
            if args.command == "issue-token":
                token_id = services.issue_token.execute(
                    IssueTokenCommand(
                        args.user,
                        args.project,
                        args.hours,
                        tuple(args.scope) if args.scope else None,
                    ),
                    PrivateCredentialFile(args.output),
                )
                print(f"Token issued: {token_id}. Credential written to the requested file.")
            elif not services.revoke_token.execute(args.token_id):
                raise IdentityValidationError("Unknown token ID")
            else:
                print("Token revoked.")
        finally:
            engine.dispose()
    except (
        ValueError,
        OSError,
        IdentityValidationError,
        IdentityUnavailable,
        CredentialDeliveryError,
    ):
        print(
            "Administration failed. Check configuration, migration state and output path.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
