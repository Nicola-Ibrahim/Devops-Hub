"""Administrative host: arguments and presentation, with explicitly wired use cases."""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

from containers.factory import create_container
from containers.operations import IssueApiTokenToFile, RevokeApiTokenCommand
from developer_platform.application.permissions import ALL_SCOPES
from entrypoints.settings import Settings
from identity.application.dto import IssueTokenCommand
from identity.application.errors import CredentialDeliveryError, IdentityUnavailable
from identity.domain.errors import IdentityValidationError
from identity.infra.credential_file import PrivateCredentialFile


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
        asyncio.run(run_command(config, args))
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


async def run_command(config: Settings, args: argparse.Namespace) -> None:
    container = create_container(config)
    try:
        async with container() as command_scope:
            if args.command == "issue-token":
                service = await command_scope.get(IssueApiTokenToFile)
                token_id = await service.execute(
                    IssueTokenCommand(
                        args.user,
                        args.project,
                        args.hours,
                        tuple(args.scope) if args.scope else None,
                    ),
                    PrivateCredentialFile(args.output),
                )
                print(f"Token issued: {token_id}. Credential written to the requested file.")
            else:
                revoke = await command_scope.get(RevokeApiTokenCommand)
                if not await revoke.execute(args.token_id):
                    raise IdentityValidationError("Unknown token ID")
                print("Token revoked.")
    finally:
        await container.close()
