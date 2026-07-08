import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import run
from newsclaw.llm import LLMError
from newsclaw.models import Candidate, FetchResult

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def hn(title, points, source_id):
    return Candidate(
        source="hackernews", source_id=source_id, title=title,
        url=f"https://example.com/{source_id}", signal_name="points",
        signal_value=points, created_at=NOW,
        discussion_url=f"https://news.ycombinator.com/item?id={source_id}",
        num_comments=10,
    )


def repo(name, stars):
    return Candidate(
        source="github", source_id=name, title=name,
        url=f"https://github.com/{name}", signal_name="stars",
        signal_value=stars, created_at=NOW - timedelta(days=10),
        summary="a multi-agent framework",
    )


def paths(tmp):
    return {"output_path": Path(tmp) / "dashboard.html",
            "state_path": Path(tmp) / "state.json",
            "runs_path": Path(tmp) / "runs.json"}


def judged_reply(ids, why="because it matters"):
    return json.dumps({"items": [
        {"ids": ids, "title": "Judged story", "url": "https://example.com/1",
         "kind": "post", "topics": ["agent"], "why": why, "resurfaced": False}
    ]})


class TestJudgePath(unittest.TestCase):
    def test_judge_success_renders_why_and_records_ok(self):
        hn_ok = FetchResult("hackernews", "ok", [hn("New agent framework", 400, "1")])
        gh_ok = FetchResult("github", "ok", [repo("acme/agent-lib", 900)])
        with TemporaryDirectory() as tmp:
            p = paths(tmp)
            with mock.patch("run.hackernews.fetch", return_value=hn_ok), \
                 mock.patch("run.github.fetch", return_value=gh_ok), \
                 mock.patch("newsclaw.llm.complete", return_value=judged_reply(["hn:1"])):
                summary = run.main(now=NOW, **p)
            html = p["output_path"].read_text()
            self.assertIn("because it matters", html)          # the why line
            self.assertIn("Judged story", html)
            self.assertIn("judge", summary)
            log = json.loads(p["runs_path"].read_text())
            self.assertEqual(log[0]["feeds"]["judge"], "ok")
            # reported_at stamped on the published candidate
            st = json.loads(p["state_path"].read_text())
            self.assertIsNotNone(st["records"]["hackernews:1"]["reported_at"])


class TestFallbackPath(unittest.TestCase):
    def test_judge_failure_falls_back_to_standin_with_banner(self):
        hn_ok = FetchResult("hackernews", "ok", [hn("New agent tool", 400, "1")])
        gh_ok = FetchResult("github", "ok", [repo("acme/agent-lib", 900)])
        with TemporaryDirectory() as tmp:
            p = paths(tmp)
            with mock.patch("run.hackernews.fetch", return_value=hn_ok), \
                 mock.patch("run.github.fetch", return_value=gh_ok), \
                 mock.patch("newsclaw.llm.complete", side_effect=LLMError("boom")):
                summary = run.main(now=NOW, **p)
            html = p["output_path"].read_text()
            self.assertIn("New agent tool", html)              # stand-in still published
            self.assertRegex(html.lower(), r"judge unavailable|stand-in")
            log = json.loads(p["runs_path"].read_text())
            self.assertEqual(log[0]["feeds"]["judge"], "failed")
        self.assertIn("judge=failed", summary)

    def test_no_key_degrades_to_standin(self):
        # No OPENCODE_API_KEY set and llm not mocked: llm raises LLMError itself.
        hn_ok = FetchResult("hackernews", "ok", [hn("New agent tool", 400, "1")])
        gh_ok = FetchResult("github", "ok", [])
        with TemporaryDirectory() as tmp:
            p = paths(tmp)
            with mock.patch.dict("os.environ", {}, clear=True), \
                 mock.patch("run.hackernews.fetch", return_value=hn_ok), \
                 mock.patch("run.github.fetch", return_value=gh_ok):
                run.main(now=NOW, **p)
            html = p["output_path"].read_text()
            self.assertIn("New agent tool", html)
            log = json.loads(p["runs_path"].read_text())
            self.assertEqual(log[0]["feeds"]["judge"], "failed")


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
        run._load_dotenv(Path("/nonexistent/does-not-exist.env"))  # must not raise


if __name__ == "__main__":
    unittest.main()
