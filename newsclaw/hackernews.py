"""Hacker News adapter.

Fetches stories above the points threshold in the window via the Algolia
``search_by_date`` API and parses them into ``Candidate`` objects. Any failure
(network, non-200, malformed JSON, timeout) is caught and returned as a degraded
``FetchResult`` so the run completes and the dashboard shows a banner instead of
crashing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

from newsclaw.models import Candidate, FetchResult

SOURCE = "hackernews"

# Only stories above this many points are fetched. A configurable tuning knob.
POINTS_THRESHOLD = 100

# Politeness + some APIs reject a missing UA.
USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
TIMEOUT_SECONDS = 15

_HN_ITEM = "https://news.ycombinator.com/item?id="


def _build_url(window_start: datetime) -> str:
    start_unix = int(window_start.timestamp())
    numeric = f"points>{POINTS_THRESHOLD},created_at_i>{start_unix}"
    return (
        "https://hn.algolia.com/api/v1/search_by_date"
        "?tags=story"
        f"&numericFilters={quote(numeric)}"
        "&hitsPerPage=200"
    )


def parse_hits(hits: list[dict]) -> list[Candidate]:
    """Parse raw Algolia hits into Candidates. Malformed hits are skipped."""
    candidates = []
    for hit in hits:
        try:
            object_id = str(hit["objectID"])
            hn_url = f"{_HN_ITEM}{object_id}"
            url = hit.get("url") or hn_url
            candidate = Candidate(
                source=SOURCE,
                source_id=object_id,
                title=hit["title"],
                url=url,
                hn_url=hn_url,
                points=int(hit["points"]),
                num_comments=int(hit.get("num_comments", 0)),
                created_at=datetime.fromtimestamp(
                    hit["created_at_i"], tz=timezone.utc
                ),
            )
        except (KeyError, TypeError, ValueError):
            # A hit missing required fields is skipped, not fatal.
            continue
        candidates.append(candidate)
    return candidates


def fetch(window_start: datetime, window_end: datetime) -> FetchResult:
    """Fetch HN stories in the window. Never raises; degrades to status=failed."""
    url = _build_url(window_start)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        candidates = parse_hits(payload.get("hits", []))
    except Exception as exc:  # network, HTTP, decode, JSON — all degrade
        return FetchResult(source=SOURCE, status="failed", candidates=[], error=str(exc))
    return FetchResult(source=SOURCE, status="ok", candidates=candidates)
