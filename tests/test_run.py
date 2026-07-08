import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import run
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


def repo(name, stars, summary="a multi-agent framework"):
    return Candidate(
        source="github", source_id=name, title=name,
        url=f"https://github.com/{name}", signal_name="stars",
        signal_value=stars, created_at=NOW - timedelta(days=10), summary=summary,
    )


def paths(tmp):
    return {
        "output_path": Path(tmp) / "dashboard.html",
        "state_path": Path(tmp) / "state.json",
        "runs_path": Path(tmp) / "runs.json",
    }


def run_with(tmp, hn_result, gh_result, now=NOW):
    with mock.patch("run.hackernews.fetch", return_value=hn_result), \
         mock.patch("run.github.fetch", return_value=gh_result):
        return run.main(now=now, **paths(tmp))


class TestMain(unittest.TestCase):
    def test_writes_dashboard_state_and_runs_log(self):
        hn_ok = FetchResult("hackernews", "ok", [hn("New LLM agent", 400, "1"),
                                                 hn("Sourdough recipe", 300, "2")])
        gh_ok = FetchResult("github", "ok", [repo("acme/agent-lib", 900)])
        with TemporaryDirectory() as tmp:
            p = paths(tmp)
            summary = run_with(tmp, hn_ok, gh_ok)
            html = p["output_path"].read_text()
            self.assertIn("New LLM agent", html)
            self.assertIn("acme/agent-lib", html)
            self.assertNotIn("Sourdough", html)          # dropped by relevance
            self.assertTrue(p["state_path"].exists())
            self.assertTrue(p["runs_path"].exists())
            log = json.loads(p["runs_path"].read_text())
            self.assertEqual(len(log), 1)
            self.assertEqual(log[0]["feeds"], {"hackernews": "ok", "github": "ok"})
            self.assertEqual(log[0]["counts"]["published"], 2)
        self.assertIn("published=2", summary)

    def test_failed_feed_still_publishes_the_healthy_one(self):
        hn_ok = FetchResult("hackernews", "ok", [hn("New agent tool", 400, "1")])
        gh_bad = FetchResult("github", "failed", [], error="boom")
        with TemporaryDirectory() as tmp:
            p = paths(tmp)
            summary = run_with(tmp, hn_ok, gh_bad)
            html = p["output_path"].read_text()
            self.assertIn("New agent tool", html)        # healthy feed published
            self.assertIn("boom", html)                  # banner names the failure
        self.assertIn("github=failed", summary)


class TestMemoryAcrossRuns(unittest.TestCase):
    def test_second_run_suppresses_repeat_and_resurfaces_a_jumper(self):
        with TemporaryDirectory() as tmp:
            p = paths(tmp)
            # Run 1: both published, reported_at stamped.
            run_with(tmp,
                     FetchResult("hackernews", "ok", [hn("New agent framework", 200, "1")]),
                     FetchResult("github", "ok", [repo("acme/agent-lib", 500)]))
            # Run 2: HN drifts (200 -> 250, < 2x) => suppressed.
            #        GitHub doubles (500 -> 1000, >= 2x peak) => resurfaces.
            run_with(tmp,
                     FetchResult("hackernews", "ok", [hn("New agent framework", 250, "1")]),
                     FetchResult("github", "ok", [repo("acme/agent-lib", 1000)]),
                     now=NOW + timedelta(days=1))
            html = p["output_path"].read_text()
            self.assertNotIn("New agent framework", html)   # suppressed repeat
            self.assertIn("acme/agent-lib", html)           # resurfaced
            self.assertRegex(html.lower(), r"\bback\b")

            log = json.loads(p["runs_path"].read_text())
            self.assertEqual(len(log), 2)
            self.assertEqual(log[1]["counts"]["suppressed"], 1)
            self.assertEqual(log[1]["counts"]["resurfaced"], 1)


if __name__ == "__main__":
    unittest.main()
