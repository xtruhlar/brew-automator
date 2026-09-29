import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import history


def make_result(mode="normal", upgraded=(), failed=(), has_problem=False):
    def pkg(name):
        return {"name": name, "kind": "formulae", "from": "1", "to": "2", "pinned": False}

    return {
        "mode": mode,
        "has_problem": has_problem,
        "upgraded": [pkg(n) for n in upgraded],
        "failed": [pkg(n) for n in failed],
        "skipped": [{**pkg("held"), "reason": "excluded"}],
        "freed": "10MB",
        "doctor_ok": True,
        "missing_output": "",
        "duration_s": 12.3,
    }


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original = history.HISTORY_FILE
        history.HISTORY_FILE = Path(self.tmpdir.name) / "history.jsonl"
        self.addCleanup(lambda: setattr(history, "HISTORY_FILE", self.original))

    def _output(self, **kwargs):
        buf = io.StringIO()
        with redirect_stdout(buf):
            history.show_history(**kwargs)
        return buf.getvalue()

    def test_empty_history(self):
        self.assertEqual(history.load_history(), [])
        self.assertIsNone(history.last_run())
        self.assertIn("No runs recorded yet", self._output())

    def test_record_and_load_roundtrip(self):
        history.record_run(make_result(upgraded=["git"]), notified=True, now=datetime(2026, 1, 2, 3, 4, 5))
        entry = history.last_run()
        self.assertEqual(entry["timestamp"], "2026-01-02T03:04:05")
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["upgraded"], [{"name": "git", "kind": "formulae", "from": "1", "to": "2"}])
        self.assertEqual(entry["skipped"][0]["reason"], "excluded")
        self.assertTrue(entry["notified"])

    def test_no_upgrade_mode_records_outdated_not_upgraded(self):
        history.record_run(make_result(mode="no-upgrade", upgraded=["git"]), notified=False)
        entry = history.last_run()
        self.assertEqual(entry["upgraded"], [])
        self.assertEqual(entry["outdated"][0]["name"], "git")

    def test_history_is_capped(self):
        original_max = history.MAX_ENTRIES
        history.MAX_ENTRIES = 3
        self.addCleanup(lambda: setattr(history, "MAX_ENTRIES", original_max))
        for i in range(5):
            history.record_run(make_result(upgraded=[f"pkg{i}"]), notified=False)
        names = [e["upgraded"][0]["name"] for e in history.load_history()]
        self.assertEqual(names, ["pkg2", "pkg3", "pkg4"])

    def test_corrupt_lines_are_skipped(self):
        history.record_run(make_result(), notified=False)
        with history.HISTORY_FILE.open("a") as f:
            f.write("not json\n")
        self.assertEqual(len(history.load_history()), 1)

    def test_show_newest_first_with_limit(self):
        for i, day in enumerate((1, 2, 3)):
            history.record_run(make_result(upgraded=[f"pkg{i}"]), notified=False, now=datetime(2026, 1, day))
        out = self._output(limit=2)
        self.assertLess(out.index("2026-01-03"), out.index("2026-01-02"))
        self.assertNotIn("2026-01-01", out)
        self.assertIn("showing 2 of 3", out)

    def test_filter_by_package(self):
        history.record_run(make_result(upgraded=["git"]), notified=False, now=datetime(2026, 1, 1))
        history.record_run(make_result(failed=["node"], has_problem=True), notified=False, now=datetime(2026, 1, 2))
        out = self._output(limit=10, package="node")
        self.assertIn("2026-01-02", out)
        self.assertIn("FAILED: node 1 -> 2", out)
        self.assertNotIn("2026-01-01", out)
        self.assertIn("No runs in history involving 'nope'", self._output(package="nope"))


if __name__ == "__main__":
    unittest.main()
