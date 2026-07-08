import io
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from newsclaw import arxiv
from newsclaw.arxiv import fetch, to_candidates
from newsclaw.feedparse import parse

FIX = Path(__file__).parent / "fixtures" / "arxiv_atom.xml"
START = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def entries():
    return parse(FIX.read_bytes())


class TestToCandidates(unittest.TestCase):
    def test_keeps_first_submission_in_window(self):
        cands = to_candidates(entries(), START, END)
        self.assertEqual(len(cands), 1)  # v3 revision + out-of-window dropped
        c = cands[0]
        self.assertEqual(c.source, "arxiv")
        self.assertEqual(c.source_id, "2607.04567")
        self.assertEqual(c.url, "https://arxiv.org/abs/2607.04567")  # https, no version
        self.assertEqual(c.signal_name, "recency")
        self.assertEqual(c.signal_value, 0)
        self.assertIn("Coordination", c.title)

    def test_revision_is_skipped(self):
        ids = [c.source_id for c in to_candidates(entries(), START, END)]
        self.assertNotIn("2601.00001", ids)

    def test_out_of_window_is_skipped(self):
        ids = [c.source_id for c in to_candidates(entries(), START, END)]
        self.assertNotIn("2606.09999", ids)


class TestFetch(unittest.TestCase):
    def test_success(self):
        with mock.patch("newsclaw.arxiv.urlopen") as m:
            m.return_value.__enter__.return_value = io.BytesIO(FIX.read_bytes())
            result = fetch(START, END)
        self.assertEqual(result.source, "arxiv")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), 1)

    def test_failure_degrades(self):
        with mock.patch("newsclaw.arxiv.urlopen", side_effect=URLError("429")):
            result = fetch(START, END)
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
