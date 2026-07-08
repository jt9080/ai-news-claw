import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import run
from newsclaw.models import Candidate, FetchResult

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def candidate(title, points, source_id):
    return Candidate(
        source="hackernews",
        source_id=source_id,
        title=title,
        url="https://example.com/x",
        hn_url=f"https://news.ycombinator.com/item?id={source_id}",
        points=points,
        num_comments=10,
        created_at=NOW,
    )


class TestMain(unittest.TestCase):
    def test_writes_dashboard_and_reports_counts(self):
        fetched = [
            candidate("New LLM agent framework", 400, "1"),
            candidate("A sourdough bread recipe", 300, "2"),  # not relevant -> dropped
        ]
        result = FetchResult(source="hackernews", status="ok", candidates=fetched)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "dashboard.html"
            with mock.patch("run.hackernews.fetch", return_value=result):
                summary = run.main(now=NOW, output_path=out)
            self.assertTrue(out.exists())
            html = out.read_text()
            self.assertIn("New LLM agent framework", html)
            self.assertNotIn("sourdough", html)
        # summary reports the funnel: fetched=2, kept=1, published=1
        self.assertIn("ok", summary)
        self.assertIn("fetched=2", summary)
        self.assertIn("published=1", summary)

    def test_failed_fetch_still_writes_dashboard(self):
        result = FetchResult(source="hackernews", status="failed", candidates=[], error="boom")
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "dashboard.html"
            with mock.patch("run.hackernews.fetch", return_value=result):
                summary = run.main(now=NOW, output_path=out)
            self.assertTrue(out.exists())
            self.assertIn("boom", out.read_text())
        self.assertIn("failed", summary)


if __name__ == "__main__":
    unittest.main()
