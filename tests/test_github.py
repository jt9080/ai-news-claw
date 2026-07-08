import io
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from newsclaw.github import fetch, parse_items
from newsclaw.window import compute_window

FIXTURE = Path(__file__).parent / "fixtures" / "github_search.json"


def load_fixture_bytes():
    return FIXTURE.read_bytes()


class TestParseItems(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text())

    def test_parses_a_repo_into_a_candidate(self):
        cands = parse_items(self.payload["items"])
        first = cands[0]
        self.assertEqual(first.source, "github")
        self.assertEqual(first.source_id, "omnigent-ai/omnigent")
        self.assertEqual(first.title, "omnigent-ai/omnigent")
        self.assertEqual(first.url, "https://github.com/omnigent-ai/omnigent")
        self.assertEqual(first.signal_name, "stars")
        self.assertEqual(first.signal_value, 6653)
        self.assertEqual(first.summary, "Omnigent is an open-source multi-agent framework")

    def test_created_at_is_utc_aware(self):
        cands = parse_items(self.payload["items"])
        self.assertEqual(
            cands[0].created_at,
            datetime(2026, 6, 14, 9, 12, 0, tzinfo=timezone.utc),
        )

    def test_repo_has_no_discussion_url_or_comments(self):
        cands = parse_items(self.payload["items"])
        self.assertIsNone(cands[0].discussion_url)
        self.assertIsNone(cands[0].num_comments)

    def test_null_description_becomes_none_summary(self):
        cands = parse_items(self.payload["items"])
        quiet = next(c for c in cands if c.source_id == "acme/quiet-tool")
        self.assertIsNone(quiet.summary)

    def test_malformed_item_is_skipped_not_fatal(self):
        cands = parse_items(self.payload["items"])
        ids = [c.source_id for c in cands]
        self.assertNotIn("broken/norepo", ids)
        self.assertEqual(len(cands), 2)


class TestFetch(unittest.TestCase):
    def test_successful_fetch_returns_ok_result(self):
        start, end = compute_window(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc))
        with mock.patch("newsclaw.github.urlopen") as m:
            m.return_value.__enter__.return_value = io.BytesIO(load_fixture_bytes())
            result = fetch(start, end)
        self.assertEqual(result.source, "github")
        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.error)
        self.assertEqual(len(result.candidates), 2)

    def test_network_error_returns_failed_result(self):
        start, end = compute_window(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc))
        with mock.patch("newsclaw.github.urlopen", side_effect=URLError("boom")):
            result = fetch(start, end)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.candidates, [])
        self.assertIsNotNone(result.error)

    def test_malformed_json_returns_failed_result(self):
        start, end = compute_window(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc))
        with mock.patch("newsclaw.github.urlopen") as m:
            m.return_value.__enter__.return_value = io.BytesIO(b"not json{{{")
            result = fetch(start, end)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
