import io
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from newsclaw import huggingface
from newsclaw.huggingface import fetch, parse_models, parse_papers

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
START = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)


def cm(body: bytes):
    m = mock.MagicMock()
    m.__enter__.return_value = io.BytesIO(body)
    m.__exit__.return_value = False
    return m


def models_bytes():
    return (FIX / "hf_models.json").read_bytes()


def papers_bytes():
    return (FIX / "hf_papers.json").read_bytes()


class TestParse(unittest.TestCase):
    def test_models_map_to_likes_signal(self):
        cands = parse_models(json.loads(models_bytes()), NOW)
        self.assertEqual(len(cands), 3)  # 4th (no id) skipped
        first = cands[0]
        self.assertEqual(first.source, "huggingface")
        self.assertEqual(first.title, "zai-org/GLM-5.2")
        self.assertEqual(first.url, "https://huggingface.co/zai-org/GLM-5.2")
        self.assertEqual(first.signal_name, "likes")
        self.assertEqual(first.signal_value, 3596)

    def test_papers_map_to_upvotes_signal_and_arxiv_url(self):
        cands = parse_papers(json.loads(papers_bytes()), NOW)
        self.assertEqual(len(cands), 2)  # malformed skipped
        p = cands[0]
        self.assertEqual(p.signal_name, "upvotes")
        self.assertEqual(p.signal_value, 92)
        self.assertEqual(p.url, "https://arxiv.org/abs/2607.01234")  # clusters w/ arXiv
        self.assertIn("MuseBench", p.title)


class TestFetch(unittest.TestCase):
    def test_combines_models_and_papers(self):
        with mock.patch("newsclaw.huggingface.urlopen",
                        side_effect=[cm(models_bytes()), cm(papers_bytes())]):
            result = fetch(START, NOW)
        self.assertEqual(result.source, "huggingface")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), 5)  # 3 models + 2 papers

    def test_partial_failure_still_ok(self):
        with mock.patch("newsclaw.huggingface.urlopen",
                        side_effect=[cm(models_bytes()), URLError("papers down")]):
            result = fetch(START, NOW)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), 3)  # models only

    def test_both_endpoints_fail_degrades(self):
        with mock.patch("newsclaw.huggingface.urlopen", side_effect=URLError("boom")):
            result = fetch(START, NOW)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.candidates, [])
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
