import argparse
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import cli, config, history, mailer, maintenance, state, webhook

SMTP_CONFIG = {
    "SMTP_HOST": "h", "SMTP_PORT": "465", "SMTP_USER": "u", "SMTP_PASSWORD": "p", "MAIL_TO": "t",
}
WEBHOOK_CONFIG = {"WEBHOOK_URL": "https://ntfy.sh/t", "WEBHOOK_TYPE": "ntfy"}


def fake_result(mode, has_problem=False):
    return {
        "mode": mode,
        "report": "REPORT",
        "summary": "SUMMARY",
        "short_summary": "short",
        "has_problem": has_problem,
        "doctor_ok": not has_problem,
        "doctor_output": "doctor says no" if has_problem else "",
        "missing_output": "",
        "upgraded": [],
        "failed": [],
        "skipped": [],
        "freed": "",
        "duration_s": 1.0,
    }


class CmdRunTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        tmp = Path(self.tmpdir.name)

        patches = {
            (state, "STATE_FILE"): tmp / "state.json",
            (history, "HISTORY_FILE"): tmp / "history.jsonl",
            (maintenance, "LOG_DIR"): tmp / "logs",
            (maintenance, "LOG_FILE"): tmp / "logs" / "log",
            (maintenance, "notify_local"): lambda summary: self.local.append(summary),
            (maintenance, "run_maintenance"): lambda mode: fake_result(mode, self.has_problem),
            (config, "config_exists"): lambda: self.cfg is not None,
            (config, "load_config"): lambda: self.cfg,
            (mailer, "send_report"): self._fake_email,
            (webhook, "send"): self._fake_webhook,
        }
        for (module, name), value in patches.items():
            original = getattr(module, name)
            setattr(module, name, value)
            self.addCleanup(setattr, module, name, original)

        self.cfg = None
        self.has_problem = False
        self.email_error = None
        self.emails, self.webhooks, self.local = [], [], []

    def _fake_email(self, cfg, subject, body):
        if self.email_error:
            raise self.email_error
        self.emails.append(subject)

    def _fake_webhook(self, cfg, title, summary, report, has_problem):
        self.webhooks.append((title, summary))

    def _run(self, dry_run=False, no_upgrade=False):
        args = argparse.Namespace(dry_run=dry_run, no_upgrade=no_upgrade)
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with redirect_stdout(out), redirect_stderr(err):
            try:
                cli.cmd_run(args)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_sends_to_both_channels_and_records_history(self):
        self.cfg = {**SMTP_CONFIG, **WEBHOOK_CONFIG}
        code, out, _ = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(len(self.emails), 1)
        self.assertTrue(self.emails[0].startswith("🍺 Homebrew OK"))
        self.assertEqual(self.webhooks[0][1], "SUMMARY")
        self.assertEqual(self.local, ["short"])
        self.assertTrue(history.last_run()["notified"])
        self.assertIn("REPORT", out)

    def test_webhook_only(self):
        self.cfg = dict(WEBHOOK_CONFIG)
        self._run()
        self.assertEqual(self.emails, [])
        self.assertEqual(len(self.webhooks), 1)

    def test_no_config_is_local_only(self):
        code, _, _ = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(self.emails + self.webhooks, [])
        self.assertFalse(history.last_run()["notified"])

    def test_unchanged_warning_is_deduplicated(self):
        self.cfg = {**SMTP_CONFIG, **WEBHOOK_CONFIG}
        self.has_problem = True
        self._run()
        self._run()
        self.assertEqual(len(self.emails), 1)
        self.assertEqual(len(self.webhooks), 1)
        self.assertTrue(self.emails[0].startswith("⚠️ Homebrew Warning"))
        self.assertEqual(len(history.load_history()), 2)

    def test_dry_run_sends_and_records_nothing(self):
        self.cfg = {**SMTP_CONFIG, **WEBHOOK_CONFIG}
        code, out, _ = self._run(dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.emails + self.webhooks + self.local, [])
        self.assertEqual(history.load_history(), [])
        self.assertFalse(state.STATE_FILE.exists())
        self.assertIn("REPORT", out)

    def test_no_upgrade_marks_subject(self):
        self.cfg = dict(SMTP_CONFIG)
        self._run(no_upgrade=True)
        self.assertTrue(self.emails[0].endswith("(report only)"))
        self.assertEqual(history.last_run()["mode"], "no-upgrade")

    def test_failed_send_exits_nonzero_but_still_records_and_notifies(self):
        self.cfg = {**SMTP_CONFIG, **WEBHOOK_CONFIG}
        self.email_error = RuntimeError("smtp down")
        code, _, err = self._run()
        self.assertEqual(code, 1)
        self.assertIn("Failed to send email: smtp down", err)
        self.assertEqual(len(self.webhooks), 1)
        self.assertEqual(self.local, ["short"])
        self.assertEqual(len(history.load_history()), 1)
        # State isn't saved, so a warning would be retried next run.
        self.assertFalse(state.STATE_FILE.exists())


if __name__ == "__main__":
    unittest.main()
