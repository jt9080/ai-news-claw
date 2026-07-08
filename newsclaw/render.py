"""Render the digest to a self-contained dashboard.html.

Reuses the prd.html design tokens (same CSS custom properties, light/dark
support, mono/sans pairing) so the digest reads as one product. All dynamic text
is escaped. Two feeds now: each card carries a source badge and, where the feed
provides it, a rising-velocity marker and a new/back memory tag. Per-feed health
is a status line; any failed feed raises a banner while the healthy feeds still
publish.

The selection behind this is a Slice 2 stand-in — the footer says so.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from newsclaw.models import Candidate, DigestItem

SGT = ZoneInfo("Asia/Singapore")

# Feed identity → human label + card badge.
_LABELS = {"hackernews": "Hacker News", "github": "GitHub", "huggingface": "Hugging Face",
           "arxiv": "arXiv", "reddit": "Reddit", "blogs": "Blogs"}
_BADGES = {"hackernews": "HN", "github": "GitHub", "huggingface": "HF",
           "arxiv": "arXiv", "reddit": "Reddit", "blogs": "Blog"}

_CSS = """
:root {
  --paper:#FBFBFE; --card:#FFFFFF; --ink:#14161D; --muted:#616677; --line:#E5E7EF;
  --accent:#3355EA; --accent-soft:#E9ECFD; --hot:#C6371F; --hot-bg:#FBE7E2;
  --warm:#9A6212; --warm-bg:#FAF0DC; --cool:#2C6E8F; --cool-bg:#E2F0F5; --code-bg:#F0F1F7;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper:#0D0F15; --card:#161922; --ink:#E8EAF2; --muted:#8B90A3; --line:#262A36;
    --accent:#7C93FF; --accent-soft:#1B2036; --hot:#F0897A; --hot-bg:#3A1D18;
    --warm:#E0AC5D; --warm-bg:#362A16; --cool:#6FB6D4; --cool-bg:#14303B; --code-bg:#1B1F2A;
  }
}
* { box-sizing: border-box; }
body {
  background: var(--paper); color: var(--ink);
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
  font-size: 1.02rem; line-height: 1.6; margin: 0; padding: 3.5rem 1.25rem 5rem;
  -webkit-font-smoothing: antialiased;
}
.sheet { max-width: 47rem; margin: 0 auto; }
.mono, .eyebrow, .chip, .signal, .topic, .age, .vel { font-family: ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace; }
h1 { font-size: 2.05rem; line-height: 1.12; letter-spacing: -0.02em; margin: 0.4rem 0 0.7rem; text-wrap: balance; font-weight: 700; }
a { color: var(--accent); text-underline-offset: 2px; }
.eyebrow { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.22em; text-transform: uppercase; color: var(--accent); }
.meta { color: var(--muted); font-size: 0.88rem; margin-bottom: 0.4rem; }
.health { color: var(--muted); font-size: 0.8rem; border-block: 1px solid var(--line); padding: 0.7rem 0; margin-bottom: 2.4rem; display: flex; gap: 1.1rem; align-items: center; flex-wrap: wrap; }
.health .feed { display: inline-flex; gap: 0.4rem; align-items: center; }
.health .dot { width: 0.55rem; height: 0.55rem; border-radius: 50%; display: inline-block; }
.health .dot.ok { background: var(--cool); }
.health .dot.failed { background: var(--hot); }
.banner { background: var(--hot-bg); color: var(--hot); border: 1px solid var(--hot); border-radius: 8px; padding: 0.9rem 1.15rem; margin-bottom: 2rem; font-size: 0.92rem; }
.banner strong { display: block; font-family: ui-monospace, Menlo, monospace; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.3rem; }
.empty { color: var(--muted); text-align: center; padding: 3rem 1rem; border: 1px dashed var(--line); border-radius: 8px; }
.item { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 1.05rem 1.25rem; margin-bottom: 0.9rem; display: flex; gap: 1rem; }
.rank { font-family: ui-monospace, Menlo, monospace; font-size: 1.1rem; font-weight: 700; color: var(--accent); flex: 0 0 auto; min-width: 1.6rem; }
.body { flex: 1 1 auto; min-width: 0; }
.item h2 { font-size: 1.08rem; line-height: 1.3; margin: 0 0 0.4rem; font-weight: 620; letter-spacing: -0.01em; }
.item h2 a { text-decoration: none; }
.item h2 a:hover { text-decoration: underline; }
.what { color: var(--ink); font-size: 0.96rem; margin: 0 0 0.4rem; }
.why { color: var(--ink); font-size: 0.92rem; margin: 0 0 0.35rem; }
.fb { color: var(--muted); font-size: 0.9rem; margin: 0 0 0.55rem; }
.lbl { font-family: ui-monospace, Menlo, monospace; font-size: 0.6rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--accent); margin-right: 0.4rem; }
.kind { font-size: 0.63rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; padding: 0.15rem 0.5rem; border-radius: 5px; border: 1px solid var(--line); color: var(--muted); }
.line { display: flex; flex-wrap: wrap; gap: 0.5rem 0.7rem; align-items: center; font-size: 0.82rem; }
.chip { font-size: 0.63rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; padding: 0.15rem 0.5rem; border-radius: 5px; background: var(--accent-soft); color: var(--accent); }
.chip.tag { background: var(--warm-bg); color: var(--warm); }
.signal { color: var(--ink); font-weight: 600; }
.vel { color: var(--cool); font-weight: 600; }
.age { color: var(--muted); }
.topic { font-size: 0.68rem; padding: 0.12rem 0.45rem; border-radius: 5px; background: var(--accent-soft); color: var(--accent); }
.disc { color: var(--muted); text-decoration: none; }
.disc:hover { color: var(--accent); }
footer { color: var(--muted); font-size: 0.78rem; text-align: center; margin-top: 3rem; }
""".strip()


def relative_age(created_at: datetime, now: datetime) -> str:
    """Human relative age, e.g. '3h ago', '10m ago', 'just now'."""
    seconds = (now - created_at).total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    return f"{days}d ago"


def _fmt_sgt(dt: datetime) -> str:
    return dt.astimezone(SGT).strftime("%a %d %b %Y, %H:%M")


def _tag(item: DigestItem) -> str:
    if item.resurfaced:
        return '<span class="chip tag">back</span>'
    if item.is_new:
        return '<span class="chip tag">new</span>'
    return ""


def _source_bits(c: Candidate) -> str:
    """Badge + signal (+ comments/velocity/discussion) for one clustered source."""
    bits = [f'<span class="chip">{escape(_BADGES.get(c.source, c.source))}</span>']
    if c.signal_value > 0:
        bits.append(f'<span class="signal">{c.signal_value} {escape(c.signal_name)}</span>')
    else:
        # signal-less feed (arXiv/Reddit/blogs): show the descriptor, not "0 x"
        bits.append(f'<span class="age">{escape(c.signal_name)}</span>')
    if c.num_comments is not None:
        bits.append(f'<span class="age">{c.num_comments} comments</span>')
    if c.velocity and c.velocity > 0:
        bits.append(f'<span class="vel">&#9650; {int(c.velocity)}</span>')
    if c.discussion_url:
        bits.append(f'<a class="disc" href="{escape(c.discussion_url)}">discussion &rsaquo;</a>')
    return "\n          ".join(bits)


def _text_block(item: DigestItem) -> str:
    """What / Why / For-builders lines, each shown only when non-empty (the
    stand-in fallback leaves them blank, so its cards stay title + signal)."""
    parts = []
    if item.what:
        parts.append(f'<p class="what">{escape(item.what)}</p>')
    if item.why:
        parts.append(f'<p class="why"><span class="lbl">Why</span>{escape(item.why)}</p>')
    if item.for_builders:
        parts.append(f'<p class="fb"><span class="lbl">For builders</span>{escape(item.for_builders)}</p>')
    return ("\n        " + "\n        ".join(parts)) if parts else ""


def _render_item(rank_num: int, item: DigestItem, now: datetime) -> str:
    topics = "".join(f'<span class="topic">{escape(t)}</span>' for t in item.topics)
    sources = "\n          ".join(_source_bits(c) for c in item.sources)
    primary = item.sources[0]
    return f"""
    <article class="item">
      <div class="rank">{rank_num}</div>
      <div class="body">
        <h2><a href="{escape(item.url)}">{escape(item.title)}</a></h2>{_text_block(item)}
        <div class="line">
          {_tag(item)}
          <span class="kind">{escape(item.kind)}</span>
          {sources}
          <span class="age">{escape(relative_age(primary.created_at, now))}</span>
          {topics}
        </div>
      </div>
    </article>"""


def render_dashboard(items, window, feeds, now: datetime, judge_failed: bool = False) -> str:
    """Return the complete dashboard.html document as a string.

    ``items`` are DigestItems (from the judge, or the stand-in wrapped). ``feeds``
    is every feed's FetchResult so health + banner cover all sources. When
    ``judge_failed`` is set, a banner explains the digest is the signal-ranked
    stand-in."""
    start, end = window
    date_line = _fmt_sgt(now)
    window_line = f"{_fmt_sgt(start)} → {_fmt_sgt(end)} SGT"

    failed = [f for f in feeds if f.status == "failed"]
    banner = ""
    if judge_failed:
        banner += """
    <div class="banner">
      <strong>LLM judge unavailable</strong>
      Showing the signal-ranked stand-in instead of the judged digest — relevance and the &ldquo;why it matters&rdquo; lines are absent this run.
    </div>"""
    if failed:
        names = ", ".join(_LABELS.get(f.source, f.source) for f in failed)
        errors = "; ".join(escape(f.error or "unknown error") for f in failed)
        banner += f"""
    <div class="banner">
      <strong>Feed unavailable</strong>
      {escape(names)} unavailable this run — its stories are missing from the digest. Error: {errors}
    </div>"""

    if items:
        body = "\n".join(_render_item(i + 1, item, now) for i, item in enumerate(items))
    elif failed and not any(f.status == "ok" for f in feeds):
        body = ""
    else:
        body = """
    <div class="empty">Nothing cleared the bar in this window. A quiet day.</div>"""

    health = " ".join(
        f'<span class="feed"><span class="dot {"ok" if f.status == "ok" else "failed"}"></span>'
        f'{escape(_LABELS.get(f.source, f.source))} &middot; {escape(f.status)} &middot; '
        f'{len(f.candidates)} fetched</span>'
        for f in feeds
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI News Monitor — {escape(date_line)}</title>
<style>{_CSS}</style>
</head>
<body>
<main class="sheet">
  <p class="eyebrow">Morning digest</p>
  <h1>AI News Monitor</h1>
  <p class="meta">{escape(date_line)} SGT &middot; {len(items)} item{"" if len(items) == 1 else "s"}</p>
  <p class="meta">Window: {escape(window_line)}</p>
  <div class="health">{health}</div>
  {banner}
  {body}
  <footer>{"Signal-ranked stand-in (LLM judge unavailable)." if judge_failed else "Curated by an LLM judge over 24h signals + memory."}</footer>
</main>
</body>
</html>
"""
