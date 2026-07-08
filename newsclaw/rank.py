"""Mechanical ranking: threshold, sort by points, cap.

Slice 1 ranks on points alone — no controversy adjustment, no velocity.
"""

from __future__ import annotations

from newsclaw.hackernews import POINTS_THRESHOLD
from newsclaw.models import Candidate

MAX_ITEMS = 8


def rank(candidates: list[Candidate]) -> list[Candidate]:
    """Keep candidates above the points threshold, sort by points desc, cap at 8.

    The threshold is already enforced by the fetch query; it is re-checked here
    defensively so ranking is correct regardless of how candidates were sourced.
    """
    eligible = [c for c in candidates if c.points > POINTS_THRESHOLD]
    eligible.sort(key=lambda c: c.points, reverse=True)
    return eligible[:MAX_ITEMS]
