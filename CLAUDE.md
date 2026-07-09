# CLAUDE.md

## What this project is

AI News Monitor — an agent that watches live AI/ML feeds (Hacker News, GitHub,
Hugging Face, arXiv, Reddit, plus a set of lab blogs and newsletters), filters the
firehose down to what matters, and publishes a morning digest to `dashboard.html`
at 08:00 Singapore time (Asia/Singapore). It runs on a schedule, unattended.

The reader has five minutes. The digest answers one question: **what shipped or broke
through in the last 24 hours that someone building agentic systems should know about?**
Agent-development news (multiagent, subagents, skills, geospatial agents) is ranked
first; the rest of AI follows.

The hard part is not fetching — it is **ranking**. Every source is a firehose, so the
product is the filter: hard signals (stars/velocity, HN points, upvotes, paper
attention) build a shortlist, later refined by an LLM judge. A normal day yields 5–8
items, not fifty. Anything already reported is suppressed unless it materially jumps
(major version, big new capability, order-of-magnitude signal change).

## Data feeds

Full details, verified endpoints, and example responses live in `feeds/`. Key facts:

- **Hacker News** (`feeds/hackernews.md`) — free, no auth. Algolia search API:
  `https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=points>N`.
  Points and comment count are the signal.
- **GitHub** (`feeds/github.md`) — `github.com/trending` has no API. Use the Search API as
  a trending proxy: `api.github.com/search/repositories?q=…created:>DATE&sort=stars`.
  60 req/hr unauth, 5000/hr with a token. Star *velocity* matters more than absolute stars.
- **Hugging Face** (`feeds/huggingface.md`) — free. Trending models via
  `huggingface.co/api/models?sort=trendingScore`; curated research via
  `huggingface.co/api/daily_papers` (better filtered than raw arXiv).
- **arXiv** (`feeds/arxiv.md`) — free Atom API, **https only**, rate-limit sensitive
  (needs a polite delay). Categories: `cs.MA` (multiagent), `cs.AI`, `cs.CL`, `cs.LG`.
- **Reddit** (`feeds/reddit.md`) — the JSON API returns **403 without OAuth**; the per-sub
  RSS (`reddit.com/r/<sub>/top/.rss?t=day`) needs no auth but is rate-limit sensitive.
- **Blogs & newsletters** (`feeds/blogs-newsletters.md`) — RSS/Atom from OpenAI, Hugging
  Face, Simon Willison, Latent Space, smol.ai (AINews), Product Hunt AI. Anthropic has no
  native RSS. Newsletters are useful because they pre-digest the firehose.

Not used: **X/Twitter** — API is paid and gated, scraping is fragile and ToS-risky.
Deliberately out of scope; the newsletters above already digest most X discourse.

## Toolchain & conventions

- **Language:** Python, **standard library only** — no third-party dependencies, so the
  scheduled GitHub Actions run needs no install step. Target 3.11+, but keep the code
  3.9-compatible (`from __future__ import annotations`); the current dev machine is 3.9.6.
- **Entry point:** `python run.py` — writes `dashboard.html` and prints a one-line summary.
- **Tests:** `python -m unittest` (or `python -m unittest discover -s tests`). Test-first
  (TDD): every module has a `tests/test_*.py`; fixtures live in `tests/fixtures/`.
- **Layout:** each feed sits behind a small adapter in `newsclaw/` (`hackernews.py`, …)
  returning a degraded `FetchResult` on failure rather than raising.

## Behaviour
- Don't assume, always ask when unsure.
- Challenge me and push back where appropriate.
- Avoid overly verbose comments.
- Every source sits behind a small adapter so one flaky feed degrades the digest
  instead of crashing the run. Always record per-feed health, even on a quiet day.
