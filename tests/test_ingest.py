import unittest
from datetime import datetime, timedelta, timezone

from newsclaw.ingest import ingest
from newsclaw.models import Candidate, SeenRecord

NOW = datetime(2026, 7, 8, 0, 0, 0, tzinfo=timezone.utc)


def cand(source_id="omni", value=500, source="github", created_days_ago=10):
    return Candidate(
        source=source, source_id=source_id, title="t", url="u",
        signal_name="stars", signal_value=value,
        created_at=NOW - timedelta(days=created_days_ago),
    )


def record(source_id="omni", value=100, peak=100, reported_at=None, source="github"):
    return SeenRecord(
        source=source, source_id=source_id, title="t", url="u",
        signal_name="stars", signal_value=value, peak_signal=peak,
        prior_value=value, velocity=0.0,
        first_seen="2026-07-01T00:00:00+00:00",
        last_seen="2026-07-07T00:00:00+00:00", reported_at=reported_at,
    )


class TestFirstSight(unittest.TestCase):
    def test_creates_record_and_uses_rate_velocity(self):
        c = cand(value=500, created_days_ago=10)
        state = {}
        ingest([c], state, NOW)
        self.assertTrue(c.is_new)
        self.assertFalse(c.resurfaced)
        self.assertEqual(c.velocity, 50.0)  # 500 stars / 10 days
        rec = state["github:omni"]
        self.assertEqual(rec.peak_signal, 500)
        self.assertIsNone(rec.reported_at)


class TestSubsequentRun(unittest.TestCase):
    def test_velocity_is_delta_since_last_run(self):
        c = cand(value=150)
        state = {"github:omni": record(value=100, peak=100)}
        ingest([c], state, NOW)
        self.assertFalse(c.is_new)
        self.assertEqual(c.velocity, 50.0)  # 150 - 100
        rec = state["github:omni"]
        self.assertEqual(rec.prior_value, 100)
        self.assertEqual(rec.signal_value, 150)
        self.assertEqual(rec.peak_signal, 150)
        self.assertEqual(rec.last_seen, NOW.isoformat())

    def test_peak_holds_when_signal_dips(self):
        c = cand(value=150)
        state = {"github:omni": record(value=300, peak=300)}
        ingest([c], state, NOW)
        self.assertEqual(state["github:omni"].peak_signal, 300)


class TestResurface(unittest.TestCase):
    def test_reported_item_resurfaces_on_2x_prior_peak(self):
        c = cand(value=250)
        state = {"github:omni": record(value=100, peak=100, reported_at="2026-07-06T00:00:00+00:00")}
        ingest([c], state, NOW)
        self.assertTrue(c.resurfaced)  # 250 >= 2 * 100

    def test_reported_item_below_2x_does_not_resurface(self):
        c = cand(value=150)
        state = {"github:omni": record(value=100, peak=100, reported_at="2026-07-06T00:00:00+00:00")}
        ingest([c], state, NOW)
        self.assertFalse(c.resurfaced)  # 150 < 2 * 100

    def test_never_reported_item_is_not_resurfaced(self):
        c = cand(value=250)
        state = {"github:omni": record(value=100, peak=100, reported_at=None)}
        ingest([c], state, NOW)
        self.assertFalse(c.resurfaced)


if __name__ == "__main__":
    unittest.main()
