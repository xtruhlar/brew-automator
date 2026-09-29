import json
import sys
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew_automator import webhook


def build(kind, url="https://example.com/hook", summary="Status: OK", has_problem=False):
    return webhook.build_request(url, kind, "🍺 Homebrew OK - 2026-01-01", summary, "full report", has_problem)


class BuildRequestTests(unittest.TestCase):
    def test_ntfy_posts_plain_text_with_title_in_query(self):
        req = build("ntfy", url="https://ntfy.sh/topic", has_problem=True)
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.data.decode(), "Status: OK")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
        self.assertEqual(query["title"], ["🍺 Homebrew OK - 2026-01-01"])
        self.assertEqual(query["tags"], ["warning"])
        self.assertEqual(query["priority"], ["high"])

    def test_ntfy_keeps_existing_query_string(self):
        req = build("ntfy", url="https://ntfy.example.com/topic?auth=abc")
        self.assertTrue(req.full_url.startswith("https://ntfy.example.com/topic?auth=abc&title="))

    def test_slack_payload(self):
        payload = json.loads(build("slack").data)
        self.assertIn("*🍺 Homebrew OK - 2026-01-01*", payload["text"])
        self.assertIn("Status: OK", payload["text"])

    def test_discord_payload_is_truncated(self):
        payload = json.loads(build("discord", summary="x" * 5000).data)
        self.assertLessEqual(len(payload["content"]), 2000)

    def test_generic_json_payload_includes_report(self):
        payload = json.loads(build("json", has_problem=True).data)
        self.assertEqual(payload["status"], "problem")
        self.assertEqual(payload["summary"], "Status: OK")
        self.assertEqual(payload["report"], "full report")


if __name__ == "__main__":
    unittest.main()
