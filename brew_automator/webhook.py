"""Send the run summary to a webhook (ntfy, Slack, Discord or a generic JSON endpoint).

Uses only urllib from the standard library.
"""

import json
import urllib.parse
import urllib.request

TIMEOUT_S = 30

# Per-service message size limits (with some headroom).
_DISCORD_LIMIT = 1900
_NTFY_LIMIT = 3900
_SLACK_LIMIT = 3900


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_request(url: str, webhook_type: str, title: str, summary: str, report: str,
                  has_problem: bool) -> urllib.request.Request:
    """Build (but don't send) the HTTP request for the given webhook flavour."""
    if webhook_type == "ntfy":
        # Title/tags go in query params rather than headers: headers must be
        # latin-1, and titles contain emoji/non-ASCII package names.
        params = urllib.parse.urlencode(
            {
                "title": title,
                "tags": "warning" if has_problem else "beer",
                "priority": "high" if has_problem else "default",
            }
        )
        separator = "&" if "?" in url else "?"
        return urllib.request.Request(
            f"{url}{separator}{params}",
            data=_truncate(summary, _NTFY_LIMIT).encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            method="POST",
        )

    if webhook_type == "slack":
        payload = {"text": _truncate(f"*{title}*\n```\n{summary}\n```", _SLACK_LIMIT)}
    elif webhook_type == "discord":
        payload = {"content": _truncate(f"**{title}**\n```\n{summary}\n```", _DISCORD_LIMIT)}
    else:
        payload = {
            "title": title,
            "status": "problem" if has_problem else "ok",
            "summary": summary,
            "report": report,
        }

    return urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def send(config: dict, title: str, summary: str, report: str, has_problem: bool):
    """POST the notification; raises on network errors or non-2xx responses."""
    request = build_request(
        config["WEBHOOK_URL"], config["WEBHOOK_TYPE"], title, summary, report, has_problem
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"webhook returned HTTP {response.status}")
