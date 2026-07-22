import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import maintenance


class RunMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        self.original_state_dir = maintenance.STATE_DIR
        self.original_log_dir = maintenance.LOG_DIR
        self.original_report_file = maintenance.REPORT_FILE
        self.original_log_file = maintenance.LOG_FILE
        maintenance.STATE_DIR = Path(self.tmpdir.name)
        maintenance.LOG_DIR = maintenance.STATE_DIR / "logs"
        maintenance.REPORT_FILE = maintenance.STATE_DIR / "report.txt"
        maintenance.LOG_FILE = maintenance.LOG_DIR / "brew-maintenance.log"
        self.addCleanup(self._restore_paths)

        self.original_run = maintenance._run
        self.original_run_with_exit = maintenance._run_with_exit
        self.addCleanup(self._restore_run_fns)

    def _restore_paths(self):
        maintenance.STATE_DIR = self.original_state_dir
        maintenance.LOG_DIR = self.original_log_dir
        maintenance.REPORT_FILE = self.original_report_file
        maintenance.LOG_FILE = self.original_log_file

    def _restore_run_fns(self):
        maintenance._run = self.original_run
        maintenance._run_with_exit = self.original_run_with_exit

    def _fake_brew(self, formula_outdated="", cask_outdated=""):
        def fake_run(*args):
            if args == ("outdated", "--formula"):
                return formula_outdated
            if args == ("outdated", "--cask", "--greedy"):
                return cask_outdated
            return ""

        def fake_run_with_exit(*args):
            return "", 0

        maintenance._run = fake_run
        maintenance._run_with_exit = fake_run_with_exit

    def test_report_has_separate_formula_and_cask_sections(self):
        self._fake_brew(formula_outdated="git 2.40 -> 2.50", cask_outdated="firefox 1.0 -> 2.0")
        result = maintenance.run_maintenance()
        self.assertIn("== brew outdated — Formulae", result["report"])
        self.assertIn("== brew outdated — Casks", result["report"])
        self.assertIn("git 2.40 -> 2.50", result["report"])
        self.assertIn("firefox 1.0 -> 2.0", result["report"])

    def test_outdated_summary_combines_both(self):
        self._fake_brew(formula_outdated="git 2.40 -> 2.50", cask_outdated="firefox 1.0 -> 2.0")
        result = maintenance.run_maintenance()
        self.assertIn("git 2.40 -> 2.50", result["outdated"])
        self.assertIn("firefox 1.0 -> 2.0", result["outdated"])

    def test_outdated_summary_empty_when_nothing_outdated(self):
        self._fake_brew(formula_outdated="", cask_outdated="")
        result = maintenance.run_maintenance()
        self.assertEqual(result["outdated"], "")


if __name__ == "__main__":
    unittest.main()
