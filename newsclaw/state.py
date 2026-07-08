"""Persistence: state.json (the agent's memory) and runs.json (the trust log).

``state.json`` is a map of ``"<source>:<source_id>" -> SeenRecord``, the memory
the S3 LLM will read to judge what is new and what has jumped. ``runs.json`` is
an append-only list of ``Run`` records so per-feed health is always on record,
even on a quiet or degraded day.

Reads never raise: a missing file is a clean empty start (``status="ok"``); a
corrupt file is discarded and flagged (``status="reset"``) rather than crashing
the run. Writes are atomic (temp file + ``os.replace``) so a crash mid-write
cannot leave a half-written, unparseable memory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple

from newsclaw.models import Run, SeenRecord


def load_state(path: Path) -> Tuple[Dict[str, SeenRecord], str]:
    """Return (records, status). status is "ok" normally, "reset" if the file
    existed but was unreadable/corrupt."""
    if not path.exists():
        return {}, "ok"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = {
            key: SeenRecord.from_dict(value)
            for key, value in raw.get("records", {}).items()
        }
    except (ValueError, TypeError, KeyError):
        return {}, "reset"
    return records, "ok"


def save_state(path: Path, records: Dict[str, SeenRecord]) -> None:
    """Atomically write the state map to ``path``."""
    payload = {"records": {key: rec.to_dict() for key, rec in records.items()}}
    _atomic_write(path, json.dumps(payload, indent=2, sort_keys=True))


def append_run(path: Path, run: Run) -> None:
    """Append one Run to the runs.json log, creating it if absent."""
    log = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                log = existing
        except ValueError:
            log = []  # a corrupt log is not worth crashing over; start fresh
    log.append(run.to_dict())
    _atomic_write(path, json.dumps(log, indent=2))


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
