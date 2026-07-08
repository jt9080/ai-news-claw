"""The LLM judge — the product's actual filter (Slice 3).

One call replaces the mechanical stand-in: given today's relevant candidates and
their memory (prior reports + peak/velocity), the model clusters the same story
across sources, ranks agent-dev topics first, drops pure-discussion noise,
suppresses already-reported stories unless they made a material jump, cuts to
5-8, and writes the one-line "why it matters".

Any failure — no key, HTTP error, unparseable or structurally-invalid output —
raises ``JudgeUnavailable`` so ``run.py`` can fall back to the stand-in selector
and still publish. An empty-but-valid result is a legitimate quiet day, not a
failure.
"""

from __future__ import annotations

import json
from datetime import datetime

from newsclaw import llm
from newsclaw.models import Candidate, DigestItem

_SOURCE_PREFIX = {"hackernews": "hn", "github": "gh"}

SYSTEM_PROMPT = """\
You are the editor of a daily AI-news digest for engineers building agentic \
systems. You will receive a JSON list of candidate stories, each with its signal \
and a memory of whether it has been reported before.

Your job, using judgement (not mechanical rules):
- Rank AGENT-DEVELOPMENT topics first (multiagent, subagents, skills, tool use, \
memory, planning, geospatial agents), then general AI.
- Drop pure-discussion, low-substance, or off-topic items.
- Cluster the SAME story appearing across sources into ONE item (combine their ids).
- Suppress any story whose memory.reported_at is set, UNLESS its signal has made a \
material jump since (use memory.peak_signal and velocity to judge).
- Return 5-8 items on a normal day; fewer on a quiet day; never pad.

For each item write three fields, each ONE factual sentence (<= 25 words, no hype):
- `what`: what the news actually is.
- `why`: why it matters.
- `for_builders`: the concrete takeaway for someone building agentic systems.

Respond with ONLY a JSON object, no prose, in exactly this shape:
{"items": [{"ids": ["hn:123","gh:owner/repo"], "title": "...", "url": "...", \
"kind": "model|repo|paper|tool|post|discussion", "topics": ["multiagent"], \
"what": "one sentence", "why": "one sentence", "for_builders": "one sentence", \
"resurfaced": false}]}
Use only ids present in the input. Order the list best-first."""


# Free/trial models are slow and intermittently error; one retry before falling
# back to the stand-in absorbs most transient timeouts.
MAX_ATTEMPTS = 2


class JudgeUnavailable(Exception):
    """The judge could not produce a usable digest; caller should fall back."""


def _cand_id(c: Candidate) -> str:
    return f"{_SOURCE_PREFIX.get(c.source, c.source)}:{c.source_id}"


def build_messages(candidates: list, records: dict, now: datetime):
    """Return (system_prompt, user_json) for the judge call."""
    payload = []
    for c in candidates:
        rec = records.get(f"{c.source}:{c.source_id}")
        age_hours = int((now - c.created_at).total_seconds() // 3600)
        payload.append({
            "id": _cand_id(c),
            "source": c.source,
            "title": c.title,
            "url": c.url,
            "summary": c.summary,
            "signal": {"name": c.signal_name, "value": c.signal_value},
            "velocity": c.velocity,
            "age_hours": age_hours,
            "topics": c.topics,
            "memory": {
                "seen_before": not c.is_new,
                "reported_at": rec.reported_at if rec else None,
                "peak_signal": rec.peak_signal if rec else c.signal_value,
            },
        })
    user = json.dumps({"candidates": payload}, ensure_ascii=False)
    return SYSTEM_PROMPT, user


def judge(candidates: list, records: dict, now: datetime) -> list:
    """Return the judged digest as DigestItems, or raise JudgeUnavailable."""
    if not candidates:
        return []

    system, user = build_messages(candidates, records, now)
    text = None
    last_error = None
    for _ in range(MAX_ATTEMPTS):
        try:
            text = llm.complete(system, user)
            break
        except llm.LLMError as exc:
            last_error = exc
    if text is None:
        raise JudgeUnavailable(str(last_error)) from last_error

    data = _extract_json(text)
    if data is None or not isinstance(data.get("items"), list):
        raise JudgeUnavailable("model did not return the expected JSON shape")

    by_id = {_cand_id(c): c for c in candidates}
    return _to_items(data["items"], by_id)


def _to_items(entries: list, by_id: dict) -> list:
    items = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        sources = [by_id[i] for i in entry.get("ids", []) if i in by_id]
        title, url = entry.get("title"), entry.get("url")
        what, why = entry.get("what"), entry.get("why")
        if not sources or not title or not url or not what or not why:
            continue  # drop items missing a resolvable source or an essential field
        kind = entry.get("kind") or ("repo" if sources[0].source == "github" else "post")
        topics = entry.get("topics")
        if not isinstance(topics, list) or not topics:
            topics = sorted({t for s in sources for t in s.topics})
        items.append(DigestItem(
            title=str(title), url=str(url),
            what=str(what), why=str(why),
            for_builders=str(entry.get("for_builders") or ""),
            kind=str(kind), topics=topics,
            resurfaced=bool(entry.get("resurfaced")) or any(s.resurfaced for s in sources),
            is_new=all(s.is_new for s in sources),
            sources=sources,
        ))
    return items


def _extract_json(text: str):
    """Parse the model's reply into a dict, tolerating code fences / stray prose."""
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    # Strip a ```json ... ``` fence, then fall back to the outermost braces.
    if "```" in text:
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            return None
    return None
