"""Compute the digest's time window.

The PRD's fixed UTC-day boundary (adopted in Slice 4 for the unattended run):
the window is the calendar day that just ended, ``[previous 00:00, current
00:00]`` in UTC. At the 00:00-UTC schedule (= 08:00 Asia/Singapore) this reports
yesterday's news. This supersedes Slice 1's rolling-24h window, which existed
only as a manual-daytime-run convenience.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

WINDOW_HOURS = 24


def compute_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return (start, end) of the previous complete UTC day as timezone-aware
    UTC datetimes. ``end`` is the start of the current UTC day (``now`` floored
    to 00:00:00); ``start`` is 24h earlier."""
    if now is None:
        now = datetime.now(timezone.utc)
    end = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=WINDOW_HOURS)
    return start, end
