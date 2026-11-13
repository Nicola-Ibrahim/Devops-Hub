"""Exercise Bash routing and cache boundaries with an isolated mocked Docker CLI."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]


class DeveloperCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("scripts/helpers", "backend", "frontend", "bin"):
            (self.root / name).mkdir(parents=True)
        shutil.copy(SOURCE / "dev.sh", self.root / "scripts/dev.sh")
        shutil.copy(
            SOURCE / "helpers/init_env.py", self.root / "scripts/helpers/init_env.py"
        )
        self.log = self.root / "docker.calls"
        mock = self.root / "bin/docker"
        mock.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_TEST_LOG"\n'
            'if [ "$1" = info ]; then exit "${DOCKER_TEST_INFO:-0}"; fi\n'
            'if [ "$1" = volume ]; then exit 0; fi\nexit 0\n'
        )
        mock.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"],
            DOCKER_TEST_LOG=str(self.log),
            DOCKER_HOST="unix:///tmp/mock-docker.sock",
            DOCKER_CONTEXT="",
        )

    def run_command(self, *args, **environment):
        return subprocess.run(
            ["bash", str(self.root / "scripts/dev.sh"), *args],
            check=False,
            cwd="/",
            env=dict(self.env, **environment),
            text=True,
            capture_output=True,
        )

    def test_help_and_invalid_options_have_no_docker_or_env_effects(self):
        self.assertEqual(self.run_command("help").returncode, 0)
        self.assertEqual(self.run_command("up", "--unknown").returncode, 2)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.root / "backend/.env").exists())

    def test_unreachable_daemon_does_not_generate_credentials(self):
        self.assertNotEqual(self.run_command("up", DOCKER_TEST_INFO="1").returncode, 0)
        self.assertFalse((self.root / "backend/.env").exists())

    def test_remote_daemon_is_refused_for_start_and_stop(self):
        for action in ("up", "down", "status"):
            self.assertNotEqual(
                self.run_command(
                    action, DOCKER_HOST="tcp://remote.invalid:2375"
                ).returncode,
                0,
            )
        self.assertFalse(self.log.exists())
        self.assertFalse((self.root / "backend/.env").exists())

    def test_up_and_down_route_profiles_and_preserve_volumes(self):
        result = self.run_command("up", "--resources", "--application-delivery")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "--profile app --profile resources --profile application-delivery up --build -d --wait",
            self.log.read_text(),
        )
        self.assertEqual(self.run_command("down").returncode, 0)
        self.assertIn(
            "--profile app --profile resources --profile application-delivery down",
            self.log.read_text(),
        )
        self.assertNotIn("--volumes", self.log.read_text())

    def test_clean_is_preview_first_and_refuses_symlink(self):
        cache = self.root / "backend/.pytest_cache"
        cache.mkdir()
        sentinel = cache / "sentinel"
        sentinel.write_text("cache")
        self.assertEqual(self.run_command("clean").returncode, 0)
        self.assertTrue(sentinel.exists())
        self.assertEqual(self.run_command("clean", "--apply").returncode, 0)
        self.assertFalse(cache.exists())
        cache.symlink_to(self.root / "frontend", target_is_directory=True)
        self.assertNotEqual(self.run_command("clean", "--apply").returncode, 0)
        self.assertTrue((self.root / "frontend").is_dir())
        self.assertEqual(self.run_command("logs", "arbitrary").returncode, 2)


if __name__ == "__main__":
    unittest.main()
