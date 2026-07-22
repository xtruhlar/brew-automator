import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import config


class LoadConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original_config_file = config.CONFIG_FILE
        config.CONFIG_FILE = Path(self.tmpdir.name) / "config.env"
        self.addCleanup(self._restore)

    def _restore(self):
        config.CONFIG_FILE = self.original_config_file

    def _write(self, contents: str):
        config.CONFIG_FILE.write_text(contents)

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            config.load_config()

    def test_parses_all_required_keys(self):
        self._write(
            "SMTP_HOST=smtp.example.com\n"
            "SMTP_PORT=465\n"
            "SMTP_USER=me@example.com\n"
            "SMTP_PASSWORD=secret\n"
            "MAIL_TO=you@example.com\n"
        )
        cfg = config.load_config()
        self.assertEqual(cfg["SMTP_HOST"], "smtp.example.com")
        self.assertEqual(cfg["SMTP_PORT"], "465")
        self.assertEqual(cfg["MAIL_TO"], "you@example.com")

    def test_strips_quotes_and_whitespace(self):
        self._write(
            'SMTP_HOST = "smtp.example.com"\n'
            "SMTP_PORT=465\n"
            "SMTP_USER=me@example.com\n"
            "SMTP_PASSWORD='secret'\n"
            "MAIL_TO=you@example.com\n"
        )
        cfg = config.load_config()
        self.assertEqual(cfg["SMTP_HOST"], "smtp.example.com")
        self.assertEqual(cfg["SMTP_PASSWORD"], "secret")

    def test_ignores_comments_and_blank_lines(self):
        self._write(
            "# comment\n"
            "\n"
            "SMTP_HOST=smtp.example.com\n"
            "SMTP_PORT=465\n"
            "SMTP_USER=me@example.com\n"
            "SMTP_PASSWORD=secret\n"
            "MAIL_TO=you@example.com\n"
        )
        cfg = config.load_config()
        self.assertEqual(cfg["SMTP_HOST"], "smtp.example.com")

    def test_missing_required_key_raises_value_error(self):
        self._write("SMTP_HOST=smtp.example.com\n")
        with self.assertRaises(ValueError):
            config.load_config()


if __name__ == "__main__":
    unittest.main()
