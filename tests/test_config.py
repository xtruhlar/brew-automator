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

    def test_webhook_only_config_is_valid(self):
        self._write("WEBHOOK_URL=https://ntfy.sh/my-topic\n")
        cfg = config.load_config()
        self.assertTrue(config.webhook_enabled(cfg))
        self.assertFalse(config.smtp_enabled(cfg))
        self.assertEqual(cfg["WEBHOOK_TYPE"], "ntfy")

    def test_smtp_and_webhook_together(self):
        self._write(
            "SMTP_HOST=smtp.example.com\n"
            "SMTP_PORT=465\n"
            "SMTP_USER=me@example.com\n"
            "SMTP_PASSWORD=secret\n"
            "MAIL_TO=you@example.com\n"
            "WEBHOOK_URL=https://example.com/hook\n"
            "WEBHOOK_TYPE=slack\n"
        )
        cfg = config.load_config()
        self.assertTrue(config.smtp_enabled(cfg))
        self.assertEqual(cfg["WEBHOOK_TYPE"], "slack")

    def test_partial_smtp_with_webhook_raises(self):
        self._write("SMTP_HOST=smtp.example.com\nWEBHOOK_URL=https://ntfy.sh/t\n")
        with self.assertRaises(ValueError):
            config.load_config()

    def test_unknown_webhook_type_raises(self):
        self._write("WEBHOOK_URL=https://example.com/hook\nWEBHOOK_TYPE=teams\n")
        with self.assertRaises(ValueError):
            config.load_config()

    def test_infer_webhook_type(self):
        self.assertEqual(config.infer_webhook_type("https://hooks.slack.com/services/x"), "slack")
        self.assertEqual(config.infer_webhook_type("https://discord.com/api/webhooks/1/x"), "discord")
        self.assertEqual(config.infer_webhook_type("https://ntfy.sh/topic"), "ntfy")
        self.assertEqual(config.infer_webhook_type("https://example.com/hook"), "json")


if __name__ == "__main__":
    unittest.main()
