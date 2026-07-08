"""Stand-in selector — deliberately dumb, deleted in Slice 3.

This is *not* the product's ranking. Its only job is to produce a plausible
dashboard with no LLM and no key, so the S2 plumbing (feeds + memory + velocity)
can be run and verified end-to-end. In S3 the LLM replaces this entirely and
owns clustering, relevance, selection, and the one-line significance.

What it does: drop already-reported stories (unless ``ingest`` flagged them
resurfaced on a 2x jump), then round-robin across sources by descending signal
so both feeds show, cap at ``MAX_ITEMS``, and stamp ``reported_at`` on whatever
is published so tomorrow's run suppresses it.
"""

from __future__ import annotations

from datetime import datetime

MAX_ITEMS = 8


def _key(candidate) -> str:
    return f"{candidate.source}:{candidate.source_id}"


def select(candidates: list, records: dict, now: datetime) -> list:
    """Return the stories to publish, and stamp reported_at on their records."""
    eligible = []
    for c in candidates:
        rec = records.get(_key(c))
        reported_before = rec is not None and rec.reported_at is not None
        if reported_before and not c.resurfaced:
            continue  # suppress: seen it, no material jump
        eligible.append(c)

    published = _interleave_by_source(eligible)[:MAX_ITEMS]

    now_iso = now.isoformat()
    for c in published:
        rec = records.get(_key(c))
        if rec is not None:
            rec.reported_at = now_iso
    return published


def _interleave_by_source(candidates: list) -> list:
    """Round-robin the per-source lists (each sorted by signal desc) so no one
    feed dominates. Source order follows first appearance for determinism."""
    groups: dict = {}
    for c in candidates:
        groups.setdefault(c.source, []).append(c)
    for group in groups.values():
        group.sort(key=lambda c: c.signal_value, reverse=True)

    ordered = []
    lists = list(groups.values())
    index = 0
    while any(index < len(group) for group in lists):
        for group in lists:
            if index < len(group):
                ordered.append(group[index])
        index += 1
    return ordered
