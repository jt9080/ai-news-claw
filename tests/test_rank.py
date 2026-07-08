import unittest
from datetime import datetime, timezone

from newsclaw.models import Candidate, SeenRecord
from newsclaw.rank import select, MAX_ITEMS

NOW = datetime(2026, 7, 8, tzinfo=timezone.utc)


def make(source, source_id, value, resurfaced=False):
    c = Candidate(
        source=source, source_id=source_id, title=source_id, url="u",
        signal_name="points" if source == "hackernews" else "stars",
        signal_value=value, created_at=NOW,
    )
    c.resurfaced = resurfaced
    c.is_new = True
    return c


def rec(source, source_id, value, reported_at=None):
    return SeenRecord(
        source=source, source_id=source_id, title=source_id, url="u",
        signal_name="points", signal_value=value, peak_signal=value,
        prior_value=value, velocity=0.0, first_seen="x", last_seen="y",
        reported_at=reported_at,
    )


def state_for(cands):
    return {f"{c.source}:{c.source_id}": rec(c.source, c.source_id, c.signal_value)
            for c in cands}


class TestSuppression(unittest.TestCase):
    def test_reported_and_not_resurfaced_is_suppressed(self):
        c = make("hackernews", "a", 300)
        state = {"hackernews:a": rec("hackernews", "a", 300, reported_at="2026-07-07T00:00:00+00:00")}
        published = select([c], state, NOW)
        self.assertEqual(published, [])

    def test_reported_but_resurfaced_is_kept(self):
        c = make("hackernews", "a", 800, resurfaced=True)
        state = {"hackernews:a": rec("hackernews", "a", 800, reported_at="2026-07-07T00:00:00+00:00")}
        published = select([c], state, NOW)
        self.assertEqual([x.source_id for x in published], ["a"])

    def test_never_reported_is_kept(self):
        c = make("hackernews", "a", 300)
        published = select([c], state_for([c]), NOW)
        self.assertEqual([x.source_id for x in published], ["a"])


class TestSelection(unittest.TestCase):
    def test_caps_at_max_items(self):
        cands = [make("hackernews", f"h{i}", 500 - i) for i in range(20)]
        published = select(cands, state_for(cands), NOW)
        self.assertEqual(len(published), MAX_ITEMS)

    def test_interleaves_across_sources(self):
        cands = [
            make("hackernews", "h1", 300), make("hackernews", "h2", 200),
            make("hackernews", "h3", 100),
            make("github", "g1", 6000), make("github", "g2", 5000),
            make("github", "g3", 4000),
        ]
        published = select(cands, state_for(cands), NOW)[:4]
        self.assertEqual(
            [(c.source, c.source_id) for c in published],
            [("hackernews", "h1"), ("github", "g1"),
             ("hackernews", "h2"), ("github", "g2")],
        )

    def test_stamps_reported_at_on_published(self):
        c = make("hackernews", "a", 300)
        state = state_for([c])
        select([c], state, NOW)
        self.assertEqual(state["hackernews:a"].reported_at, NOW.isoformat())


if __name__ == "__main__":
    unittest.main()
