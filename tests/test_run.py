import json
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import run
from newsclaw.llm import LLMError
from newsclaw.models import Candidate, FetchResult

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
FEED_NAMES = ["hackernews", "github", "huggingface", "arxiv", "reddit", "blogs"]


def hn(title, points, source_id):
    return Candidate(
        source="hackernews", source_id=source_id, title=title,
        url=f"https://example.com/{source_id}", signal_name="points",
        signal_value=points, created_at=NOW,
        discussion_url=f"https://news.ycombinator.com/item?id={source_id}",
        num_comments=10,
    )


def paths(tmp):
    return {"output_path": Path(tmp) / "dashboard.html",
            "state_path": Path(tmp) / "state.json",
            "runs_path": Path(tmp) / "runs.json"}


def patch_feeds(stack, **results):
    """Patch every feed's fetch; unспecified feeds default to empty-ok."""
    for name in FEED_NAMES:
        res = results.get(name, FetchResult(name, "ok", []))
        stack.enter_context(mock.patch(f"run.{name}.fetch", return_value=res))


def judged_reply(ids):
    return json.dumps({"items": [
        {"ids": ids, "title": "Judged story", "url": "https://example.com/1",
         "kind": "post", "topics": ["agent"],
         "what": "a new thing shipped", "why": "because it matters",
         "for_builders": "wire it into your agent loop", "resurfaced": False}
    ]})


class TestSixFeeds(unittest.TestCase):
    def test_judge_success_records_all_feeds(self):
        hn_ok = FetchResult("hackernews", "ok", [hn("New agent framework", 400, "1")])
        with TemporaryDirectory() as tmp, ExitStack() as stack:
            p = paths(tmp)
            patch_feeds(stack, hackernews=hn_ok)
            stack.enter_context(mock.patch("newsclaw.llm.complete",
                                           return_value=judged_reply(["hn:1"])))
            run.main(now=NOW, **p)
            html = p["output_path"].read_text()
            self.assertIn("a new thing shipped", html)
            log = json.loads(p["runs_path"].read_text())
            feeds = log[0]["feeds"]
            for name in FEED_NAMES:
                self.assertIn(name, feeds)          # every feed's health recorded
            self.assertEqual(feeds["judge"], "ok")

    def test_one_feed_failed_still_publishes(self):
        hn_ok = FetchResult("hackernews", "ok", [hn("New agent tool", 400, "1")])
        arxiv_bad = FetchResult("arxiv", "failed", [], error="429")
        with TemporaryDirectory() as tmp, ExitStack() as stack:
            p = paths(tmp)
            patch_feeds(stack, hackernews=hn_ok, arxiv=arxiv_bad)
            stack.enter_context(mock.patch("newsclaw.llm.complete",
                                           return_value=judged_reply(["hn:1"])))
            run.main(now=NOW, **p)
            html = p["output_path"].read_text()
            self.assertIn("Judged story", html)
            self.assertIn("429", html)              # failed feed banner
            log = json.loads(p["runs_path"].read_text())
            self.assertEqual(log[0]["feeds"]["arxiv"], "failed")

    def test_fallback_when_judge_unavailable(self):
        hn_ok = FetchResult("hackernews", "ok", [hn("New agent tool", 400, "1")])
        with TemporaryDirectory() as tmp, ExitStack() as stack:
            p = paths(tmp)
            patch_feeds(stack, hackernews=hn_ok)
            stack.enter_context(mock.patch("newsclaw.llm.complete",
                                           side_effect=LLMError("boom")))
            summary = run.main(now=NOW, **p)
            html = p["output_path"].read_text()
            self.assertIn("New agent tool", html)
            self.assertRegex(html.lower(), r"judge unavailable|stand-in")
        self.assertIn("judge=failed", summary)

    def test_per_feed_cap_bounds_judge_input(self):
        many = FetchResult("hackernews", "ok",
                           [hn(f"agent story {i}", 500 - i, str(i)) for i in range(25)])
        captured = {}

        def spy(candidates, records, now):
            captured["n_hn"] = sum(1 for c in candidates if c.source == "hackernews")
            return []

        with TemporaryDirectory() as tmp, ExitStack() as stack:
            p = paths(tmp)
            patch_feeds(stack, hackernews=many)
            stack.enter_context(mock.patch("run.judge.judge", side_effect=spy))
            run.main(now=NOW, **p)
        self.assertLessEqual(captured["n_hn"], run.PER_FEED_CAP)
        self.assertEqual(captured["n_hn"], run.PER_FEED_CAP)  # 25 capped to the limit


class TestDotenv(unittest.TestCase):
    def test_sets_missing_keys_from_file(self):
        import os
        with TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("# a comment\nOPENCODE_API_KEY=sk-abc\nLLM_MODEL=foo\n\n")
            with mock.patch.dict("os.environ", {}, clear=True):
                run._load_dotenv(env)
                self.assertEqual(os.environ["OPENCODE_API_KEY"], "sk-abc")
                self.assertEqual(os.environ["LLM_MODEL"], "foo")

    def test_does_not_override_existing_env(self):
        import os
        with TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("OPENCODE_API_KEY=fromfile\n")
            with mock.patch.dict("os.environ", {"OPENCODE_API_KEY": "fromenv"}, clear=True):
                run._load_dotenv(env)
                self.assertEqual(os.environ["OPENCODE_API_KEY"], "fromenv")

    def test_missing_file_is_noop(self):
        run._load_dotenv(Path("/nonexistent/does-not-exist.env"))


if __name__ == "__main__":
    unittest.main()
