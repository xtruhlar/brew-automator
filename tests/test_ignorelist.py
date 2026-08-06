import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import ignorelist


class IgnoreListTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original_ignore_file = ignorelist.IGNORE_FILE
        ignorelist.IGNORE_FILE = Path(self.tmpdir.name) / "ignored.json"
        self.addCleanup(self._restore)

    def _restore(self):
        ignorelist.IGNORE_FILE = self.original_ignore_file

    def test_load_missing_file_returns_empty_lists(self):
        self.assertEqual(ignorelist.load_ignored(), {"formulae": [], "casks": []})

    def test_save_then_load_roundtrip(self):
        ignorelist.save_ignored({"formulae": ["git", "node"], "casks": ["firefox"]})
        self.assertEqual(
            ignorelist.load_ignored(), {"formulae": ["git", "node"], "casks": ["firefox"]}
        )

    def test_load_corrupt_file_returns_empty_lists(self):
        ignorelist.IGNORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ignorelist.IGNORE_FILE.write_text("not valid json {{{")
        self.assertEqual(ignorelist.load_ignored(), {"formulae": [], "casks": []})

    def test_load_missing_keys_defaults_to_empty(self):
        ignorelist.IGNORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ignorelist.IGNORE_FILE.write_text('{"formulae": ["git"]}')
        self.assertEqual(ignorelist.load_ignored(), {"formulae": ["git"], "casks": []})


if __name__ == "__main__":
    unittest.main()
