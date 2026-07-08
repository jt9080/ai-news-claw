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

import os
from datetime import datetime, timezone
from pathlib import Path

from newsclaw import github, hackernews, ingest, judge, rank, relevance, state
from newsclaw.models import DigestItem, Run
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

    # The judge makes the editorial calls. If it is unavailable (no key, HTTP
    # error, unparseable output) we fall back to the signal-ranked stand-in so
    # the run still publishes.
    judge_failed = False
    if not relevant:
        items = []
        judge_status = "skipped"
    else:
        try:
            items = judge.judge(relevant, records, now)
            judge_status = "ok"
        except judge.JudgeUnavailable:
            judge_failed = True
            judge_status = "failed"
            items = [DigestItem.from_candidate(c) for c in rank.select(relevant, records, now)]

    # Stamp reported_at on every published member so tomorrow suppresses it.
    now_iso = now.isoformat()
    for item in items:
        for c in item.sources:
            rec = records.get(f"{c.source}:{c.source_id}")
            if rec is not None:
                rec.reported_at = now_iso

    html = render_dashboard(items, (start, end), feeds, now, judge_failed)
    output_path.write_text(html, encoding="utf-8")

    state.save_state(state_path, records)

    published_ids = {(c.source, c.source_id) for item in items for c in item.sources}
    counts = {
        "candidates": len(candidates),
        "kept": len(relevant),
        "new": sum(1 for c in relevant if c.is_new),
        "resurfaced": sum(1 for item in items if item.resurfaced),
        "suppressed": len(relevant) - len(published_ids),
        "published": len(items),
    }
    feed_health = {feed.source: feed.status for feed in feeds}
    feed_health["judge"] = judge_status
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


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file into the environment without
    overriding anything already set. Keeps the API key out of the shell — the
    process reads its own config. A missing file is a no-op."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


if __name__ == "__main__":
    _load_dotenv(_ROOT / ".env")
    print(main())
