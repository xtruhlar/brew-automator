import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN = REPO_ROOT / "bin" / "brew-automator"


def run(*args):
    return subprocess.run([sys.executable, str(BIN), *args], capture_output=True, text=True)


class CliSmokeTests(unittest.TestCase):
    def test_help_exits_zero(self):
        result = run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("brew-automator", result.stdout)

    def test_no_command_exits_nonzero(self):
        result = run()
        self.assertNotEqual(result.returncode, 0)

    def test_schedule_help_lists_subcommands(self):
        result = run("schedule", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("install", result.stdout)
        self.assertIn("remove", result.stdout)
        self.assertIn("status", result.stdout)

    def test_version_exits_zero(self):
        result = run("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("brew-automator", result.stdout)


if __name__ == "__main__":
    unittest.main()
