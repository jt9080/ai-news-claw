"""AI News Monitor — Slice 2 entry point.

Run with `python run.py`. Computes the window, fetches Hacker News and GitHub
behind their adapters, filters for relevance, folds this run's candidates into
the persisted memory (state.json) while computing velocity, selects a digest
with the stand-in selector, renders dashboard.html, appends a health record to
runs.json, and prints a one-line summary of the funnel.

No LLM and no key: the selection is a deliberately-dumb stand-in that Slice 3
replaces with the LLM judge. This slice exists to build and verify the memory +
velocity plumbing the judge will consume.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from newsclaw import github, hackernews, ingest, rank, relevance, state
from newsclaw.models import Run
from newsclaw.render import render_dashboard
from newsclaw.window import compute_window

_ROOT = Path(__file__).parent
DEFAULT_OUTPUT = _ROOT / "dashboard.html"
DEFAULT_STATE = _ROOT / "state.json"
DEFAULT_RUNS = _ROOT / "runs.json"


def main(
    now: datetime = None,
    output_path: Path = DEFAULT_OUTPUT,
    state_path: Path = DEFAULT_STATE,
    runs_path: Path = DEFAULT_RUNS,
) -> str:
    if now is None:
        now = datetime.now(timezone.utc)

    start, end = compute_window(now)

    feeds = [hackernews.fetch(start, end), github.fetch(start, end)]
    candidates = [c for feed in feeds for c in feed.candidates]

    relevant = relevance.filter_relevant(candidates)

    records, state_status = state.load_state(state_path)
    ingest.ingest(relevant, records, now)

    # Count truly-suppressed repeats before the selector stamps reported_at.
    suppressed = sum(
        1 for c in relevant
        if _reported_before(c, records) and not c.resurfaced
    )
    published = rank.select(relevant, records, now)

    html = render_dashboard(published, (start, end), feeds, now)
    output_path.write_text(html, encoding="utf-8")

    state.save_state(state_path, records)

    counts = {
        "candidates": len(candidates),
        "kept": len(relevant),
        "new": sum(1 for c in relevant if c.is_new),
        "resurfaced": sum(1 for c in relevant if c.resurfaced),
        "suppressed": suppressed,
        "published": len(published),
    }
    feed_health = {feed.source: feed.status for feed in feeds}
    state.append_run(runs_path, Run(
        run_at=now.isoformat(),
        window={"start": start.isoformat(), "end": end.isoformat()},
        feeds=feed_health,
        counts=counts,
        state=state_status,
    ))

    health_str = " ".join(f"{src}={st}" for src, st in feed_health.items())
    return (
        f"window={start.isoformat()}..{end.isoformat()} "
        f"{health_str} state={state_status} "
        f"candidates={counts['candidates']} kept={counts['kept']} "
        f"new={counts['new']} resurfaced={counts['resurfaced']} "
        f"suppressed={counts['suppressed']} published={counts['published']} "
        f"-> {output_path}"
    )


def _reported_before(candidate, records) -> bool:
    rec = records.get(f"{candidate.source}:{candidate.source_id}")
    return rec is not None and rec.reported_at is not None


if __name__ == "__main__":
    print(main())
