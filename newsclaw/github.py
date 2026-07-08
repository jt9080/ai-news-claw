"""GitHub adapter.

``github.com/trending`` has no API, so we use the Search API as a trending
proxy: repos created recently, sorted by stars. The star count is the signal;
its 24h *velocity* (computed against stored state in ``ingest``) is what really
matters. Any failure degrades to a ``FetchResult`` with ``status="failed"`` so
one flaky feed never crashes the run.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

from newsclaw.models import Candidate, FetchResult

SOURCE = "github"

# Free-text query covering agent-dev + general AI without burning the 60/hr
# unauth budget on many overlapping calls. A single query keeps S2 keyless.
QUERY_TERMS = "agent OR llm OR mcp OR agentic"

USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
TIMEOUT_SECONDS = 15


def _build_url(window_start: datetime) -> str:
    # Look back a little further than the window so a repo that crossed the star
    # bar mid-window is still discoverable; ingest/velocity handle recency.
    created_after = (window_start - timedelta(days=30)).date().isoformat()
    q = f"{QUERY_TERMS} created:>{created_after}"
    return (
        "https://api.github.com/search/repositories"
        f"?q={quote(q)}"
        "&sort=stars&order=desc&per_page=30"
    )


def _parse_created_at(raw: str) -> datetime:
    # GitHub returns e.g. "2026-06-14T09:12:00Z"; normalise the trailing Z.
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_items(items: list) -> list:
    """Parse raw Search API items into Candidates. Malformed items are skipped."""
    candidates = []
    for item in items:
        try:
            full_name = str(item["full_name"])
            candidate = Candidate(
                source=SOURCE,
                source_id=full_name,
                title=full_name,
                url=item["html_url"],
                signal_name="stars",
                signal_value=int(item["stargazers_count"]),
                created_at=_parse_created_at(item["created_at"]),
                summary=item.get("description") or None,
            )
        except (KeyError, TypeError, ValueError):
            continue
        candidates.append(candidate)
    return candidates


def fetch(window_start: datetime, window_end: datetime) -> FetchResult:
    """Fetch trending repos. Never raises; degrades to status=failed."""
    url = _build_url(window_start)
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        candidates = parse_items(payload.get("items", []))
    except Exception as exc:  # network, HTTP, decode, JSON — all degrade
        return FetchResult(source=SOURCE, status="failed", candidates=[], error=str(exc))
    return FetchResult(source=SOURCE, status="ok", candidates=candidates)
