"""AI News Monitor — Slice 1 entry point.

Run with `python run.py`. Computes the window, fetches Hacker News via the
adapter, filters for relevance, ranks by points, renders dashboard.html, and
prints a one-line summary of the funnel and feed health.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from newsclaw import hackernews, rank, relevance
from newsclaw.render import render_dashboard
from newsclaw.window import compute_window

DEFAULT_OUTPUT = Path(__file__).parent / "dashboard.html"


def main(now: datetime | None = None, output_path: Path = DEFAULT_OUTPUT) -> str:
    if now is None:
        now = datetime.now(timezone.utc)

    start, end = compute_window(now)
    feed = hackernews.fetch(start, end)

    relevant = relevance.filter_relevant(feed.candidates)
    items = rank.rank(relevant)

    html = render_dashboard(items, (start, end), feed, now)
    output_path.write_text(html, encoding="utf-8")

    summary = (
        f"window={start.isoformat()}..{end.isoformat()} "
        f"feed={feed.status} "
        f"fetched={len(feed.candidates)} "
        f"kept={len(relevant)} "
        f"published={len(items)} "
        f"-> {output_path}"
    )
    return summary


if __name__ == "__main__":
    print(main())
