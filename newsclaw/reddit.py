"""Reddit adapter — practitioner chatter via per-sub RSS (no auth).

The JSON API 403s without OAuth, so we use the auth-free ``top/.rss?t=day`` feed
for each subreddit. RSS gives no upvote/comment counts, so items carry ``top`` =
0 (their presence in "top of the day" is the only signal) and lean on the judge
to separate a real launch from people-talking. Subreddits are fetched
independently: one 429'd sub drops out, the rest still contribute; only a total
failure degrades the feed. A short delay spaces the same-host calls.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from urllib.request import Request, urlopen

from newsclaw import feedparse
from newsclaw.models import Candidate, FetchResult

SOURCE = "reddit"
SUBREDDITS = ["LocalLLaMA", "MachineLearning", "AI_Agents"]
USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
TIMEOUT_SECONDS = 20
DELAY_SECONDS = 2  # politeness between same-host calls (Reddit is 429-sensitive)

_COMMENT_ID = re.compile(r"/comments/([^/]+)")


def _url(sub: str) -> str:
    return f"https://www.reddit.com/r/{sub}/top/.rss?t=day"


def to_candidates(entries: list, window_start: datetime, window_end: datetime) -> list:
    candidates = []
    for entry in entries:
        link = entry.get("link") or ""
        match = _COMMENT_ID.search(link)
        if not match:
            continue
        published = entry.get("published")
        if published is not None and not (window_start <= published <= window_end):
            continue
        candidates.append(Candidate(
            source=SOURCE, source_id=match.group(1),
            title=entry.get("title") or "(untitled)", url=link,
            signal_name="top", signal_value=0,
            created_at=published or window_end,
            discussion_url=link, summary=entry.get("summary") or None,
        ))
    return candidates


def fetch(window_start: datetime, window_end: datetime) -> FetchResult:
    """Fetch top/day across the subreddits. Degrades only if ALL subs fail."""
    candidates = []
    errors = []
    for i, sub in enumerate(SUBREDDITS):
        if i:
            time.sleep(DELAY_SECONDS)
        request = Request(_url(sub), headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                entries = feedparse.parse(response.read())
            candidates.extend(to_candidates(entries, window_start, window_end))
        except Exception as exc:  # noqa: BLE001 - one sub down is not fatal
            errors.append(f"{sub}: {exc}")
    if len(errors) == len(SUBREDDITS):
        return FetchResult(source=SOURCE, status="failed", candidates=[],
                           error="; ".join(errors))
    return FetchResult(source=SOURCE, status="ok", candidates=candidates)
