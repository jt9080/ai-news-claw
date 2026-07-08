"""Hugging Face adapter — trending models + curated daily papers.

Two JSON endpoints, both free and auth-free. Trending models carry a ``likes``
signal; daily papers carry an ``upvotes`` signal and an arXiv id, so a paper's
canonical URL is its arXiv abstract — which lets the judge cluster it with the
raw arXiv feed. The two sub-fetches fail independently: if one endpoint is down
the other still contributes, and only a total failure degrades the feed.
"""

from __future__ import annotations

import json
from datetime import datetime
from urllib.request import Request, urlopen

from newsclaw.models import Candidate, FetchResult

SOURCE = "huggingface"
MODELS_URL = "https://huggingface.co/api/models?sort=trendingScore&limit=20"
PAPERS_URL = "https://huggingface.co/api/daily_papers?limit=20"
USER_AGENT = "ai-news-monitor/0.1 (+https://github.com/jt9080/ai-news-claw)"
TIMEOUT_SECONDS = 15


def parse_models(items: list, now: datetime) -> list:
    candidates = []
    for item in items:
        try:
            model_id = str(item["id"])
            candidates.append(Candidate(
                source=SOURCE, source_id=f"model:{model_id}", title=model_id,
                url=f"https://huggingface.co/{model_id}",
                signal_name="likes", signal_value=int(item.get("likes", 0)),
                created_at=now, summary=model_id,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return candidates


def parse_papers(items: list, now: datetime) -> list:
    candidates = []
    for item in items:
        try:
            paper = item["paper"]
            paper_id = str(paper["id"])
            candidates.append(Candidate(
                source=SOURCE, source_id=f"paper:{paper_id}",
                title=paper["title"],
                url=f"https://arxiv.org/abs/{paper_id}",
                signal_name="upvotes", signal_value=int(paper.get("upvotes", 0)),
                created_at=now, summary=paper.get("summary") or None,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return candidates


def _get_json(url: str) -> list:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch(window_start: datetime, window_end: datetime) -> FetchResult:
    """Fetch trending models + daily papers. Degrades to failed only if BOTH
    endpoints fail; a single dead endpoint still returns the other's items."""
    candidates = []
    errors = []
    for url, parse in ((MODELS_URL, parse_models), (PAPERS_URL, parse_papers)):
        try:
            candidates.extend(parse(_get_json(url), window_end))
        except Exception as exc:  # noqa: BLE001 - one endpoint down is not fatal
            errors.append(str(exc))
    if len(errors) == 2:
        return FetchResult(source=SOURCE, status="failed", candidates=[],
                           error="; ".join(errors))
    return FetchResult(source=SOURCE, status="ok", candidates=candidates)
