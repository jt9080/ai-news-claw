"""Render the digest to a self-contained dashboard.html.

The design is "The Morning Claw" — a salmon-paper broadsheet (FT register):
Playfair Display for the masthead and headlines, Source Serif 4 for body text,
JetBrains Mono for kickers and signal telemetry. A cockpit rail on the left
carries the wire services (each feed with its real mark as an inline SVG,
fetch count, and status), the run window, and the edition's topics; the ranked
stories run down the right, the lead story set larger. Light theme only —
newspapers are paper.

All dynamic text is escaped. Per-feed health lives in the rail; any failed feed
or a failed judge raises a correction-style notice while the rest publishes.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo

from newsclaw.models import Candidate, DigestItem

SGT = ZoneInfo("Asia/Singapore")

MASTHEAD = "The Morning Claw"

# Feed identity → human label + chip badge.
_LABELS = {"hackernews": "Hacker News", "github": "GitHub", "huggingface": "Hugging Face",
           "arxiv": "arXiv", "reddit": "Reddit", "blogs": "Blogs"}
_BADGES = {"hackernews": "HN", "github": "GitHub", "huggingface": "HF",
           "arxiv": "arXiv", "reddit": "Reddit", "blogs": "Blog"}

# Inline SVG marks, one per source. Kept on one line each so they can sit
# inside chips and rail rows; brand colors are hard-coded, not themed.
_LOGOS = {
    "hackernews": '<svg class="slogo" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="4" fill="#FF6600"/><path fill="#fff" d="M13.2 13.9v5.1h-2.4v-5.1L6.3 5.4h2.8l3.1 6 3.1-6h2.8z"/></svg>',
    "github": '<svg class="slogo" viewBox="0 0 16 16" aria-hidden="true"><path fill="#1B1817" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>',
    "huggingface": '<svg class="slogo" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="5" fill="#FFD21E"/><circle cx="8.4" cy="10" r="1.5" fill="#1B1817"/><circle cx="15.6" cy="10" r="1.5" fill="#1B1817"/><path d="M7.6 13.8c1.2 2.1 2.7 3.2 4.4 3.2s3.2-1.1 4.4-3.2" stroke="#1B1817" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>',
    "arxiv": '<svg class="slogo" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="4" fill="#B31B1B"/><path d="M7 6.2l10 11.6M17 6.2L7 17.8" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></svg>',
    "reddit": '<svg class="slogo" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#FF4500"/><path d="M12 10.2V6.6l3.4-.9" stroke="#fff" stroke-width="1.4" fill="none" stroke-linecap="round"/><circle cx="15.9" cy="5.4" r="1.2" fill="#fff"/><circle cx="5.7" cy="11.6" r="1.6" fill="#fff"/><circle cx="18.3" cy="11.6" r="1.6" fill="#fff"/><ellipse cx="12" cy="14.4" rx="6.7" ry="4.4" fill="#fff"/><circle cx="9.6" cy="13.7" r="1.1" fill="#FF4500"/><circle cx="14.4" cy="13.7" r="1.1" fill="#FF4500"/><path d="M9.8 16.2c.7.6 1.4.9 2.2.9s1.5-.3 2.2-.9" stroke="#FF4500" stroke-width="1.1" fill="none" stroke-linecap="round"/></svg>',
    "blogs": '<svg class="slogo" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="4" fill="#F26522"/><circle cx="7.4" cy="16.6" r="2" fill="#fff"/><path d="M5.5 10.6a8 8 0 0 1 7.9 7.9M5.5 5.6a13 13 0 0 1 12.9 12.9" stroke="#fff" stroke-width="2.3" fill="none" stroke-linecap="round"/></svg>',
}

# The paper's emblem: three tapered claret talon slashes. Reused inline beside
# the masthead and, URL-encoded, as the favicon.
_CLAW_PATHS = (
    '<g fill="#990F3D">'
    '<path d="M16 10 Q34 40 44 88 Q40 92 36 90 Q22 48 10 16 Q12 10 16 10z"/>'
    '<path d="M40 4 Q54 36 62 80 Q58 84 54 82 Q44 42 34 10 Q36 4 40 4z"/>'
    '<path d="M62 12 Q72 38 76 70 Q72 74 68 72 Q60 42 54 18 Q57 12 62 12z"/>'
    '</g>'
)
_CLAW_LOGO = f'<svg class="mastlogo" viewBox="0 0 80 100" aria-hidden="true">{_CLAW_PATHS}</svg>'
_FAVICON = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
    + quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 100">{_CLAW_PATHS}</svg>')
    + '">'
)

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500'
    '&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400'
    '&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)

_CSS = """
:root {
  --paper:#FFF1E5; --ink:#33302E; --headline:#1A1817; --muted:#8F857B;
  --rule:#33302E; --hairline:#E6D3C1; --claret:#990F3D; --teal:#0D7680;
}
* { box-sizing: border-box; }
body {
  background: var(--paper); color: var(--ink);
  font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif;
  font-size: 1.02rem; line-height: 1.6; margin: 0; padding: 2.4rem 1.4rem 4rem;
  -webkit-font-smoothing: antialiased;
}
.edition { max-width: 66rem; margin: 0 auto; }
.mono, .dateline, .railhead, .wire, .window-line, .kicker, .lbl, .sig, footer {
  font-family: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace;
}
a { color: var(--claret); text-underline-offset: 3px; }
a:focus-visible { outline: 2px solid var(--claret); outline-offset: 2px; }

.masthead { text-align: center; padding: 0.4rem 0 1.15rem; border-bottom: 1px solid var(--rule); }
.mastrow { display: flex; align-items: center; justify-content: center; gap: 1.1rem; }
.mastlogo { width: 2.7rem; height: auto; flex: 0 0 auto; }
.masthead h1 {
  font-family: 'Playfair Display', Georgia, serif; font-weight: 600;
  font-size: clamp(2.3rem, 5.5vw, 3.4rem); line-height: 1.1;
  letter-spacing: 0.01em; color: var(--headline); margin: 0;
}
.dateline { font-size: 0.68rem; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); margin: 0.65rem 0 0; }

.frame { display: grid; grid-template-columns: 14.5rem minmax(0, 1fr); gap: 0 2.4rem; padding-top: 1.7rem; }
.rail { border-right: 1px solid var(--hairline); padding-right: 2.4rem; }
.rail section { margin-bottom: 1.8rem; }
.rail section.assignment { border: 1px solid var(--claret); padding: 0.85rem 1rem 0.95rem; }
.assignment .railhead { color: var(--claret); }
.atext { font-size: 0.95rem; font-style: italic; line-height: 1.55; margin: 0 0 0.65rem; }
.alink { font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace; font-size: 0.68rem; margin: 0; overflow-wrap: anywhere; }
.alink a { color: var(--claret); text-decoration: none; }
.alink a:hover { text-decoration: underline; }
.railhead { font-size: 0.62rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); margin: 0 0 0.65rem; }
.wires { list-style: none; margin: 0; padding: 0; }
.wire { display: flex; align-items: center; gap: 0.5rem; padding: 0.34rem 0; font-size: 0.74rem; }
.wire .wname { flex: 1 1 auto; }
.wire .wnum { color: var(--muted); }
.wire.failed .wname, .wire.failed .wnum { color: var(--claret); font-weight: 600; }
.slogo { width: 0.95rem; height: 0.95rem; flex: 0 0 auto; display: inline-block; vertical-align: -0.14em; }
.window-line { font-size: 0.72rem; line-height: 1.7; color: var(--muted); margin: 0; }
.edition-topics { font-size: 0.92rem; font-style: italic; line-height: 1.7; margin: 0; }

.notice { border: 1px solid var(--claret); color: var(--claret); padding: 0.85rem 1.1rem; margin: 0 0 1.4rem; font-size: 0.92rem; }
.notice strong { display: block; font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace; font-size: 0.62rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 0.3rem; }

.story { padding: 1.45rem 0 1.6rem; }
.story + .story { padding-top: 0.55rem; }
.story + .story::before {
  content: "\\2766"; display: block; text-align: center;
  color: #C9B39F; font-size: 0.95rem; line-height: 1; padding-bottom: 1.35rem;
}
.story.hero { padding-top: 0.2rem; }
.kicker { font-size: 0.66rem; font-weight: 500; letter-spacing: 0.16em; text-transform: uppercase; color: var(--claret); margin: 0 0 0.55rem; }
.story h2 {
  font-family: 'Playfair Display', Georgia, serif; font-weight: 600;
  font-size: 1.32rem; line-height: 1.28; color: var(--headline);
  margin: 0 0 0.55rem; text-wrap: balance;
}
.story.hero h2 { font-size: 2.05rem; line-height: 1.16; }
.story h2 a { color: inherit; text-decoration: none; }
.story h2 a:hover { text-decoration: underline; text-decoration-thickness: 1px; }
.what { font-size: 1rem; margin: 0 0 0.45rem; }
.story.hero .what { font-size: 1.08rem; }
.why { font-style: italic; font-size: 0.98rem; margin: 0 0 0.45rem; }
.fb { font-size: 0.95rem; margin: 0 0 0.75rem; }
.lbl { font-size: 0.6rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--claret); margin-right: 0.45rem; }
.sig { font-size: 0.7rem; color: var(--muted); margin: 0.6rem 0 0; display: flex; flex-wrap: wrap; gap: 0.25rem 0.55rem; align-items: center; }
.src { display: inline-flex; align-items: center; gap: 0.34rem; color: var(--ink); font-weight: 500; }
.strong { color: var(--claret); font-weight: 600; }
.vel { color: var(--teal); font-weight: 600; }
.sep { color: var(--hairline); }
.disc { color: var(--muted); text-decoration: none; border-bottom: 1px dotted var(--muted); }
.disc:hover { color: var(--claret); border-bottom-color: var(--claret); }

.empty { text-align: center; font-style: italic; color: var(--muted); padding: 3.5rem 1rem; }
footer {
  margin-top: 2.6rem; border-top: 1px solid var(--rule); padding-top: 0.85rem;
  font-size: 0.64rem; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--muted); text-align: center;
}

@media (max-width: 52rem) {
  .frame { grid-template-columns: 1fr; }
  .rail { border-right: none; border-bottom: 1px solid var(--hairline); padding: 0 0 0.6rem; display: flex; flex-wrap: wrap; gap: 0 2.4rem; }
  .rail section { margin-bottom: 1.1rem; }
  .story.hero h2 { font-size: 1.55rem; }
  .mastlogo { width: 1.9rem; }
}
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


def _fmt_dateline(dt: datetime) -> str:
    local = dt.astimezone(SGT)
    # %d then lstrip("0") keeps this portable (no %-d on Windows).
    day = local.strftime("%d").lstrip("0")
    return local.strftime(f"%A, {day} %B %Y")


def _memory_tag(item: DigestItem) -> str:
    # Only "back" is worth ink: new is the default state of news.
    return "back" if item.resurfaced else ""


def _source_bits(c: Candidate) -> list:
    """Chip (logo + badge) + signal (+ comments/velocity/discussion) spans for
    one clustered source."""
    logo = _LOGOS.get(c.source, "")
    bits = [f'<span class="src">{logo}{escape(_BADGES.get(c.source, c.source))}</span>']
    if c.signal_value > 0:
        bits.append(f'<span class="strong">{c.signal_value} {escape(c.signal_name)}</span>')
    else:
        # signal-less feed (arXiv/Reddit/blogs): show the descriptor, not "0 x"
        bits.append(f'<span>{escape(c.signal_name)}</span>')
    if c.num_comments is not None:
        bits.append(f'<span>{c.num_comments} comments</span>')
    if c.velocity and c.velocity > 0:
        bits.append(f'<span class="vel">&#9650; {int(c.velocity)}</span>')
    if c.discussion_url:
        bits.append(f'<a class="disc" href="{escape(c.discussion_url)}">discussion &rsaquo;</a>')
    return bits


def _text_block(item: DigestItem) -> str:
    """What / Why / For-builders lines, each shown only when non-empty (the
    stand-in fallback leaves them blank, so its entries stay title + signal)."""
    parts = []
    if item.what:
        parts.append(f'<p class="what">{escape(item.what)}</p>')
    if item.why:
        parts.append(f'<p class="why">{escape(item.why)}</p>')
    if item.for_builders:
        parts.append(f'<p class="fb"><span class="lbl">For builders</span>{escape(item.for_builders)}</p>')
    return ("\n      " + "\n      ".join(parts)) if parts else ""


def _render_item(item: DigestItem, now: datetime, hero: bool = False) -> str:
    kicker_bits = (["Lead story"] if hero else []) + [escape(item.kind)]
    tag = _memory_tag(item)
    if tag:
        kicker_bits.append(tag)
    kicker = " &middot; ".join(kicker_bits)

    primary = item.sources[0]
    sig_bits = []
    for c in item.sources:
        sig_bits.extend(_source_bits(c))
    sig_bits.append(f'<span>{escape(relative_age(primary.created_at, now))}</span>')
    sig_bits.extend(f'<span>{escape(t)}</span>' for t in item.topics)
    sig = '\n        <span class="sep">&middot;</span>\n        '.join(sig_bits)

    return f"""
    <article class="story{' hero' if hero else ''}">
      <p class="kicker">{kicker}</p>
      <h2><a href="{escape(item.url)}">{escape(item.title)}</a></h2>{_text_block(item)}
      <p class="sig">
        {sig}
      </p>
    </article>"""


def _render_assignment(assignment) -> str:
    if assignment is None:
        return ""
    return f"""<section class="assignment">
      <h3 class="railhead">The Assignment</h3>
      <p class="atext">{escape(assignment.text)}</p>
      <p class="alink"><a href="{escape(assignment.url)}">&rarr; {escape(assignment.title)}</a></p>
    </section>
    """


def _render_rail(feeds, window_line: str, items, assignment=None) -> str:
    wires = "\n        ".join(
        f'<li class="wire{"" if f.status == "ok" else " failed"}">'
        f'{_LOGOS.get(f.source, "")}'
        f'<span class="wname">{escape(_LABELS.get(f.source, f.source))}</span>'
        f'<span class="wnum">{len(f.candidates) if f.status == "ok" else "failed"}</span></li>'
        for f in feeds
    )
    topics = list(dict.fromkeys(t for item in items for t in item.topics))
    topics_section = ""
    if topics:
        topics_section = f"""
    <section>
      <h3 class="railhead">In this edition</h3>
      <p class="edition-topics">{" &middot; ".join(escape(t) for t in topics)}</p>
    </section>"""
    return f"""<aside class="rail">
    {_render_assignment(assignment)}<section>
      <h3 class="railhead">Wire services</h3>
      <ul class="wires">
        {wires}
      </ul>
    </section>
    <section>
      <h3 class="railhead">Window</h3>
      <p class="window-line">{escape(window_line)}</p>
    </section>{topics_section}
  </aside>"""


def render_dashboard(items, window, feeds, now: datetime, judge_failed: bool = False,
                     assignment=None) -> str:
    """Return the complete dashboard.html document as a string.

    ``items`` are DigestItems (from the judge, or the stand-in wrapped). ``feeds``
    is every feed's FetchResult so the rail + notices cover all sources. When
    ``judge_failed`` is set, a notice explains the digest is the signal-ranked
    stand-in. ``assignment`` (an Assignment or None) draws the rail card."""
    start, end = window
    date_line = _fmt_sgt(now)
    dateline = _fmt_dateline(now)
    window_line = f"{_fmt_sgt(start)} → {_fmt_sgt(end)} SGT"

    failed = [f for f in feeds if f.status == "failed"]
    notices = ""
    if judge_failed:
        notices += """
    <div class="notice">
      <strong>Notice &mdash; LLM judge unavailable</strong>
      Showing the signal-ranked stand-in instead of the judged digest &mdash; relevance and the &ldquo;why it matters&rdquo; lines are absent this run.
    </div>"""
    if failed:
        names = ", ".join(_LABELS.get(f.source, f.source) for f in failed)
        errors = "; ".join(escape(f.error or "unknown error") for f in failed)
        notices += f"""
    <div class="notice">
      <strong>Notice &mdash; feed unavailable</strong>
      {escape(names)} unavailable this run &mdash; its stories are missing from the digest. Error: {errors}
    </div>"""

    if items:
        body = "\n".join(
            _render_item(item, now, hero=(i == 0)) for i, item in enumerate(items)
        )
    elif failed and not any(f.status == "ok" for f in feeds):
        body = ""
    else:
        body = """
    <div class="empty">Nothing cleared the bar in this window. A quiet day.</div>"""

    n = len(items)
    stories_word = "story" if n == 1 else "stories"
    footer_line = (
        "Signal-ranked stand-in (LLM judge unavailable)" if judge_failed
        else "Curated by an LLM judge over 24h signals + memory"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{MASTHEAD} — {escape(date_line)}</title>
{_FAVICON}
{_FONTS}
<style>{_CSS}</style>
</head>
<body>
<div class="edition">
  <header class="masthead">
    <div class="mastrow">
      {_CLAW_LOGO}
      <h1>{MASTHEAD}</h1>
    </div>
    <p class="dateline">{escape(dateline)} &middot; Morning Edition &middot; {n} {stories_word}</p>
  </header>
  <div class="frame">
  {_render_rail(feeds, window_line, items, assignment)}
  <section class="stories">{notices}{body}
  </section>
  </div>
  <footer>{MASTHEAD} &middot; {footer_line} &middot; Printed {escape(date_line)} SGT</footer>
</div>
</body>
</html>
"""
