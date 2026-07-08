import unittest
from datetime import datetime, timedelta, timezone

from newsclaw.models import Candidate, FetchResult
from newsclaw.render import render_dashboard, relative_age

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
WINDOW = (NOW - timedelta(hours=24), NOW)


def hn(title="New LLM agent", points=400, comments=120, topics=None,
       hours_ago=3, url="https://example.com/x", is_new=True, resurfaced=False,
       velocity=0.0):
    c = Candidate(
        source="hackernews", source_id="42", title=title, url=url,
        signal_name="points", signal_value=points,
        created_at=NOW - timedelta(hours=hours_ago),
        discussion_url="https://news.ycombinator.com/item?id=42",
        num_comments=comments, topics=topics or ["agent", "llm"],
    )
    c.is_new, c.resurfaced, c.velocity = is_new, resurfaced, velocity
    return c


def gh(name="omnigent-ai/omnigent", stars=6653, topics=None, velocity=120.0):
    c = Candidate(
        source="github", source_id=name, title=name,
        url="https://github.com/" + name,
        signal_name="stars", signal_value=stars,
        created_at=NOW - timedelta(days=10),
        topics=topics or ["agent"], velocity=velocity,
    )
    c.is_new = True
    return c


def feeds(hn_status="ok", gh_status="ok", hn_c=None, gh_c=None, gh_error=None):
    return [
        FetchResult(source="hackernews", status=hn_status, candidates=hn_c or []),
        FetchResult(source="github", status=gh_status, candidates=gh_c or [], error=gh_error),
    ]


class TestRelativeAge(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(relative_age(NOW - timedelta(hours=3), NOW), "3h ago")

    def test_days(self):
        self.assertEqual(relative_age(NOW - timedelta(days=2), NOW), "2d ago")


class TestCards(unittest.TestCase):
    def test_hn_card_shows_points_and_comments(self):
        html = render_dashboard([hn()], WINDOW, feeds(hn_c=[hn()]), NOW)
        self.assertIn("New LLM agent", html)
        self.assertIn("400", html)
        self.assertIn("120", html)

    def test_github_card_shows_stars_and_no_comments_link(self):
        html = render_dashboard([gh()], WINDOW, feeds(gh_c=[gh()]), NOW)
        self.assertIn("omnigent-ai/omnigent", html)
        self.assertIn("6653", html)
        self.assertNotIn("comments", html)
        self.assertNotIn("discussion", html)

    def test_source_badges_present(self):
        html = render_dashboard([hn(), gh()], WINDOW, feeds(hn_c=[hn()], gh_c=[gh()]), NOW)
        self.assertRegex(html, r">\s*HN\s*<")
        self.assertRegex(html.lower(), r">\s*github\s*<")

    def test_hn_has_both_links(self):
        html = render_dashboard([hn()], WINDOW, feeds(hn_c=[hn()]), NOW)
        self.assertIn("https://example.com/x", html)
        self.assertIn("https://news.ycombinator.com/item?id=42", html)

    def test_new_tag_for_first_sight(self):
        html = render_dashboard([hn(is_new=True)], WINDOW, feeds(hn_c=[hn()]), NOW)
        self.assertRegex(html.lower(), r"\bnew\b")

    def test_back_tag_for_resurfaced(self):
        html = render_dashboard([hn(is_new=False, resurfaced=True)], WINDOW, feeds(hn_c=[hn()]), NOW)
        self.assertRegex(html.lower(), r"\bback\b")

    def test_velocity_shown_when_positive(self):
        html = render_dashboard([gh(velocity=250.0)], WINDOW, feeds(gh_c=[gh()]), NOW)
        self.assertIn("250", html)

    def test_escapes_html_in_title(self):
        evil = hn(title="<script>alert('x')</script>")
        html = render_dashboard([evil], WINDOW, feeds(hn_c=[evil]), NOW)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_renders_topics(self):
        html = render_dashboard([hn(topics=["agent", "mcp"])], WINDOW, feeds(), NOW)
        self.assertIn("mcp", html)


class TestHealthAndBanner(unittest.TestCase):
    def test_health_line_names_both_feeds(self):
        html = render_dashboard([], WINDOW, feeds(), NOW)
        self.assertRegex(html.lower(), r"hacker news")
        self.assertRegex(html.lower(), r"github")

    def test_banner_when_one_feed_failed(self):
        html = render_dashboard([hn()], WINDOW,
                                feeds(gh_status="failed", gh_error="boom", hn_c=[hn()]), NOW)
        self.assertIn("boom", html)
        self.assertRegex(html.lower(), r"github")
        # the other feed's item still renders
        self.assertIn("New LLM agent", html)

    def test_no_banner_when_all_ok(self):
        html = render_dashboard([hn()], WINDOW, feeds(hn_c=[hn()]), NOW)
        self.assertNotRegex(html.lower(), r"unavailable")

    def test_empty_state_when_no_items_but_healthy(self):
        html = render_dashboard([], WINDOW, feeds(), NOW)
        self.assertRegex(html.lower(), r"nothing|no items|quiet")

    def test_header_and_doctype(self):
        html = render_dashboard([hn()], WINDOW, feeds(hn_c=[hn()]), NOW)
        self.assertIn("AI News Monitor", html)
        self.assertTrue(html.strip().lower().startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()
