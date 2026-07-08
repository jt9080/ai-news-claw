"""Shared RSS/Atom feed parser — standard library only.

Adapters for arXiv, Reddit, and the blogs/newsletters all pull XML feeds in
either RSS (``<item>``, ``<pubDate>``) or Atom (``<entry>``, ``<updated>`` /
``<published>``) shape. This turns either into a uniform list of entries so the
adapters stay thin.

Never raises: malformed or empty XML yields an empty list. Namespaces are
ignored by matching on the local tag name, so Atom's default namespace needs no
special handling at the call site.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET


def parse(data: bytes) -> list:
    """Parse RSS or Atom bytes into ``[{title, link, published, summary}]``."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []

    entries = []
    # RSS items live under channel/item; Atom entries are direct <entry> nodes.
    nodes = [n for n in root.iter() if _local(n.tag) in ("item", "entry")]
    for node in nodes:
        entries.append({
            "title": _text(node, "title"),
            "link": _link(node),
            "published": _published(node),
            "summary": _text(node, "summary") or _text(node, "description")
            or _text(node, "content"),
        })
    return entries


def _local(tag: str) -> str:
    """Strip an XML namespace: '{http://...}entry' -> 'entry'."""
    return tag.rsplit("}", 1)[-1]


def _child(node, name: str):
    for child in node:
        if _local(child.tag) == name:
            return child
    return None


def _text(node, name: str) -> str:
    child = _child(node, name)
    return (child.text or "").strip() if child is not None else ""


def _link(node) -> str:
    # RSS: <link>text</link>. Atom: <link href="..." rel="alternate"/>.
    href = ""
    for child in node:
        if _local(child.tag) != "link":
            continue
        if child.get("href"):
            rel = child.get("rel", "alternate")
            if rel == "alternate" or not href:
                href = child.get("href")
        elif child.text:
            return child.text.strip()
    return href


def _published(node):
    raw = _text(node, "published") or _text(node, "pubDate") or _text(node, "updated")
    if not raw:
        return None
    return _parse_date(raw)


def _parse_date(raw: str):
    # Atom/ISO-8601 first, then RSS/RFC-822. Return None if neither parses.
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return _as_utc(dt)
    except ValueError:
        pass
    try:
        return _as_utc(parsedate_to_datetime(raw))
    except (TypeError, ValueError):
        return None


def _as_utc(dt: datetime):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
