"""Resource lifecycle ports and private worker values."""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class DatabaseCredentials:
    user: str
    database: str
    password: str = field(repr=False)
    administrator_password: str = field(repr=False)


@dataclass(frozen=True)
class ProvisioningJob:
    operation_id: UUID
    resource_id: UUID
    installation_id: UUID
    generation: int
    claim_token: UUID
    action: str
    cpu_millis: int
    memory_bytes: int
    credentials: DatabaseCredentials = field(repr=False)


@dataclass(frozen=True)
class DatabaseEndpoint:
    host: str
    port: int


@dataclass(frozen=True)
class DeletionObservation:
    absent: bool
    observed_owned_object: bool


class ProviderFailure(Exception):
    def __init__(self, code: str = "provider_unavailable", uncertain: bool = True) -> None:
        super().__init__(code)
        self.code = code
        self.uncertain = uncertain


class LocalDatabaseProvider(Protocol):
    async def provision(self, job: ProvisioningJob) -> DatabaseEndpoint: ...
    async def delete(self, job: ProvisioningJob) -> DeletionObservation: ...
    async def inspect(self, job: ProvisioningJob) -> DatabaseEndpoint | None: ...
    async def discover(self, installation_id: UUID) -> tuple[UUID, ...]: ...


class ResourceCredentialCipher(Protocol):
    def encrypt(self, resource_id: UUID, credentials: DatabaseCredentials) -> bytes: ...
    def decrypt(self, resource_id: UUID, ciphertext: bytes, key_id: str) -> DatabaseCredentials: ...


class ProvisioningQueue(Protocol):
    async def claim(self) -> ProvisioningJob | None: ...
    async def heartbeat(self, job: ProvisioningJob) -> bool: ...
    async def ready(self, job: ProvisioningJob, endpoint: DatabaseEndpoint) -> None: ...
    async def deleted(self, job: ProvisioningJob, observation: DeletionObservation) -> None: ...
    async def failed(self, job: ProvisioningJob, error: ProviderFailure) -> None: ...
    async def sweep(self) -> None: ...
    async def should_execute(self, job: ProvisioningJob) -> bool: ...
    async def reconcile(self, resource_ids: tuple[UUID, ...]) -> None: ...
