import io
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from newsclaw import blogs
from newsclaw.blogs import fetch, to_candidates
from newsclaw.feedparse import parse

FIX = Path(__file__).parent / "fixtures" / "blog_rss.xml"
START = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def cm(body: bytes):
    m = mock.MagicMock()
    m.__enter__.return_value = io.BytesIO(body)
    m.__exit__.return_value = False
    return m


class TestToCandidates(unittest.TestCase):
    def test_editorial_zero_signal_and_window_filter(self):
        cands = to_candidates(parse(FIX.read_bytes()), START, END)
        self.assertEqual(len(cands), 1)  # picnic (June) filtered out
        c = cands[0]
        self.assertEqual(c.source, "blogs")
        self.assertEqual(c.url, "https://openai.com/blog/agent-sdk")
        self.assertEqual(c.source_id, "https://openai.com/blog/agent-sdk")
        self.assertEqual(c.signal_name, "editorial")
        self.assertEqual(c.signal_value, 0)
        self.assertIn("agent SDK", c.title)


class TestFetch(unittest.TestCase):
    def test_aggregates_all_sources(self):
        with mock.patch("newsclaw.blogs.urlopen",
                        side_effect=[cm(FIX.read_bytes()) for _ in blogs.SOURCES]):
            result = fetch(START, END)
        self.assertEqual(result.source, "blogs")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), len(blogs.SOURCES))  # 1 in-window each

    def test_one_source_down_still_ok(self):
        side = [cm(FIX.read_bytes()) for _ in blogs.SOURCES]
        side[1] = URLError("down")
        with mock.patch("newsclaw.blogs.urlopen", side_effect=side):
            result = fetch(START, END)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), len(blogs.SOURCES) - 1)

    def test_all_sources_down_degrades(self):
        with mock.patch("newsclaw.blogs.urlopen", side_effect=URLError("down")):
            result = fetch(START, END)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
