"""Focused, filesystem-isolated tests for the standalone local env initializer."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "helpers" / "init_env.py"
SPEC = importlib.util.spec_from_file_location("init_env", MODULE)
init_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(init_env)


class InitEnvTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "backend").mkdir()
        (self.root / "frontend").mkdir()
        self.volume_check = patch.object(
            init_env, "control_plane_volume_exists", return_value=False
        )
        self.volume_check.start()
        self.addCleanup(self.volume_check.stop)

    def tearDown(self):
        self.temp.cleanup()

    def test_creates_private_files_without_printing_values(self):
        init_env.initialize(self.root)
        backend = self.root / "backend/.env"
        frontend = self.root / "frontend/.env"
        self.assertEqual(backend.stat().st_mode & 0o777, 0o600)
        self.assertEqual(frontend.stat().st_mode & 0o777, 0o600)
        self.assertIn("PLATFORM_DATABASE_URL=", backend.read_text())

    def test_existing_complete_files_are_preserved_and_made_private(self):
        backend = self.root / "backend/.env"
        frontend = self.root / "frontend/.env"
        backend.write_text(
            "POSTGRES_PASSWORD=old\nPLATFORM_DATABASE_URL=db\nPLATFORM_TOKEN_PEPPER=x\nPLATFORM_INSTALLATION_ID=id\nPLATFORM_RESOURCE_KEY=key\n"
        )
        frontend.write_text("BACKEND_URL=http://api:8000\n")
        backend.chmod(0o644)
        init_env.initialize(self.root)
        self.assertIn("POSTGRES_PASSWORD=old", backend.read_text())
        self.assertEqual(backend.stat().st_mode & 0o777, 0o600)

    def test_incomplete_existing_file_is_not_overwritten(self):
        backend = self.root / "backend/.env"
        backend.write_text("CUSTOM=value\n")
        with self.assertRaisesRegex(RuntimeError, "missing"):
            init_env.initialize(self.root)
        self.assertEqual(backend.read_text(), "CUSTOM=value\n")

    def test_symlink_env_is_refused(self):
        outside = self.root / "outside"
        outside.write_text("untouched\n")
        (self.root / "backend/.env").symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            init_env.initialize(self.root)
        self.assertEqual(outside.read_text(), "untouched\n")

    def test_partial_legacy_secret_set_is_refused(self):
        legacy = self.root / ".local/secrets"
        legacy.mkdir(parents=True)
        (legacy / init_env.LEGACY_NAMES[0]).write_text("old\n")
        with self.assertRaisesRegex(RuntimeError, "Incomplete legacy"):
            init_env.initialize(self.root)

    def test_symlink_component_directory_is_refused(self):
        (self.root / "backend").rmdir()
        (self.root / "backend").symlink_to(
            self.root / "frontend", target_is_directory=True
        )
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            init_env.initialize(self.root)
        self.assertFalse((self.root / "frontend/.env").exists())


class VolumeDetectionTests(unittest.TestCase):
    def test_volume_query_failure_is_not_treated_as_absence(self):
        from subprocess import CompletedProcess

        with (
            patch.object(init_env.shutil, "which", return_value="mock-docker"),
            patch.object(
                init_env.subprocess,
                "run",
                side_effect=[
                    CompletedProcess([], 0),
                    CompletedProcess([], 1, stdout=""),
                ],
            ),
            self.assertRaisesRegex(RuntimeError, "could not determine"),
        ):
            init_env.control_plane_volume_exists()


if __name__ == "__main__":
    unittest.main()
