# Slice 4 — Run unattended

**Date:** 2026-07-08
**Status:** Agreed
**Source of truth:** `prd.html` (§4 slice S4, §7 decisions), `CLAUDE.md`,
`.github/workflows/sitrep.yml.disabled`.

## Goal

Make the digest run itself. A scheduled GitHub Action executes `python run.py`
every morning at 08:00 Singapore time, publishes the result to a live GitHub
Pages URL, and commits its memory back so suppression and velocity work across
days. Unattended and trustworthy: one flaky feed or a judge outage degrades the
run (never crashes), and every run is recorded in `runs.json`.

## Scope (decided in brainstorming)

**In:** schedule + `workflow_dispatch`, API key from a repo secret, fixed
UTC-day window, commit-back of memory + product, GitHub Pages hosting, per-feed
health (already present).

**Deferred:** the newsletter cross-check and retraction corrections. Newsletters
are already an intake feed (the judge sees them), and reliable retraction
detection is hard (an item aging out of the window looks identical to a
retraction). Add later only if a real gap shows.

## Deviation from the scaffold

`sitrep.yml.disabled` envisioned a deterministic change-detector plus a headless
`claude -p` running a `/sitrep` skill. Our architecture makes both unnecessary:
`run.py` is self-contained (fetch → filter → ingest → judge over HTTP → render),
so the workflow is simply *checkout → run → publish*. The scaffold is renamed to
`sitrep.yml` with rewritten contents.

## Components

### 1. Workflow — `.github/workflows/sitrep.yml`

- **Triggers:** `schedule: - cron: "0 0 * * *"` (00:00 UTC = 08:00 Asia/Singapore;
  cron is UTC) and `workflow_dispatch: {}` for manual runs.
- **Permissions:** `contents: write` (to commit back).
- **Concurrency:** a single group so overlapping runs can't race the commit.
- **Steps:**
  1. `actions/checkout@v4`.
  2. `actions/setup-python@v5` with `python-version: "3.11"`.
  3. Run the digest: `python run.py`, with `env: OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}`
     (also passes `LLM_MODEL`/`LLM_BASE_URL` if set as vars). No `pip install` —
     stdlib only.
  4. Publish + persist: `cp dashboard.html index.html`, then if
     `git status --porcelain` shows changes, commit `dashboard.html`,
     `index.html`, `state.json`, `runs.json` as `github-actions[bot]` with
     message `chore: morning digest <UTC date> [skip ci]` and push. The
     `[skip ci]` and the fact that the workflow only runs on schedule/dispatch
     (not `push`) both prevent self-triggering.

### 2. Memory persistence

- Remove `state.json` and `runs.json` from `.gitignore` so they are tracked.
- Do **not** commit local dev copies; the first CI run seeds them fresh (empty
  memory → builds up over subsequent days).
- The commit-back step keeps them current across runs — this is what makes
  suppression/velocity function unattended.

### 3. GitHub Pages

- Hosting model: **deploy from branch** (`main`, root). Pushing the commit-back
  triggers GitHub's automatic Pages build — no extra deploy action.
- `index.html` (a copy of `dashboard.html`) is the Pages entry point, served at
  `https://<owner>.github.io/ai-news-claw/`.
- A `.nojekyll` file at the repo root disables Jekyll so the HTML is served
  verbatim.
- One-time manual step (documented, not automatable here): enable Pages in repo
  Settings → Pages → Source: Deploy from a branch → `main` / `/` (root).

### 4. Fixed UTC-day window — `newsclaw/window.py`

Replace the rolling-24h window with the PRD boundary:

```
end   = now floored to 00:00:00 UTC (start of the current UTC day)
start = end - 24h
```

At the 00:00-UTC run this reports the calendar day that just ended
(`[yesterday 00:00, today 00:00]`). Consistent for manual runs too — a manual
daytime run now shows the previous complete UTC day, which is the intended
scheduled behavior (superseding the S1 rolling-window convenience).

## Error handling / trust

- Unchanged degrade-never-crash posture: each feed adapter and the judge already
  fall back independently; the workflow's run step therefore exits 0 on a
  degraded-but-published run, and the commit-back still publishes.
- A genuinely empty/failed run still writes a dashboard (banner/empty state) and
  appends a `runs.json` record, so the Pages URL and the health log always
  reflect the latest attempt.
- No secret in CI logs: the key is passed via `env` from `secrets`, never echoed.

## Testing / verification

- **Unit:** rewrite `test_window.py` for the fixed UTC-day boundary (start of
  day, 24h span, arbitrary `now` within a day maps to that day's window).
- **Local:** `python run.py` still runs green with the new window (smoke).
- **Workflow YAML:** validate it parses.
- **Full suite:** all `unittest` green on 3.9.
- **Real unattended path (needs the repo secret):** after merge, the user adds
  `OPENCODE_API_KEY` as a repo secret and enables Pages; then a
  `workflow_dispatch` run is triggered and watched — it must run green, commit
  `dashboard.html`/`index.html`/`state.json`/`runs.json`, and the Pages URL must
  render the digest. This is the true end-to-end proof and cannot be fully
  verified from the dev machine.

## Success criteria

- The scheduled workflow runs `python run.py` daily at 08:00 SGT and publishes
  to the Pages URL.
- Memory persists between runs (a repeat is suppressed the next day; velocity is
  computed against the stored snapshot).
- A single feed or judge failure degrades gracefully; the run still publishes
  and records health.
- All tests green on Python 3.9; no secret ever appears in logs.
