"""Slice 2 data model.

The ``Candidate`` is the per-run object a feed adapter emits; it carries a
source-agnostic ``raw_signal`` (``signal_name`` + ``signal_value``) so Hacker
News points and GitHub stars flow through the same pipeline. Run-derived
annotations (``velocity``, ``is_new``, ``resurfaced``) are filled in by
``ingest`` against the persisted memory.

``SeenRecord`` is the persisted memory unit — one per ``(source, source_id)``,
stored in ``state.json``. ``Run`` is one entry in the append-only ``runs.json``
health log. Cross-source clustering into a canonical ``Item`` is deferred to the
S3 LLM, so state holds seen-records, not clustered items.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Candidate:
    source: str            # "hackernews" | "github"
    source_id: str         # HN objectID | GitHub full_name
    title: str
    url: str               # canonical link (story url / repo html_url)
    signal_name: str       # "points" | "stars"
    signal_value: int
    created_at: datetime   # UTC, timezone-aware
    discussion_url: Optional[str] = None   # hn item url; None for GitHub
    num_comments: Optional[int] = None     # HN secondary signal; None for GitHub
    summary: Optional[str] = None          # repo description; extra relevance haystack
    topics: list = field(default_factory=list)  # matched allowlist terms
    # Run-derived annotations, set by ingest against prior memory:
    velocity: float = 0.0  # signal delta since last run (rate on first sight)
    is_new: bool = True     # not seen in any prior run
    resurfaced: bool = False  # was reported, then jumped >= 2x prior peak


@dataclass
class FetchResult:
    source: str            # "hackernews" | "github"
    status: str            # "ok" | "failed"
    candidates: list = field(default_factory=list)
    error: Optional[str] = None  # populated when status == "failed"


@dataclass
class SeenRecord:
    """One remembered story, keyed by (source, source_id) in state.json."""

    source: str
    source_id: str
    title: str
    url: str
    signal_name: str
    signal_value: int      # latest observed
    peak_signal: int       # highest ever seen — for jump detection
    prior_value: int       # previous run's value — the velocity basis
    velocity: float
    first_seen: str        # UTC ISO-8601
    last_seen: str
    reported_at: Optional[str] = None  # set when published; drives suppression

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SeenRecord":
        return cls(**d)


@dataclass
class DigestItem:
    """One rendered story in the digest.

    The judge produces these (clustering one or more candidates and adding the
    ``why``/``kind``); the stand-in fallback wraps each published candidate into
    one via ``from_candidate`` so ``render`` consumes a single uniform shape.
    """

    title: str
    url: str
    what: str           # one sentence: what the news is; "" on the fallback path
    why: str            # one sentence: why it matters; "" on the fallback path
    for_builders: str   # one sentence: takeaway for agent builders; may be ""
    kind: str           # model|repo|paper|tool|post|discussion
    topics: list
    resurfaced: bool
    is_new: bool
    sources: list       # the clustered Candidates (for signal/age/links)

    @classmethod
    def from_candidate(cls, c) -> "DigestItem":
        kind = "repo" if c.source == "github" else "post"
        return cls(
            title=c.title, url=c.url, what="", why="", for_builders="", kind=kind,
            topics=list(c.topics), resurfaced=c.resurfaced,
            is_new=c.is_new, sources=[c],
        )


@dataclass
class Assignment:
    """The judge's one 'if you have an hour today' pick, shown as a rail card.

    ``title``/``url`` come from the referenced candidate (grounded, never
    model-invented); ``text`` is the judge's instruction to the reader."""

    title: str
    url: str
    text: str


@dataclass
class Run:
    """One entry in the append-only runs.json health log — the trust artefact."""

    run_at: str
    window: dict           # {"start": iso, "end": iso}
    feeds: dict            # {"hackernews": "ok"|"failed", "github": ...}
    counts: dict           # {candidates, kept, new, resurfaced, suppressed, published}
    state: str             # "ok" | "reset"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Run":
        return cls(**d)
