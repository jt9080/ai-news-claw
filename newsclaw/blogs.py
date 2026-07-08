"""Blogs & newsletters adapter.

Lab blogs are the authoritative source for official releases; newsletters
pre-digest the firehose. Both are pulled as plain RSS/Atom via the shared feed
parser. No numeric signal, so items carry ``editorial`` = 0 and lean on the
judge to pick launches out of hiring posts and recaps. Each source is fetched
independently — one dead feed drops out, the rest still contribute; only a total
failure degrades. (Anthropic has no native feed — a known gap, not listed here.)
"""

from __future__ import annotations

from datetime import datetime
from urllib.request import Request, urlopen

from newsclaw import feedparse
from newsclaw.models import Candidate, FetchResult

SOURCE = "blogs"

# (label, feed url) — from feeds/blogs-newsletters.md, verified 8 Jul 2026.
SOURCES = [
    ("OpenAI", "https://openai.com/blog/rss.xml"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("Simon Willison", "https://simonwillison.net/atom/everything/"),
    ("Latent Space", "https://www.latent.space/feed"),
    ("smol.ai", "https://news.smol.ai/rss.xml"),
    ("Product Hunt AI", "https://www.producthunt.com/feed?category=artificial-intelligence"),
]
USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
TIMEOUT_SECONDS = 20


def to_candidates(entries: list, window_start: datetime, window_end: datetime) -> list:
    candidates = []
    for entry in entries:
        link = entry.get("link") or ""
        if not link:
            continue
        published = entry.get("published")
        if published is not None and not (window_start <= published <= window_end):
            continue
        candidates.append(Candidate(
            source=SOURCE, source_id=link, title=entry.get("title") or "(untitled)",
            url=link, signal_name="editorial", signal_value=0,
            created_at=published or window_end, summary=entry.get("summary") or None,
        ))
    return candidates


def fetch(window_start: datetime, window_end: datetime) -> FetchResult:
    """Fetch all blog/newsletter feeds. Degrades only if every source fails."""
    candidates = []
    errors = []
    for label, url in SOURCES:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                entries = feedparse.parse(response.read())
            candidates.extend(to_candidates(entries, window_start, window_end))
        except Exception as exc:  # noqa: BLE001 - one feed down is not fatal
            errors.append(f"{label}: {exc}")
    if len(errors) == len(SOURCES):
        return FetchResult(source=SOURCE, status="failed", candidates=[],
                           error="; ".join(errors))
    return FetchResult(source=SOURCE, status="ok", candidates=candidates)
