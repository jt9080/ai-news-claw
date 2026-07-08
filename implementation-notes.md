# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

### Slice 1 — HN → dashboard (2026-07-08)
Built `fetch → filter → rank → render` for one feed (Hacker News), no state/LLM.
Modules under `newsclaw/`: `window`, `models`, `hackernews`, `relevance`, `rank`,
`render`; entry `run.py`; 38 unittest tests. Design spec:
`docs/superpowers/specs/2026-07-08-slice-1-hn-dashboard-design.md`.

### Slice 2 — Feeds & memory (2026-07-08)
Added a second feed (GitHub) + persistent memory, keyless (no LLM). New modules:
`github` (adapter), `state` (state.json + runs.json, atomic writes), `ingest`
(velocity + resurface annotations). `models` generalized to a source-agnostic
`raw_signal` (+ `SeenRecord`, `Run`); `rank` became a dumb stand-in selector
(round-robin interleave + 2×-peak suppression); `render`/`relevance` extended for
two feeds. 71 unittest tests green on 3.9.6. Live: 65 fetched → 30 kept → 8
published; a second run suppressed all 8 repeats. Design spec:
`docs/superpowers/specs/2026-07-08-slice-2-feeds-memory-design.md`. Roadmap
revised in `prd.html` §4/§7 (LLM decides everything; signals are a pre-filter).

## Open questions

- **Points threshold (`>100`) and the keyword allowlist** are tuning knobs, not
  settled values. First live run: 34 fetched → 2 published. Revisit after more runs.

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

- **Health rendered inline, not persisted.** The PRD keeps S1 stateless; `CLAUDE.md`
  requires per-feed health always be recorded. Reconciled by rendering health into
  the dashboard (status line + failure banner). Persisted `runs.json` arrives in S2.
- **Rolling last-24h window** instead of the PRD's fixed "previous 00:00 → current
  00:00 UTC" boundary. For a manual daytime run the fixed boundary would exclude
  everything posted today. The fixed boundary is correct for the 08:00-SGT scheduled
  run and is adopted in S3.
- **Signal-only cards, no `why`-it-matters.** The PRD marks the one-line significance
  LLM-only (S3+). S1 cards show the signal (points · comments) and matched topics
  rather than a fabricated editorial claim.
- **Python 3.9-compatible** (`from __future__ import annotations` in every module),
  though the spec/CLAUDE.md say 3.11+. The dev machine runs 3.9.6, so tests must run
  there; the code is stdlib-only and runs identically on 3.11 (CI). No feature above
  3.9 is used.
- **Relevance uses word-boundary matching** (`\bTERM s?\b`) rather than plain
  substring, after a live run admitted "Why **skill**ed workers come to Germany" via
  the term `skill`. Colliding stems (`skill`, `fine-tun`) are spelled out. Still a
  knowingly-imperfect stopgap, superseded by the S3 judge.

### Slice 2
- **No canonical `Item` / cross-source clustering.** Deferred to the S3 LLM (per the
  revised roadmap). `state.json` therefore holds per-source `SeenRecord`s keyed by
  `source:source_id`, not clustered `Item`s as the PRD §5 data model shows.
- **`state.json` / `runs.json` gitignored, not committed.** PRD §5 says "in the repo";
  reconciled — they live in the repo directory and persist between local runs, but are
  gitignored to keep dev churn and machine timestamps out of the PR. Committing them
  back for scheduled-run persistence is an S4 decision.
- **`load_state`: missing file → `ok`, only corrupt → `reset`.** The spec said both
  reset; a missing file on first run isn't a reset (nothing was lost), so the trust log
  distinguishes them honestly.
- **Resurface tested against the *prior* peak** (captured before the record's peak
  absorbs today's value), so a jumper can't be masked by its own current value. Matches
  the intent of the "2× peak" knob.
- **`Candidate.summary`** added so GitHub repos match the keyword pre-filter on their
  description (repo names rarely contain "agent"/"llm").
- **Stand-in selector is deliberately dumb** (round-robin interleave, no cross-source
  normalization) and is deleted in S3 when the LLM owns selection.
