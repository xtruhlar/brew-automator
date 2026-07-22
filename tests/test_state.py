import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import state


class WarningSignatureTests(unittest.TestCase):
    def test_same_content_same_signature(self):
        sig1 = state.warning_signature("doctor output", "missing output")
        sig2 = state.warning_signature("doctor output", "missing output")
        self.assertEqual(sig1, sig2)

    def test_different_content_different_signature(self):
        sig1 = state.warning_signature("doctor output A", "")
        sig2 = state.warning_signature("doctor output B", "")
        self.assertNotEqual(sig1, sig2)

    def test_signature_is_stable_hex_digest(self):
        sig = state.warning_signature("x", "y")
        self.assertEqual(len(sig), 64)
        int(sig, 16)  # raises if not valid hex


class LoadSaveStateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original_state_file = state.STATE_FILE
        state.STATE_FILE = Path(self.tmpdir.name) / "state.json"
        self.addCleanup(self._restore)

    def _restore(self):
        state.STATE_FILE = self.original_state_file

    def test_load_missing_file_returns_empty_dict(self):
        self.assertEqual(state.load_state(), {})

    def test_save_then_load_roundtrip(self):
        state.save_state({"last_warning_key": "abc123", "last_run": "2026-01-01"})
        self.assertEqual(
            state.load_state(), {"last_warning_key": "abc123", "last_run": "2026-01-01"}
        )

    def test_load_corrupt_file_returns_empty_dict(self):
        state.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state.STATE_FILE.write_text("not valid json {{{")
        self.assertEqual(state.load_state(), {})


if __name__ == "__main__":
    unittest.main()
