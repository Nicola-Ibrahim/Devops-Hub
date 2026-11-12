import os
import stat

import pytest

from identity.application.shared.errors import CredentialDeliveryError
from identity.infra.security.credential_file import PrivateCredentialFile


def test_exclusive_private_output(tmp_path):
    path = tmp_path / "token"
    receipt = PrivateCredentialFile(path).write_new("synthetic-secret")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(CredentialDeliveryError):
        PrivateCredentialFile(path).write_new("replacement")
    assert path.read_text() == "synthetic-secret\n"
    receipt.remove_owned()
    assert not path.exists()


def test_cleanup_never_removes_a_replacement_file(tmp_path):
    path = tmp_path / "token"
    receipt = PrivateCredentialFile(path).write_new("synthetic-secret")
    replacement = tmp_path / "other"
    replacement.write_text("unrelated")
    replacement.replace(path)
    receipt.remove_owned()
    assert path.read_text() == "unrelated"


@pytest.mark.parametrize("failure", [OSError("simulated I/O failure"), KeyboardInterrupt()])
def test_partial_delivery_cleanup_preserves_failure_class(tmp_path, monkeypatch, failure):
    def fail_fsync(descriptor):
        raise failure

    monkeypatch.setattr(os, "fsync", fail_fsync)
    path = tmp_path / "token"
    expected = (
        KeyboardInterrupt if isinstance(failure, KeyboardInterrupt) else CredentialDeliveryError
    )
    with pytest.raises(expected):
        PrivateCredentialFile(path).write_new("synthetic-secret")
    assert not path.exists()
