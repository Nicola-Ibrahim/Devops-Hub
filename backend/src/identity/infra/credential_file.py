"""Exclusive private-file delivery for locally issued credentials."""

import os
from pathlib import Path

from identity.application.errors import CredentialDeliveryError


class _FileOwnershipReceipt:
    def __init__(self, path: Path, device: int, inode: int) -> None:
        self._path = path
        self._device = device
        self._inode = inode

    def remove_owned(self) -> None:
        try:
            stat = self._path.stat(follow_symlinks=False)
            if (stat.st_dev, stat.st_ino) == (self._device, self._inode):
                self._path.unlink()
        except FileNotFoundError:
            return


class PrivateCredentialFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write_new(self, secret: str) -> _FileOwnershipReceipt:
        descriptor: int | None = None
        ownership: tuple[int, int] | None = None
        try:
            descriptor = os.open(
                self._path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            stat = os.fstat(descriptor)
            ownership = (stat.st_dev, stat.st_ino)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                descriptor = None
                output.write(secret + "\n")
                output.flush()
                os.fsync(output.fileno())
            return _FileOwnershipReceipt(self._path, stat.st_dev, stat.st_ino)
        except BaseException as primary:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except BaseException:
                    primary.add_note(
                        "Credential file cleanup failed; the original failure was preserved."
                    )
            if ownership is not None:
                try:
                    stat = self._path.stat(follow_symlinks=False)
                    if (stat.st_dev, stat.st_ino) == ownership:
                        self._path.unlink()
                except FileNotFoundError:
                    pass
                except BaseException:
                    primary.add_note(
                        "Credential file cleanup failed; the original failure was preserved."
                    )
            if not isinstance(primary, Exception):
                raise
            raise CredentialDeliveryError() from primary
