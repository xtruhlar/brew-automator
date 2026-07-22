import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import maintenance


class IconFileTests(unittest.TestCase):
    def test_icon_file_exists(self):
        self.assertTrue(maintenance.ICON_FILE.exists())

    def test_icon_file_is_png(self):
        with maintenance.ICON_FILE.open("rb") as f:
            header = f.read(8)
        self.assertEqual(header, b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
