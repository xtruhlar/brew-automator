import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import ignorelist, maintenance


class FakeBrew:
    """Stateful stand-in for brew: `upgrade` removes packages from the outdated
    list unless they're listed in `broken`, in which case it exits non-zero."""

    def __init__(self, formulae=None, casks=None, broken=(), doctor_exit=0, missing="",
                 cleanup_output=""):
        self.formulae = list(formulae or [])
        self.casks = list(casks or [])
        self.broken = set(broken)
        self.doctor_exit = doctor_exit
        self.missing = missing
        self.cleanup_output = cleanup_output
        self.calls = []

    def outdated_json(self):
        def item(name, old, new, pinned=False):
            return {"name": name, "installed_versions": [old], "current_version": new, "pinned": pinned}

        return json.dumps(
            {
                "formulae": [item(*f) for f in self.formulae],
                "casks": [item(*c) for c in self.casks],
            }
        )

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("outdated", "--json=v2"):
            return self.outdated_json(), 0
        if args and args[0] == "upgrade":
            if "--dry-run" in args:
                return "Would upgrade", 0
            kind = "formulae" if "--formula" in args else "casks"
            names = [a for a in args[1:] if not a.startswith("--")]
            failed = [n for n in names if n in self.broken]
            setattr(
                self,
                kind,
                [p for p in getattr(self, kind) if p[0] not in names or p[0] in self.broken],
            )
            if failed:
                return f"Error: {' '.join(failed)} failed", 1
            return f"Upgraded: {' '.join(names)}", 0
        if args and args[0] == "cleanup":
            return self.cleanup_output, 0
        if args == ("doctor",):
            return ("Warning: something" if self.doctor_exit else ""), self.doctor_exit
        if args == ("missing",):
            return self.missing, 0
        return "", 0

    def upgrade_calls(self):
        return [c for c in self.calls if c[0] == "upgrade"]


class RunMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        originals = {
            "STATE_DIR": maintenance.STATE_DIR,
            "LOG_DIR": maintenance.LOG_DIR,
            "REPORT_FILE": maintenance.REPORT_FILE,
            "LOG_FILE": maintenance.LOG_FILE,
            "_run_with_exit": maintenance._run_with_exit,
        }
        original_load_ignored = ignorelist.load_ignored

        def restore():
            for name, value in originals.items():
                setattr(maintenance, name, value)
            ignorelist.load_ignored = original_load_ignored

        self.addCleanup(restore)

        maintenance.STATE_DIR = Path(self.tmpdir.name)
        maintenance.LOG_DIR = maintenance.STATE_DIR / "logs"
        maintenance.REPORT_FILE = maintenance.STATE_DIR / "report.txt"
        maintenance.LOG_FILE = maintenance.LOG_DIR / "brew-maintenance.log"

    def _use(self, brew, ignored=None):
        maintenance._run_with_exit = brew
        ignorelist.load_ignored = lambda: ignored or {"formulae": [], "casks": []}
        return brew

    def test_report_has_separate_formula_and_cask_sections(self):
        self._use(FakeBrew(formulae=[("git", "2.40", "2.50")], casks=[("firefox", "1.0", "2.0")]))
        result = maintenance.run_maintenance()
        self.assertIn("== brew outdated — Formulae", result["report"])
        self.assertIn("== brew outdated — Casks", result["report"])
        self.assertIn("git 2.40 -> 2.50", result["report"])
        self.assertIn("firefox 1.0 -> 2.0", result["report"])

    def test_summary_is_first_section_and_lists_upgrades(self):
        self._use(FakeBrew(formulae=[("git", "2.40", "2.50")], casks=[("firefox", "1.0", "2.0")]))
        result = maintenance.run_maintenance()
        self.assertTrue(result["report"].split("\n\n")[1].startswith("== Summary =="))
        self.assertIn("Status: OK", result["summary"])
        self.assertIn("Upgraded (2): git (2.40 -> 2.50), firefox (1.0 -> 2.0)", result["summary"])
        self.assertEqual([p["name"] for p in result["upgraded"]], ["git", "firefox"])
        self.assertEqual(result["failed"], [])
        self.assertFalse(result["has_problem"])

    def test_failed_upgrade_is_a_problem(self):
        self._use(
            FakeBrew(formulae=[("git", "2.40", "2.50"), ("node", "20", "21")], broken={"node"})
        )
        result = maintenance.run_maintenance()
        self.assertTrue(result["has_problem"])
        self.assertEqual([p["name"] for p in result["failed"]], ["node"])
        self.assertEqual([p["name"] for p in result["upgraded"]], ["git"])
        self.assertIn("Status: PROBLEM", result["summary"])
        self.assertIn("Failed (1): node (20 -> 21)", result["summary"])

    def test_nonzero_upgrade_exit_without_leftovers_is_still_a_problem(self):
        brew = FakeBrew(formulae=[("git", "2.40", "2.50")])
        original = brew.__call__

        def flaky(*args):
            output, code = original(*args)
            return (output, 1) if args[0] == "upgrade" else (output, code)

        self._use(flaky)
        result = maintenance.run_maintenance()
        self.assertTrue(result["has_problem"])
        self.assertIn("exited with code 1", result["summary"])

    def test_doctor_and_missing_problems_detected(self):
        self._use(FakeBrew(doctor_exit=1))
        self.assertTrue(maintenance.run_maintenance()["has_problem"])
        self._use(FakeBrew(missing="foo: bar"))
        self.assertTrue(maintenance.run_maintenance()["has_problem"])

    def test_ignored_formula_is_excluded_from_upgrade(self):
        brew = self._use(
            FakeBrew(formulae=[("git", "2.40", "2.50"), ("node", "20", "21")]),
            ignored={"formulae": ["git"], "casks": []},
        )
        result = maintenance.run_maintenance()
        upgraded_names = " ".join(" ".join(call) for call in brew.upgrade_calls())
        self.assertNotIn("git", upgraded_names)
        self.assertIn("node", upgraded_names)
        self.assertEqual([(p["name"], p["reason"]) for p in result["skipped"]], [("git", "excluded")])

    def test_ignored_formula_listed_as_skipped_in_report(self):
        self._use(
            FakeBrew(formulae=[("git", "2.40", "2.50")]),
            ignored={"formulae": ["git"], "casks": []},
        )
        result = maintenance.run_maintenance()
        self.assertIn("== Skipped (excluded via 'brew-automator settings' or pinned) ==", result["report"])
        self.assertIn("Formulae: git", result["report"])
        self.assertIn("Skipped (1): git (excluded)", result["summary"])

    def test_pinned_formula_is_skipped_not_failed(self):
        brew = FakeBrew()
        brew.outdated_json = lambda: json.dumps(
            {"formulae": [{"name": "git", "installed_versions": ["1"], "current_version": "2",
                           "pinned": True}], "casks": []}
        )
        self._use(brew)
        result = maintenance.run_maintenance()
        self.assertEqual(brew.upgrade_calls(), [])
        self.assertEqual([(p["name"], p["reason"]) for p in result["skipped"]], [("git", "pinned")])
        self.assertFalse(result["has_problem"])

    def test_no_upgrade_call_when_nothing_outdated(self):
        brew = self._use(FakeBrew())
        result = maintenance.run_maintenance()
        self.assertEqual(brew.upgrade_calls(), [])
        self.assertEqual(result["short_summary"], "Nothing to update")

    def test_freed_space_is_parsed_from_cleanup(self):
        self._use(
            FakeBrew(cleanup_output="Removing: foo\nThis operation has freed approximately 1.2GB of disk space.")
        )
        result = maintenance.run_maintenance()
        self.assertEqual(result["freed"], "1.2GB")
        self.assertIn("Freed by cleanup: 1.2GB", result["summary"])

    def test_no_upgrade_mode_neither_upgrades_nor_cleans_up(self):
        brew = self._use(FakeBrew(formulae=[("git", "2.40", "2.50")]))
        result = maintenance.run_maintenance(maintenance.MODE_NO_UPGRADE)
        self.assertEqual(brew.upgrade_calls(), [])
        self.assertFalse(any(c[0] == "cleanup" for c in brew.calls))
        self.assertIn("Outdated, not upgraded (1): git", result["summary"])
        self.assertTrue(maintenance.REPORT_FILE.exists())

    def test_dry_run_passes_dry_run_flag_and_writes_no_report(self):
        brew = self._use(
            FakeBrew(
                formulae=[("git", "2.40", "2.50")],
                cleanup_output="This operation would free approximately 300MB of disk space.",
            )
        )
        result = maintenance.run_maintenance(maintenance.MODE_DRY_RUN)
        self.assertTrue(all("--dry-run" in c for c in brew.upgrade_calls()))
        self.assertIn(("cleanup", "--dry-run"), brew.calls)
        self.assertIn("Would upgrade (1): git", result["summary"])
        self.assertIn("Would free: 300MB", result["summary"])
        self.assertFalse(maintenance.REPORT_FILE.exists())

    def test_outdated_json_with_leading_warning_is_parsed(self):
        brew = FakeBrew(formulae=[("git", "2.40", "2.50")])
        original = brew.outdated_json
        brew.outdated_json = lambda: "Warning: some notice\n" + original()
        self._use(brew)
        result = maintenance.run_maintenance(maintenance.MODE_NO_UPGRADE)
        self.assertEqual([p["name"] for p in result["upgraded"]], ["git"])


if __name__ == "__main__":
    unittest.main()
