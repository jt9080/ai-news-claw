import unittest
from datetime import datetime, timedelta, timezone

from newsclaw.models import Candidate, FetchResult
from newsclaw.render import render_dashboard, relative_age

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
WINDOW = (NOW - timedelta(hours=24), NOW)


def make(title="New LLM agent", points=400, comments=120, topics=None, hours_ago=3, url="https://example.com/x"):
    return Candidate(
        source="hackernews",
        source_id="42",
        title=title,
        url=url,
        hn_url="https://news.ycombinator.com/item?id=42",
        points=points,
        num_comments=comments,
        created_at=NOW - timedelta(hours=hours_ago),
        topics=topics or ["agent", "llm"],
    )


def ok(candidates):
    return FetchResult(source="hackernews", status="ok", candidates=candidates)


class TestRelativeAge(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(relative_age(NOW - timedelta(hours=3), NOW), "3h ago")

    def test_minutes(self):
        self.assertEqual(relative_age(NOW - timedelta(minutes=10), NOW), "10m ago")

    def test_just_now(self):
        self.assertEqual(relative_age(NOW - timedelta(seconds=5), NOW), "just now")


class TestRenderDashboard(unittest.TestCase):
    def test_contains_item_title_and_signal(self):
        html = render_dashboard([make()], WINDOW, ok([make()]), NOW)
        self.assertIn("New LLM agent", html)
        self.assertIn("400", html)   # points
        self.assertIn("120", html)   # comments

    def test_contains_both_links(self):
        html = render_dashboard([make()], WINDOW, ok([make()]), NOW)
        self.assertIn("https://example.com/x", html)
        self.assertIn("https://news.ycombinator.com/item?id=42", html)

    def test_renders_topics(self):
        html = render_dashboard([make(topics=["agent", "mcp"])], WINDOW, ok([]), NOW)
        self.assertIn("agent", html)
        self.assertIn("mcp", html)

    def test_escapes_html_in_title(self):
        evil = make(title="<script>alert('x')</script>")
        html = render_dashboard([evil], WINDOW, ok([evil]), NOW)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_failure_banner_when_feed_failed(self):
        failed = FetchResult(source="hackernews", status="failed", candidates=[], error="boom")
        html = render_dashboard([], WINDOW, failed, NOW)
        self.assertIn("boom", html)
        self.assertRegex(html.lower(), r"fail|error|unavailable")

    def test_no_failure_banner_when_ok(self):
        html = render_dashboard([make()], WINDOW, ok([make()]), NOW)
        self.assertNotRegex(html.lower(), r"feed unavailable|fetch failed")

    def test_empty_state_when_no_items_but_healthy(self):
        html = render_dashboard([], WINDOW, ok([]), NOW)
        self.assertRegex(html.lower(), r"nothing|no items|quiet")

    def test_header_present(self):
        html = render_dashboard([make()], WINDOW, ok([make()]), NOW)
        self.assertIn("AI News Monitor", html)
        self.assertTrue(html.strip().lower().startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()
