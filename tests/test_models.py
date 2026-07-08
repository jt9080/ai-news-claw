import unittest
from datetime import datetime, timezone

from newsclaw.models import Candidate, SeenRecord, Run, FetchResult, DigestItem


class TestCandidate(unittest.TestCase):
    def test_generalized_signal_fields(self):
        c = Candidate(
            source="github",
            source_id="omnigent-ai/omnigent",
            title="Omnigent",
            url="https://github.com/omnigent-ai/omnigent",
            signal_name="stars",
            signal_value=6653,
            created_at=datetime(2026, 6, 14, tzinfo=timezone.utc),
        )
        self.assertEqual(c.signal_name, "stars")
        self.assertEqual(c.signal_value, 6653)

    def test_optional_fields_default_sensibly(self):
        c = Candidate(
            source="github", source_id="x", title="t", url="u",
            signal_name="stars", signal_value=1,
            created_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
        )
        self.assertIsNone(c.discussion_url)
        self.assertIsNone(c.num_comments)
        self.assertEqual(c.topics, [])
        # run-derived annotations set by ingest, safe defaults before then
        self.assertEqual(c.velocity, 0.0)
        self.assertFalse(c.resurfaced)
        self.assertTrue(c.is_new)


class TestSeenRecord(unittest.TestCase):
    def test_round_trips_through_dict(self):
        rec = SeenRecord(
            source="hackernews", source_id="42",
            title="t", url="u", signal_name="points",
            signal_value=200, peak_signal=200, prior_value=150,
            velocity=50.0, first_seen="2026-07-07T00:00:00+00:00",
            last_seen="2026-07-08T00:00:00+00:00", reported_at=None,
        )
        as_dict = rec.to_dict()
        self.assertEqual(as_dict["signal_value"], 200)
        restored = SeenRecord.from_dict(as_dict)
        self.assertEqual(restored, rec)


class TestRun(unittest.TestCase):
    def test_round_trips_through_dict(self):
        run = Run(
            run_at="2026-07-08T00:00:00+00:00",
            window={"start": "a", "end": "b"},
            feeds={"hackernews": "ok", "github": "failed"},
            counts={"candidates": 10, "kept": 4, "new": 2,
                    "resurfaced": 1, "suppressed": 1, "published": 3},
            state="ok",
        )
        restored = Run.from_dict(run.to_dict())
        self.assertEqual(restored, run)


class TestDigestItem(unittest.TestCase):
    def _cand(self, source="github"):
        c = Candidate(
            source=source, source_id="omni", title="Omni", url="u",
            signal_name="stars", signal_value=10,
            created_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
            topics=["agent"],
        )
        c.resurfaced, c.is_new = False, True
        return c

    def test_from_candidate_wraps_with_empty_text_fields(self):
        item = DigestItem.from_candidate(self._cand("github"))
        self.assertEqual(item.what, "")
        self.assertEqual(item.why, "")
        self.assertEqual(item.for_builders, "")
        self.assertEqual(item.kind, "repo")
        self.assertEqual(item.title, "Omni")
        self.assertEqual(item.sources, [self._cand("github")])

    def test_from_candidate_kind_for_hn_is_post(self):
        item = DigestItem.from_candidate(self._cand("hackernews"))
        self.assertEqual(item.kind, "post")


class TestFetchResult(unittest.TestCase):
    def test_still_has_source_status_candidates(self):
        r = FetchResult(source="github", status="ok")
        self.assertEqual(r.candidates, [])
        self.assertIsNone(r.error)


if __name__ == "__main__":
    unittest.main()
