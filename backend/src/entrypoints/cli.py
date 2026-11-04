"""Administrative host: arguments and presentation, with explicitly wired use cases."""

import argparse
import asyncio
import getpass
import secrets
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from api.identity.browser import BrowserIdentityOperations
from containers.browser_operations import BrowserIdentityService
from containers.factory import create_container
from containers.operations import IssueApiTokenToFile, RevokeApiTokenCommand
from containers.platform_operations import RegisterProjectCommandHandler
from developer_platform.application.errors import PlatformRequestError
from developer_platform.application.ledger import RegisterProjectCommand
from developer_platform.application.lifecycle import DatabaseCredentials, ProvisioningJob
from developer_platform.application.permissions import ALL_SCOPES
from developer_platform.infra.docker_provider import DockerPostgresProvider
from developer_platform.infra.persistence.models import QuotaBudget
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
    register = commands.add_parser("register-project")
    register.add_argument("--name", required=True)
    register.add_argument("--team", required=True)
    register.add_argument("--repository", required=True)
    register.add_argument("--environment", required=True, action="append")
    create_user = commands.add_parser("create-user")
    create_user.add_argument("--name", required=True)
    create_user.add_argument("--password-file", type=Path)
    bootstrap = commands.add_parser("bootstrap-project-admin")
    bootstrap.add_argument("--user-id", type=UUID, required=True)
    bootstrap.add_argument("--project-id", type=UUID, required=True)
    setup = commands.add_parser("issue-password-setup")
    setup.add_argument("--user-id", type=UUID, required=True)
    setup.add_argument("--actor-id", type=UUID, required=True)
    setup.add_argument("--output", type=Path, required=True)
    consume = commands.add_parser("consume-password-setup")
    consume.add_argument("--token-file", type=Path, required=True)
    consume.add_argument("--password-file", type=Path)
    target = commands.add_parser("verify-local-target")
    target.add_argument("--max-resources", type=int, default=10)
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
        PlatformRequestError,
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
            elif args.command == "register-project":
                registration = await command_scope.get(RegisterProjectCommandHandler)
                project = await registration.execute(
                    RegisterProjectCommand(
                        args.name,
                        args.team,
                        args.repository,
                        tuple(args.environment),
                    )
                )
                print(f"Project registered: {project.project_id}.")
                for environment in project.environments:
                    print(f"Environment {environment.name}: {environment.id}.")
            elif args.command in {
                "create-user",
                "bootstrap-project-admin",
                "issue-password-setup",
                "consume-password-setup",
            }:
                browser = await command_scope.get(BrowserIdentityOperations)
                assert isinstance(browser, BrowserIdentityService)
                if args.command == "create-user":
                    password = read_password(args.password_file)
                    user_id = await browser.create_user(args.name, password)
                    print(f"User created: {user_id}.")
                elif args.command == "bootstrap-project-admin":
                    await browser.bootstrap_first_project_admin(args.user_id, args.project_id)
                    print("Initial project administrator configured.")
                elif args.command == "issue-password-setup":
                    secret = await browser.issue_password_setup(args.user_id, args.actor_id)
                    PrivateCredentialFile(args.output).write_new(secret)
                    print("One-time setup secret written to requested private file.")
                else:
                    if not await browser.consume_password_setup(
                        args.token_file.read_text().strip(), read_password(args.password_file)
                    ):
                        raise ValueError("Setup secret is invalid or expired")
                    print("Password configured.")
            elif args.command == "verify-local-target":
                if (
                    config.installation_id is None
                    or config.resource_key is None
                    or args.max_resources < 1
                ):
                    raise ValueError("Configure stable installation and encryption key first")
                from uuid import uuid4

                engine = await command_scope.get(AsyncEngine)
                provider = DockerPostgresProvider(
                    config.docker_url, config.postgres_image, config.advertised_host
                )
                job = ProvisioningJob(
                    uuid4(),
                    uuid4(),
                    config.installation_id,
                    1,
                    uuid4(),
                    "provision",
                    500,
                    536870912,
                    DatabaseCredentials(
                        "verify_user",
                        "verify_db",
                        secrets.token_urlsafe(32),
                        secrets.token_urlsafe(32),
                    ),
                )
                try:
                    await provider.provision(job)
                finally:
                    observation = await provider.delete(job)
                    if not observation.absent:
                        raise ValueError("Probe cleanup incomplete")
                async with AsyncSession(engine) as session, session.begin():
                    row = await session.get(QuotaBudget, ("target", "local"), with_for_update=True)
                    if row is None:
                        row = QuotaBudget(
                            scope="target",
                            scope_id="local",
                            max_resources=args.max_resources,
                            max_cpu_millis=args.max_resources * 500,
                            max_memory_bytes=args.max_resources * 536870912,
                            max_storage_bytes=args.max_resources * 1073741824,
                        )
                        session.add(row)
                    else:
                        row.max_resources = args.max_resources
                        row.max_cpu_millis = args.max_resources * 500
                        row.max_memory_bytes = args.max_resources * 536870912
                        row.max_storage_bytes = args.max_resources * 1073741824
                print(
                    "Local PostgreSQL target provision/readiness/cleanup verified; "
                    "capacity configured."
                )
            else:
                revoke = await command_scope.get(RevokeApiTokenCommand)
                if not await revoke.execute(args.token_id):
                    raise IdentityValidationError("Unknown token ID")
                print("Token revoked.")
    finally:
        await container.close()


def read_password(path: Path | None) -> str:
    if path is None:
        return getpass.getpass("Password: ")
    if path.stat().st_mode & 0o077:
        raise ValueError("Password file must be private")
    value = path.read_text().strip()
    if not value:
        raise ValueError("Password is empty")
    return value
