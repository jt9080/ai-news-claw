"""arXiv adapter — the research tier.

Atom API over the shared feed parser, scoped to the agent-relevant categories
(cs.MA multiagent + cs.AI) and sorted newest-first. arXiv has no popularity
signal, so items carry ``recency`` = 0 and lean entirely on the judge (and
cross-referencing against Hugging Face daily papers) for importance.

Only first submissions are kept — a ``v2+`` id is a revision resurfacing older
work, not news. The canonical URL is the versionless https abstract, so a paper
here clusters with the same paper surfaced via Hugging Face daily papers.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.request import Request, urlopen

from newsclaw import feedparse
from newsclaw.models import Candidate, FetchResult

SOURCE = "arxiv"
QUERY_URL = (
    "https://export.arxiv.org/api/query"
    "?search_query=cat:cs.MA+OR+cat:cs.AI"
    "&sortBy=submittedDate&sortOrder=descending&max_results=25"
)
USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
TIMEOUT_SECONDS = 20

_VERSION = re.compile(r"v(\d+)$")


def to_candidates(entries: list, window_start: datetime, window_end: datetime) -> list:
    """First-submission arXiv entries within the window, as Candidates."""
    candidates = []
    for entry in entries:
        link = entry.get("link") or ""
        seg = link.rstrip("/").rsplit("/", 1)[-1]  # e.g. "2607.04567v1"
        if not seg:
            continue
        match = _VERSION.search(seg)
        if match and int(match.group(1)) > 1:
            continue  # a revision, not a first submission
        bare_id = _VERSION.sub("", seg)
        published = entry.get("published")
        if published is None or not (window_start <= published <= window_end):
            continue
        candidates.append(Candidate(
            source=SOURCE, source_id=bare_id, title=entry.get("title") or bare_id,
            url=f"https://arxiv.org/abs/{bare_id}",
            signal_name="recency", signal_value=0,
            created_at=published, summary=entry.get("summary") or None,
        ))
    return candidates


def fetch(window_start: datetime, window_end: datetime) -> FetchResult:
    """Fetch recent agent-relevant preprints. Never raises; degrades to failed."""
    request = Request(QUERY_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            entries = feedparse.parse(response.read())
        candidates = to_candidates(entries, window_start, window_end)
    except Exception as exc:  # network, HTTP 429, timeout — all degrade
        return FetchResult(source=SOURCE, status="failed", candidates=[], error=str(exc))
    return FetchResult(source=SOURCE, status="ok", candidates=candidates)
