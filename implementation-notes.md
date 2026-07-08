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

### Slice 3 — The LLM judge (2026-07-08)
Replaced the stand-in with a real LLM judge via OpenCode Zen (OpenAI-compatible
`/chat/completions`, stdlib `urllib`). New modules: `llm` (client, env-configured
key/base-url/model, default `gpt-5.4-mini`), `judge` (prompt + robust JSON parse
→ `DigestItem`s). `render` now shows the judge's `why` + `kind` and consumes a
uniform `DigestItem`; `rank` became the fallback selector. On any judge failure
`run.py` degrades to the stand-in + banner and records `judge: failed`. 87 tests
green on 3.9.6 (HTTP fully mocked — no key needed in CI). Keyless live run
confirmed the fallback. Design spec:
`docs/superpowers/specs/2026-07-08-slice-3-llm-judge-design.md`.

### Slice 3 — richer cards (2026-07-08, folded into PR #6)
Expanded each judged item from a single one-line `why` to three one-sentence
fields: `what` (what the news is), `why` (why it matters), `for_builders` (the
agent-builder takeaway). `DigestItem` carries all three; `judge` requires
`what`+`why` (drops the item otherwise) and treats `for_builders` as optional;
`render` shows three labeled lines, each omitted when blank (so stand-in
fallback cards stay title+signal). PRD §6 "full summarization" revised to allow
this bounded three-sentence block (still not article/paper summaries). No spec
doc (user opted to skip — straightforward). 95 tests green.

### Remaining feeds — HF, arXiv, Reddit, blogs (2026-07-08)
Completed the feed catalog. New `feedparse` (stdlib RSS+Atom parser) backs three
adapters — `arxiv` (cs.MA+cs.AI, first-submission only), `reddit` (3 subs via
`top/day` RSS, no auth), `blogs` (6 RSS/Atom sources) — plus `huggingface` (JSON:
trending models + daily_papers). Signal-less feeds carry `signal_value=0` with an
honest name (`recency`/`top`/`editorial`); the judge weighs them on content.
`run.py` fetches all six and caps each feed to `PER_FEED_CAP=20` before the judge.
`render` gained badges + value-0 display (label, not "0 x"). 121 tests green;
live run: all six feeds ok, 169→116→7, digest spanned HN/GitHub/Reddit/arXiv.
Design spec: `docs/superpowers/specs/2026-07-08-remaining-feeds-design.md`.

### Slice 4 — Run unattended (2026-07-08)
Scheduled GitHub Action (`.github/workflows/sitrep.yml`, cron `0 0 * * *` = 08:00
SGT, + `workflow_dispatch`) runs `python run.py` with `OPENCODE_API_KEY` from a
repo secret, then commits `dashboard.html`/`index.html`/`state.json`/`runs.json`
back with `[skip ci]`. GitHub Pages (deploy-from-branch, main/root; `.nojekyll`)
serves `index.html` at the Pages URL. `state.json`/`runs.json` un-gitignored so
memory persists across runs (first CI run seeds them). `window.py` switched to
the fixed UTC-day boundary. Cross-check + corrections deferred. 122 tests green;
local smoke run confirmed the fixed window + all six feeds. Spec:
`docs/superpowers/specs/2026-07-08-slice-4-unattended-design.md`.
Manual steps for the user: add the `OPENCODE_API_KEY` repo secret; enable Pages
(Settings → Pages → main/root).

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
  normalization). *Update (S3):* not deleted — it is now the judge's fallback path.

### Slice 3
- **Stand-in kept as the judge fallback**, not deleted as the S2 spec anticipated. Judge
  failure (no key / HTTP / bad JSON) degrades to it with a banner, so the run always
  publishes.
- **No persisted `Item` / cluster ids.** Clustering is ephemeral per run; the LLM decides
  suppression from the per-candidate memory we feed it, and `run.py` stamps `reported_at`
  on published member records. State stays record-level.
- **Mechanical 2×-peak resurface retired.** `ingest` still stores `peak_signal`/`velocity`,
  but they are now judge *inputs*; the LLM decides what a material jump is.
- **`runs.json` `judge` status** (`ok` / `failed` / `skipped`) is stored in the `feeds`
  dict (skipped = no relevant candidates to judge).
- **Provider is OpenCode Zen** (OpenAI-compatible), all env-overridable
  (`OPENCODE_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`). No SDK — stdlib only.
- **Provider endpoint is OpenCode Go** (`https://opencode.ai/zen/go/v1`), a flat-rate
  subscription, default model `deepseek-v4-pro`. The plain Zen endpoint's paid models are
  per-token and the account had no credits (`401 CreditsError`); the Go subscription
  covers a set of open reasoning models (deepseek-v4-pro, glm-5.2, qwen3.7-max,
  kimi-k2.7-code…) at no marginal cost. Model ids are **bare** (the `opencode-go/` prefix
  from their config is rejected by the raw API). Auth is `Authorization: Bearer`.
- **Timeout is 240s.** The Go reasoning models take ~80-95s on the full digest payload
  and vary; 120s was too tight (caused a live judge failure). It's a daily batch call, so
  a long timeout is fine, and the stand-in fallback still covers a genuine hang.
- **`.env` is loaded in-process** by `run.py` at the CLI entry (`_load_dotenv`), not via
  shell `source` (a guardrail blocks sourcing secrets). Keeps the key out of the shell;
  `.env` is gitignored.
