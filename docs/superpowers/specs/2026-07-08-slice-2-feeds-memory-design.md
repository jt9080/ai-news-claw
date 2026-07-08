# Slice 2 — Feeds & memory

**Date:** 2026-07-08
**Status:** Agreed
**Source of truth:** `prd.html` (§4 slices, §5 data model, §7 decisions — all revised
2026-07-08), `CLAUDE.md`, `feeds/github.md`

## Goal

Build the two things the LLM structurally **cannot do for itself**, plus a second feed:

1. **Cross-run memory** — remember what we've seen and reported, so tomorrow's digest
   doesn't re-report today's stories.
2. **Velocity** — today's signal minus the stored snapshot, so "rising fast" is
   computable at all (a feed API returns a total, never a delta).

Both collapse to one artifact: **`state.json`**, the agent's memory between runs. Plus
**`runs.json`**, the append-only health log. Selection stays a deliberately-dumb
stand-in; `python run.py` still produces a dashboard with **no LLM and no key**.

This slice is plumbing. It exists so the S3 LLM call is cheap and possible, not to make
good editorial decisions itself.

## The roadmap revision this slice sits in

Recorded in `prd.html` §4/§7 on 2026-07-08. The original PRD ranked mechanically and
added the LLM only to "refine". We reversed that: **the LLM makes every editorial call**
(clustering, relevance, selection, the one-line significance). Hard signals are now only
a cheap **pre-filter** to bound the LLM's input — never a ranker. Consequences for S2:

- **No mechanical clustering.** Deferred entirely to the S3 LLM. `state.json` therefore
  stores per-source **seen-records**, not canonical clustered `Item`s.
- **No tier/normalization ranking.** The stand-in selector is throwaway.

## Decisions carried in

Locked in the brainstorming pass for this slice:

- **Second feed: GitHub.** Best exercises both hard parts. Velocity: the Search API
  returns a snapshot star total, forcing real delta-from-state work. Clustering (later,
  in S3): an HN thread's URL is often the GitHub repo link — a clean join for the LLM.
- **Clustering: none in S2.** Deferred to the S3 LLM. State is keyed by
  `(source, source_id)`.
- **Resurface rule: 2× peak.** A reported item resurfaces when its current signal ≥
  `2 × peak_signal`. One tuning-knob constant.
- **Ranking: dumb stand-in.** Per-source top-by-raw-signal, capped at 8. Explicitly
  deleted in S3 when the LLM takes over selection.
- **Toolchain:** Python, **standard library only**, 3.9-compatible
  (`from __future__ import annotations`) despite the spec's 3.11+ target — the dev
  machine is 3.9.6. Carried over from S1.

## Deliberate deferrals

In scope for later slices, not this one:

- **Canonical `Item` + cross-source clustering** → S3 (the LLM does it).
- **The `why` one-liner and real relevance ranking** → S3 (the LLM).
- **HF / arXiv / Reddit / newsletter adapters** → later; the seam is proven with the
  second feed (GitHub), the rest slot in behind the same interface.
- **`pushed:`-based intake and watch-lists** for viral *old* repos → later. S2 uses a
  single `created:>DATE&sort=stars` query (new-repos-by-stars). A second intake path
  brings its own dedup concerns; YAGNI here.
- **Fixed UTC-day window and the scheduled run** → S4. S2 keeps S1's rolling-24h window.

## Architecture

Extends S1's convention: thin, mostly-pure modules orchestrated by an explicit pipeline
in `run.py`. New/changed modules under `newsclaw/`:

| Module | Role |
|---|---|
| `models.py` | Generalize `Candidate` to a source-agnostic `raw_signal {name, value}`. Add `SeenRecord` (persisted memory unit) and `Run`. Keep `FetchResult`. |
| `github.py` | **New** adapter. Same `fetch(start, end) → FetchResult` seam. Query `created:>DATE&sort=stars`; `raw_signal = ("stars", stargazers_count)`. Degrades to `status="failed"`, never raises. |
| `hackernews.py` | Light refactor onto the generalized candidate; `raw_signal = ("points", points)`. |
| `state.py` | **New.** `load_state(path)`, `save_state(path, state)` (atomic temp-file + rename), `append_run(path, run)`. |
| `ingest.py` | **New.** Upsert candidates into state: update `last_seen`, last value, `peak_signal`; compute `velocity`. |
| `rank.py` | Becomes the **stand-in selector**: suppression + per-source top-by-signal + cap 8 + stamp `reported_at`. Throwaway. |
| `relevance.py` | Unchanged. Now the cheap **pre-filter**, applied to both feeds. |
| `render.py` | Minor: source badge per card, `new`/`back` tag, per-feed health line for two feeds. |
| `window.py` | Unchanged (rolling 24h). |
| `run.py` | New pipeline (below). |

## Data flow (`run.py`)

```
window
  → [hackernews.fetch, github.fetch]        # each degrades independently
  → relevance.filter (both feeds)           # cheap pre-filter (allowlist)
  → state.load_state                        # missing/corrupt → start empty, flag it
  → ingest (upsert + compute velocity)      # updates last_seen / peak_signal / velocity
  → rank.select (suppression + top-8)       # stand-in; stamps reported_at on published
  → render_dashboard → write dashboard.html
  → state.save_state + state.append_run     # persist memory + trust log
```

## Data model (S2 subset)

`state.json` — a map keyed by `f"{source}:{source_id}"`:

```
SeenRecord {
  source        str          # "hackernews" | "github"
  source_id     str          # HN objectID | GitHub full_name
  title         str
  url           str
  signal_name   str          # "points" | "stars"
  signal_value  int          # latest observed
  peak_signal   int          # highest ever seen — for 2× resurface
  prior_value   int          # previous run's value — for velocity
  velocity      float        # signal_value - prior_value (see first-sight below)
  first_seen    str          # UTC ISO-8601
  last_seen     str
  reported_at   str | null   # set when published; drives suppression
}
```

`runs.json` — append-only list of `Run`:

```
Run {
  run_at   str
  window   { start, end }                              # UTC
  feeds    { hackernews: ok|failed, github: ok|failed } # per-feed health, always recorded
  counts   { candidates, kept, new, resurfaced, suppressed, published }
  state    ok | reset                                   # "reset" if state.json was missing/corrupt
}
```

**Velocity, first-sight rule:** on a record's first appearance there is no prior
snapshot, so `velocity = signal_value / max(age_days, 1)` (creation-to-now rate,
using `created_at` where the feed provides it, else the window length). On later runs,
`velocity = signal_value - prior_value`.

**Resurface / suppression:** a candidate whose `SeenRecord.reported_at` is set is
suppressed **unless** `signal_value ≥ 2 × peak_signal`, in which case it is eligible
again (and re-stamped when published).

## Error handling

- **Per-feed degradation.** Each adapter returns `FetchResult(status="failed")` on any
  error (network, HTTP, decode, malformed). One feed down never fails the run — the
  other still publishes, and the dead feed shows a banner. (S1 pattern, now for two.)
- **State resilience.** Missing or corrupt `state.json` → start from empty state and set
  `Run.state = "reset"` (never crash, never silently lose the log of the reset).
  `save_state` writes to a temp file and `os.replace`s it, so a crash mid-write cannot
  corrupt the memory.
- **`runs.json` is the trust artifact.** Appended every run, even a quiet or degraded
  one, so feed health is always recorded (per `CLAUDE.md`).

## Testing (TDD)

Every module gets `tests/test_*.py`; fixtures in `tests/fixtures/`.

- `test_github.py` — parse a GitHub search fixture into candidates; malformed items
  skipped; failure → degraded `FetchResult`.
- `test_models.py` — generalized `Candidate.raw_signal`; `SeenRecord`/`Run` shape.
- `test_state.py` — load/save round-trip; missing file → empty + `reset`; corrupt JSON →
  empty + `reset`; atomic save leaves no partial file; `append_run` appends.
- `test_ingest.py` — first-sight velocity (rate); subsequent-run velocity (delta);
  `peak_signal` tracks the max; `last_seen` updates.
- `test_rank.py` — suppression drops reported items; 2× peak resurfaces; per-source
  top-by-signal; cap at 8; `reported_at` stamped on published.
- `test_render.py` — source badges; new/back tags; two-feed health line; one feed failed
  → banner + other feed still rendered.
- `test_run.py` — integration: two feeds → state written → second run suppresses a
  repeat and resurfaces a 2× jumper.

## Success criteria

- `python run.py` produces `dashboard.html` **with no key**, pulling HN + GitHub.
- A second consecutive run suppresses items reported in the first, and resurfaces one
  whose signal has ≥ doubled past its peak.
- `state.json` and `runs.json` exist, round-trip, and survive a corrupt-file start.
- One feed failing degrades to a banner; the run still publishes.
- All `unittest` tests green on Python 3.9.
