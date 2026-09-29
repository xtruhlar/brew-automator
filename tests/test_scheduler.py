import plistlib
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import scheduler

# 2026-01-07 is a Wednesday.
WEDNESDAY_NOON = datetime(2026, 1, 7, 12, 0)


class NextRunTests(unittest.TestCase):
    def test_no_entries(self):
        self.assertIsNone(scheduler.next_run([], WEDNESDAY_NOON))

    def test_later_same_day(self):
        # launchd weekday 3 = Wednesday
        self.assertEqual(scheduler.next_run([(3, 18, 30)], WEDNESDAY_NOON), datetime(2026, 1, 7, 18, 30))

    def test_earlier_same_day_rolls_to_next_week(self):
        self.assertEqual(scheduler.next_run([(3, 9, 0)], WEDNESDAY_NOON), datetime(2026, 1, 14, 9, 0))

    def test_sunday_is_zero(self):
        self.assertEqual(scheduler.next_run([(0, 8, 0)], WEDNESDAY_NOON), datetime(2026, 1, 11, 8, 0))

    def test_picks_earliest_of_several(self):
        entries = [(1, 8, 0), (5, 8, 0)]  # Monday, Friday
        self.assertEqual(scheduler.next_run(entries, WEDNESDAY_NOON), datetime(2026, 1, 9, 8, 0))


class ReadEntriesTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original = scheduler.PLIST_FILE
        scheduler.PLIST_FILE = Path(self.tmpdir.name) / "test.plist"
        self.addCleanup(lambda: setattr(scheduler, "PLIST_FILE", self.original))

    def test_missing_plist(self):
        self.assertEqual(scheduler.read_entries(), [])

    def test_roundtrip_with_generated_plist(self):
        entries = [(1, 9, 0), (4, 18, 45)]
        scheduler.PLIST_FILE.write_text(scheduler._build_plist(entries, "/usr/local/bin/brew-automator"))
        self.assertEqual(scheduler.read_entries(), entries)

    def test_single_dict_interval(self):
        scheduler.PLIST_FILE.write_bytes(
            plistlib.dumps({"StartCalendarInterval": {"Weekday": 7, "Hour": 6, "Minute": 5}})
        )
        self.assertEqual(scheduler.read_entries(), [(0, 6, 5)])

    def test_corrupt_plist(self):
        scheduler.PLIST_FILE.write_text("garbage")
        self.assertEqual(scheduler.read_entries(), [])


if __name__ == "__main__":
    unittest.main()
