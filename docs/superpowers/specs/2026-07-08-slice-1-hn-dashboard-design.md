# Slice 1 — One feed to one page

**Date:** 2026-07-08
**Status:** Agreed
**Source of truth:** `prd.html` (§4 slices, §5 data model, §7 decisions), `CLAUDE.md`, `feeds/hackernews.md`

## Goal

Prove the digest's report shape and that a raw signal threshold produces something
readable. Fetch **one** feed — **Hacker News** — filter it down to AI stories, rank by
points, and render a scannable `dashboard.html`. Manual run. No state, no clustering, no
LLM.

This slice is intentionally the smallest end-to-end path: `fetch → filter → rank →
render`. It exists to lock the report shape and the adapter seam that Slice 2 extends,
not to be the finished product.

## Decisions carried in

Locked in the brainstorming pass for this slice:

- **Feed:** Hacker News. No auth, no token, no rate-limit dance; a single windowed query
  returns stories already carrying a clean mechanical signal (points), and it needs zero
  state — the right fit for a stateless proof-of-shape slice.
- **Toolchain:** Python 3.11+, **standard library only** (`urllib.request`, `json`,
  `html`, `datetime`, `zoneinfo`, `unittest`). No third-party dependencies, so the
  scheduled GitHub Actions run in a later slice needs no install step.
- **Relevance:** a small **keyword allowlist** filter, applied in code after the fetch —
  explicitly a stopgap until the S3 LLM judge does real relevance.

## Deliberate deferrals

These are in scope for later slices, not this one:

- **`why` it matters (one-line significance).** The PRD marks this LLM-only (S3+). A
  Slice 1 card therefore shows the *signal and matched topics*, never a mechanically
  fabricated editorial claim.
- **`runs.json` run/health log.** The PRD keeps S1 stateless, while `CLAUDE.md` requires
  per-feed health always be recorded. Reconciled by rendering health **into the dashboard
  itself** (a status line plus a failure banner). The persisted `runs.json` arrives in S2.
- **Comment/point controversy down-rank.** Noted in the PRD blindspot pass, but it is a
  mechanical-ranking refinement. S1 ranks on points alone.
- **Fixed UTC-day window boundary.** S1 uses a rolling last-24h window (see below); the
  PRD's "previous 00:00 → current 00:00 UTC" boundary is correct for the 08:00-SGT
  scheduled run and is adopted in S3.
- **State, clustering, velocity, multiple feeds** — all Slice 2+.

## Window and fetch

- **Window:** rolling **last 24 hours ending at run time**, computed in UTC via
  `datetime.now(timezone.utc)`. Rationale: for a manual daytime run, the PRD's fixed
  "previous 00:00 → current 00:00 UTC" boundary would exclude everything posted today.
  Timestamps are stored/compared in UTC and rendered in Asia/Singapore.
- **Endpoint:**
  `https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=points>{THRESHOLD},created_at_i>{window_start_unix}&hitsPerPage=200`
  No `query=` term — relevance filtering happens in code for finer control.
- **HTTP:** `urllib.request` with an explicit timeout and a `User-Agent` header. Any
  failure (network error, non-200 status, malformed JSON, timeout) is caught and returned
  as a degraded `FetchResult`, so the run completes and the dashboard shows a banner
  rather than crashing.
- **Threshold:** `points > 100` (a configurable module constant). After filtering, the
  digest is capped at the top **8** items by points.
- **Text posts:** Ask HN / Show HN entries with a null `url` link to their HN item page.

## Structure

Hacker News sits behind a small adapter even though it is the only feed — `CLAUDE.md`
mandates the adapter seam, and it is exactly what Slice 2 extends when more feeds land.

```
run.py                  # entry point: `python run.py` → writes dashboard.html + prints a summary
newsclaw/
  __init__.py
  models.py             # Candidate + FetchResult dataclasses
  window.py             # compute the UTC 24h window (start, end)
  hackernews.py         # adapter: fetch(window) -> FetchResult{status, candidates, error}
  relevance.py          # AI keyword allowlist + is_relevant(); returns matched topics
  rank.py               # threshold + sort-by-points + cap at 8
  render.py             # render dashboard.html (inline CSS, escapes all dynamic text)
tests/
  __init__.py
  fixtures/             # sample HN API responses as JSON
  test_*.py             # unittest modules, one per unit
```

### Data model (Slice 1 subset of the PRD `Item`)

```
Candidate:
  source        str        # "hackernews"
  source_id     str        # HN objectID
  title         str
  url           str        # story url; falls back to hn_url for text posts
  hn_url        str        # https://news.ycombinator.com/item?id=<objectID>
  points        int
  num_comments  int
  created_at    datetime   # UTC, timezone-aware
  topics        list[str]  # which allowlist terms matched (for display)

FetchResult:
  source        str        # "hackernews"
  status        str        # "ok" | "failed"
  candidates    list[Candidate]
  error         str | None # populated when status == "failed"
```

No clustering, velocity, or persistence fields — those belong to the canonical `Item` in
Slice 2's `state.json`.

## Relevance filter

A short allowlist of AI/agent-dev terms matched case-insensitively against the story
title and url (e.g. `llm`, `agent`, `model`, `gpt`, `claude`, `gemini`, `rag`, `mcp`,
`transformer`, `diffusion`, `neural`, `fine-tun`, `inference`, `openai`, `anthropic`,
`hugging face`, and similar). A story is kept if it matches any term; the matched terms
become its `topics`. This is mechanical and knowingly imperfect — it can miss an
oddly-titled item or admit a false positive. That is acceptable for a proof-of-shape
slice and is superseded by the S3 judge. The exact term list lives in `relevance.py` and
is easy to tune.

## Ranking

1. Keep candidates with `points > THRESHOLD` (already enforced by the query; re-checked
   defensively in code).
2. Sort by `points` descending.
3. Cap at the top 8.

No controversy adjustment, no velocity — points only.

## Rendering

`dashboard.html` reuses the `prd.html` design tokens (the same CSS custom properties,
light/dark support, mono/sans pairing) so it reads as one product, adapted to a digest
layout. All dynamic text is passed through `html.escape`. The file is self-contained
(inline CSS, no external assets) and responsive.

- **Header:** date in SGT, "AI News Monitor — morning digest", the window covered, the
  item count, and a **per-feed health line**.
- **Item card:** rank number, title linking to the story url, an HN source chip, the
  `points · comments` signal, matched-topic tags, a secondary "discussion" link to the HN
  thread, and a relative age ("3h ago").
- **Empty state:** a clear message when nothing clears the bar in the window.
- **Failure banner:** a prominent banner at the top when the HN fetch failed, so a broken
  feed is obvious rather than silently producing an empty digest.

## Error handling

- Feed fetch failure → degraded `FetchResult(status="failed")`; the render shows the
  failure banner and an empty item list. The process exits successfully (the run
  completed and reported its health).
- Zero relevant items on a healthy fetch → the empty-state message, no banner.
- Malformed individual hits (missing fields) are skipped, not fatal.

## Testing (TDD)

Written test-first (red → green) per the test-driven-development skill. Run with
`python -m unittest`. Standard library `unittest` + `unittest.mock` only.

- **window** — the 24h UTC window math (start/end, ordering).
- **hackernews** — HN JSON → `Candidate` parsing from a fixture; text-post url fallback;
  a mocked `urlopen` raising → `FetchResult(status="failed")`; malformed hit skipped.
- **relevance** — a matching title kept with correct topics; a non-AI title rejected.
- **rank** — threshold enforced, sorted by points, capped at 8.
- **render** — output contains the expected items; HTML in a title is escaped; failure
  banner present when status is failed; empty-state message when there are no items.

## Manual run

`python run.py`:
1. Compute the window.
2. Fetch HN via the adapter.
3. Filter for relevance, rank, cap at 8.
4. Render and write `dashboard.html`.
5. Print a one-line summary to stdout: window, feed status, candidates fetched, kept
   after filter, published count.

## Docs to update in this slice

- **`CLAUDE.md`** — add the toolchain and conventions: Python 3.11+ stdlib only, entry
  point `python run.py`, tests via `python -m unittest`.
- **`implementation-notes.md`** — record the S1 simplifications (health rendered inline
  rather than persisted, rolling-24h window, signal-only cards) as deviations with their
  reasons.

## Out of scope (restated from PRD §6)

State/`state.json`, clustering, velocity, repeat suppression, the LLM judge, scheduling,
additional feeds, push delivery. All arrive in later slices.
