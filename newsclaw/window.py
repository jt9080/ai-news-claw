"""Compute the digest's time window.

Slice 1 uses a rolling last-24h window ending at run time, computed in UTC.
See the S1 design spec for why this differs from the PRD's fixed UTC-day boundary.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

WINDOW_HOURS = 24


def compute_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return (start, end) of the rolling window as timezone-aware UTC datetimes.

    ``end`` is ``now`` (defaulting to the current UTC time); ``start`` is 24h earlier.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    start = now - timedelta(hours=WINDOW_HOURS)
    return start, now
