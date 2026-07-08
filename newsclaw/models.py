"""Slice 1 data model — a subset of the PRD ``Item``.

No clustering, velocity, or persistence fields; those belong to the canonical
``Item`` in Slice 2's state.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candidate:
    source: str          # "hackernews"
    source_id: str       # HN objectID
    title: str
    url: str             # story url; falls back to hn_url for text posts
    hn_url: str          # https://news.ycombinator.com/item?id=<objectID>
    points: int
    num_comments: int
    created_at: datetime  # UTC, timezone-aware
    topics: list[str] = field(default_factory=list)  # matched allowlist terms


@dataclass
class FetchResult:
    source: str          # "hackernews"
    status: str          # "ok" | "failed"
    candidates: list[Candidate] = field(default_factory=list)
    error: str | None = None  # populated when status == "failed"
