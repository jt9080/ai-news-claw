import io
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from newsclaw.hackernews import fetch, parse_hits
from newsclaw.window import compute_window

FIXTURE = Path(__file__).parent / "fixtures" / "hn_search.json"


def load_fixture_bytes():
    return FIXTURE.read_bytes()


class TestParseHits(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text())

    def test_parses_a_normal_story(self):
        candidates = parse_hits(self.payload["hits"])
        first = candidates[0]
        self.assertEqual(first.source, "hackernews")
        self.assertEqual(first.source_id, "42150001")
        self.assertEqual(first.title, "GLM 5.2 and the coming AI margin collapse")
        self.assertEqual(first.url, "https://example.com/glm-5-2")
        self.assertEqual(first.points, 666)
        self.assertEqual(first.num_comments, 412)

    def test_hn_url_built_from_object_id(self):
        candidates = parse_hits(self.payload["hits"])
        self.assertEqual(
            candidates[0].hn_url,
            "https://news.ycombinator.com/item?id=42150001",
        )

    def test_created_at_is_utc_aware(self):
        candidates = parse_hits(self.payload["hits"])
        self.assertEqual(
            candidates[0].created_at,
            datetime(2026, 7, 6, 4, 40, 0, tzinfo=timezone.utc),
        )

    def test_text_post_url_falls_back_to_hn_url(self):
        candidates = parse_hits(self.payload["hits"])
        ask = next(c for c in candidates if c.source_id == "42150002")
        self.assertEqual(ask.url, ask.hn_url)

    def test_malformed_hit_is_skipped_not_fatal(self):
        candidates = parse_hits(self.payload["hits"])
        ids = [c.source_id for c in candidates]
        self.assertNotIn("42150003", ids)
        self.assertEqual(len(candidates), 2)


class TestFetch(unittest.TestCase):
    def test_successful_fetch_returns_ok_result(self):
        start, end = compute_window(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc))
        with mock.patch("newsclaw.hackernews.urlopen") as m:
            m.return_value.__enter__.return_value = io.BytesIO(load_fixture_bytes())
            result = fetch(start, end)
        self.assertEqual(result.source, "hackernews")
        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.error)
        self.assertEqual(len(result.candidates), 2)

    def test_network_error_returns_failed_result(self):
        start, end = compute_window(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc))
        with mock.patch("newsclaw.hackernews.urlopen", side_effect=URLError("boom")):
            result = fetch(start, end)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.candidates, [])
        self.assertIsNotNone(result.error)

    def test_malformed_json_returns_failed_result(self):
        start, end = compute_window(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc))
        with mock.patch("newsclaw.hackernews.urlopen") as m:
            m.return_value.__enter__.return_value = io.BytesIO(b"not json{{{")
            result = fetch(start, end)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
