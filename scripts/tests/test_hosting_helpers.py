"""Host helper checks use temporary files only; no host or Docker effects."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HELPERS = Path(__file__).resolve().parents[2] / "ops/hosting/scripts/helpers"


def load(name):
    spec = importlib.util.spec_from_file_location(name, HELPERS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostingHelperTests(unittest.TestCase):
    def test_storage_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "daemon.json"
            path.write_text('{"log-driver":"local"}')
            load("configure_docker_storage").configure(path, "/approved/data")
            self.assertEqual(
                json.loads(path.read_text()),
                {"log-driver": "local", "data-root": "/approved/data"},
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_conflicting_or_invalid_storage_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "daemon.json"
            for content in ('{"data-root":"/other"}', "[]", "invalid"):
                path.write_text(content)
                with self.assertRaises((ValueError, TypeError)):
                    load("configure_docker_storage").configure(path, "/approved/data")
                self.assertEqual(path.read_text(), content)

    def test_storage_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "outside"
            target.write_text("{}")
            path = Path(folder) / "daemon.json"
            path.symlink_to(target)
            with self.assertRaises((ValueError, TypeError)):
                load("configure_docker_storage").configure(path, "/approved/data")
            self.assertEqual(target.read_text(), "{}")

    def test_restore_password_is_private_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            name = load("prepare_restore").prepare(directory)
            path = directory / "postgres_password"
            before = path.read_bytes()
            self.assertTrue(name.startswith("devops-hub-restore-"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(before.strip().decode(), name)
            with self.assertRaises(FileExistsError):
                load("prepare_restore").prepare(directory)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
