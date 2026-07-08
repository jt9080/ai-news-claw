"""Ingest: fold this run's candidates into the persisted memory.

For each candidate we compute the two things the S3 LLM structurally cannot do
for itself and annotate them onto the candidate:

- **velocity** — the signal delta since the last run. On a story's first sight
  there is no prior snapshot, so velocity falls back to a creation-to-now rate
  (``signal / age_days``).
- **resurfaced** — whether an already-reported story has jumped to >= 2x its
  *prior* peak (the peak from before this run), which is the mechanical half of
  the "resurface only on a material jump" rule. Computed against the old peak
  before it is updated, so a story can never fail to resurface just because the
  peak already absorbed today's value.

The matching ``SeenRecord`` is created or updated in place.
"""

from __future__ import annotations

from datetime import datetime

from newsclaw.models import Candidate, SeenRecord

# A reported story resurfaces when its signal reaches this multiple of its prior
# peak. A one-line tuning knob (chosen 2x in the S2 brainstorm).
RESURFACE_FACTOR = 2


def _key(candidate: Candidate) -> str:
    return f"{candidate.source}:{candidate.source_id}"


def ingest(candidates: list, records: dict, now: datetime) -> None:
    """Upsert candidates into ``records`` and annotate velocity / is_new /
    resurfaced onto each candidate. Mutates both in place."""
    now_iso = now.isoformat()
    for c in candidates:
        key = _key(c)
        rec = records.get(key)
        if rec is None:
            c.is_new = True
            c.resurfaced = False
            age_days = max((now - c.created_at).total_seconds() / 86400.0, 1.0)
            c.velocity = round(c.signal_value / age_days, 2)
            records[key] = SeenRecord(
                source=c.source, source_id=c.source_id, title=c.title, url=c.url,
                signal_name=c.signal_name, signal_value=c.signal_value,
                peak_signal=c.signal_value, prior_value=c.signal_value,
                velocity=c.velocity, first_seen=now_iso, last_seen=now_iso,
                reported_at=None,
            )
        else:
            c.is_new = False
            c.velocity = float(c.signal_value - rec.signal_value)
            prior_peak = rec.peak_signal
            c.resurfaced = (
                rec.reported_at is not None
                and c.signal_value >= RESURFACE_FACTOR * prior_peak
            )
            rec.prior_value = rec.signal_value
            rec.signal_value = c.signal_value
            rec.velocity = c.velocity
            rec.peak_signal = max(prior_peak, c.signal_value)
            rec.last_seen = now_iso
            rec.title = c.title
            rec.url = c.url
