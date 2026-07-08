# Slice 3 — The LLM judge

**Date:** 2026-07-08
**Status:** Agreed
**Source of truth:** `prd.html` (§4 slices, §5 data model, §7 decisions — revised
2026-07-08), `CLAUDE.md`, the S2 spec, OpenCode Zen docs (OpenAI-compatible).

## Goal

Replace the deliberately-dumb stand-in selector with the actual product: **one
LLM call that makes every editorial decision.** Given today's relevant
candidates *and their memory* (prior reports + peak/velocity), the judge
clusters the same story across sources, ranks agent-dev topics first, drops
pure-discussion noise, suppresses already-reported stories unless they made a
material jump, cuts to 5–8, and writes the one-line "why it matters."

This is the slice that proves the filter. Everything in S1–S2 was plumbing to
make this call cheap, possible, and trustworthy. Scheduling and unattended
operation are **S4**, not this slice — S3 is still a manual `python run.py`.

## Decisions carried in

Locked in the brainstorming pass:

- **Provider: OpenCode Zen**, an OpenAI-compatible gateway
  (`https://opencode.ai/zen/v1/chat/completions`, `Authorization: Bearer`).
  Called with stdlib `urllib` — no SDK, toolchain rules unchanged.
- **Default model: `gpt-5.4-mini`** (cheap, capable, OpenAI-native JSON).
  Overridable via env var. Cost is negligible: one small call per day.
- **Judge-unavailable → fall back to the S2 stand-in selector** and render
  normally with a clear banner. The stand-in (`rank.select`) is therefore *not*
  deleted — it earns a permanent role as the degradation path.
- **Ephemeral clustering, record-level suppression.** No persisted canonical
  `Item`/cluster ids. State stays record-level (as S2); the LLM decides
  suppression from the per-candidate memory we feed it, and on publish we stamp
  `reported_at` on every member record.
- **The mechanical 2×-peak rule is retired.** `ingest` still computes and stores
  `peak_signal`/`velocity`, but they become *inputs to the judge* rather than a
  hard rule; the LLM decides what a "material jump" is.

## Deliberate deferrals

- **Scheduling / unattended run / repo secret** → S4.
- **Persisted canonical `Item` (PRD §5)** → not built; ephemeral clustering makes
  it unnecessary for the digest. Revisit only if a future slice needs durable
  cross-run story identity.
- **Newsletter cross-check and retraction corrections** (PRD S4 bullet) → S4.
- **Widening the relevance pre-filter** now that the LLM does real relevance →
  left as-is for S3; the allowlist still cheaply bounds the judge's input. Tune
  later if it proves too aggressive.

## Architecture

Two new thin modules under `newsclaw/`, plus edits to `render.py` and `run.py`.

| Module | Role |
|---|---|
| `llm.py` | **New.** Minimal `urllib` client for an OpenAI-compatible `/chat/completions` endpoint. Reads `OPENCODE_API_KEY`, `LLM_BASE_URL` (default `https://opencode.ai/zen/v1`), `LLM_MODEL` (default `gpt-5.4-mini`). Sends `{model, messages, temperature}` (low temp). Returns the assistant text or raises `LLMError` on missing key / HTTP / timeout. |
| `judge.py` | **New.** Builds the prompt from candidates + memory, calls `llm`, extracts and validates the JSON, and maps it back to renderable items. Raises `JudgeUnavailable` on any failure (no key, HTTP error, unparseable/empty/invalid JSON) so `run.py` can fall back. |
| `rank.py` | Unchanged behaviour — now the **fallback** selector, not throwaway. |
| `render.py` | Cards show the judge's `why` line + `kind`; footer/banner reflect judge-vs-stand-in. |
| `run.py` | Judge in the happy path; `rank.select` on `JudgeUnavailable`. |

## Data flow (`run.py`)

```
window → [hackernews.fetch, github.fetch] → relevance pre-filter
  → state.load → ingest (velocity + memory)
  → try: items = judge.judge(relevant, records, now)      # LLM
    except JudgeUnavailable: items = rank.select(...) ; judge_failed = True
  → render_dashboard(items, ..., judge_failed) → write dashboard.html
  → stamp reported_at on published member records
  → state.save + append_run
```

`runs.json` gains `judge: ok | failed | skipped` in its feeds/health so the
trust log records whether the digest was judged or fell back.

## The judge call

**Input we send** (per relevant candidate, as JSON in the user message):

```
{ "id": "hn:42150001" | "gh:owner/repo",
  "source": "hackernews" | "github",
  "title": "...", "url": "...", "summary": "... or null",
  "signal": { "name": "points|stars", "value": 412 },
  "velocity": 50.0, "age_hours": 6,
  "topics": ["agent", "llm"],
  "memory": { "seen_before": true, "reported_at": "2026-07-05T...", "prior_peak": 200 } }
```

**System prompt** encodes the editorial policy: agent-dev topics first
(multiagent, subagents, skills, geospatial agents), general AI second; drop
pure-discussion/low-substance items; cluster the same story across sources into
one item; suppress anything whose `memory.reported_at` is set *unless* its signal
made a material jump (use `prior_peak`/`velocity` to judge); return **5–8** items
(fewer on a quiet day); write a factual one-line `why`. Output **only** the JSON
object below.

**Output contract** (validated after parsing):

```json
{ "items": [
    { "ids": ["hn:42150001", "gh:owner/repo"],
      "title": "best title across sources",
      "url": "canonical link",
      "kind": "model|repo|paper|tool|post|discussion",
      "topics": ["multiagent"],
      "why": "one line: why it matters",
      "resurfaced": false }
] }
```

Validation: top-level `items` is a list; each entry has non-empty `ids` that all
resolve to fetched candidates, a `title`, a `url`, and a `why`; unknown `ids` are
dropped, and an item left with no valid id is dropped. `kind`/`topics`/`resurfaced`
default if absent. If nothing valid survives, that is a legitimate empty digest
(not a failure). We map each item's `ids` back to their candidates to recover
signal/velocity/age/discussion_url for rendering; the judge supplies
title/url/kind/topics/why/order/resurfaced.

## Error handling

- **`llm.py`** raises `LLMError` on: missing `OPENCODE_API_KEY`, network/HTTP
  error, timeout, or empty body. It never leaks a raw exception.
- **`judge.py`** catches `LLMError` and JSON/validation failures and raises
  `JudgeUnavailable(reason)`.
- **`run.py`** catches `JudgeUnavailable`, falls back to `rank.select`, sets the
  banner, and records `judge: failed` in `runs.json`. The run always publishes.
- No key present is treated the same as any other judge failure (→ stand-in),
  so `python run.py` still works with no configuration.

## Testing (TDD, all offline)

Mock the HTTP layer so no key is needed in CI.

- `test_llm.py` — builds the right request (headers, model, messages); parses
  `choices[0].message.content`; missing key → `LLMError`; HTTP error → `LLMError`.
- `test_judge.py` — prompt includes each candidate + its memory; a mocked valid
  JSON response maps to render items with correct id→candidate resolution and
  preserved order; unknown ids dropped; malformed/empty JSON → `JudgeUnavailable`;
  code-fence-wrapped JSON still parses.
- `test_render.py` — a judged item renders its `why` and `kind`; banner shown
  when `judge_failed`.
- `test_run.py` — judge-success path (mocked client) publishes judged items with
  `why` and stamps `reported_at`; `JudgeUnavailable` → stand-in items + banner +
  `runs.json` records `judge: failed`.

## Success criteria

- With `OPENCODE_API_KEY` set, `python run.py` produces a judged digest: 5–8
  clustered items, agent-dev first, each with a one-line `why`, repeats
  suppressed, `runs.json` records `judge: ok`.
- With no key or a forced failure, the same command produces the stand-in digest
  with a "judge unavailable" banner and `judge: failed` — never crashes.
- One live run against the real Zen endpoint confirms real output quality.
- All `unittest` tests green on Python 3.9, no network in the suite.
