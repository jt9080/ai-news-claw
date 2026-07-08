import io
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from newsclaw import reddit
from newsclaw.reddit import fetch, to_candidates
from newsclaw.feedparse import parse

FIX = Path(__file__).parent / "fixtures" / "reddit_atom.xml"
START = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def cm(body: bytes):
    m = mock.MagicMock()
    m.__enter__.return_value = io.BytesIO(body)
    m.__exit__.return_value = False
    return m


class TestToCandidates(unittest.TestCase):
    def test_entry_maps_to_top_zero_signal(self):
        cands = to_candidates(parse(FIX.read_bytes()), START, END)
        self.assertEqual(len(cands), 1)
        c = cands[0]
        self.assertEqual(c.source, "reddit")
        self.assertEqual(c.source_id, "abc123")  # extracted comment id
        self.assertEqual(c.signal_name, "top")
        self.assertEqual(c.signal_value, 0)
        self.assertIn("multi-agent", c.title)
        self.assertEqual(c.discussion_url, c.url)


class TestFetch(unittest.TestCase):
    def test_aggregates_all_subs(self):
        with mock.patch("newsclaw.reddit.time.sleep"), \
             mock.patch("newsclaw.reddit.urlopen",
                        side_effect=[cm(FIX.read_bytes()) for _ in reddit.SUBREDDITS]):
            result = fetch(START, END)
        self.assertEqual(result.source, "reddit")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), len(reddit.SUBREDDITS))

    def test_one_sub_down_still_ok(self):
        side = [cm(FIX.read_bytes()), URLError("429"), cm(FIX.read_bytes())]
        with mock.patch("newsclaw.reddit.time.sleep"), \
             mock.patch("newsclaw.reddit.urlopen", side_effect=side):
            result = fetch(START, END)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), 2)  # 2 of 3 subs

    def test_all_subs_down_degrades(self):
        with mock.patch("newsclaw.reddit.time.sleep"), \
             mock.patch("newsclaw.reddit.urlopen", side_effect=URLError("429")):
            result = fetch(START, END)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
