import unittest
from datetime import datetime, timedelta, timezone

from newsclaw.models import Candidate, DigestItem, FetchResult
from newsclaw.render import render_dashboard, relative_age

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
WINDOW = (NOW - timedelta(hours=24), NOW)


def hn_c(title="New LLM agent", points=400, comments=120, topics=None,
         hours_ago=3, url="https://example.com/x", velocity=0.0):
    c = Candidate(
        source="hackernews", source_id="42", title=title, url=url,
        signal_name="points", signal_value=points,
        created_at=NOW - timedelta(hours=hours_ago),
        discussion_url="https://news.ycombinator.com/item?id=42",
        num_comments=comments, topics=topics or ["agent", "llm"],
    )
    c.is_new, c.resurfaced, c.velocity = True, False, velocity
    return c


def zero_c(source="blogs", signal_name="editorial", title="Lab ships agent SDK"):
    c = Candidate(
        source=source, source_id="x1", title=title, url="https://lab.example/post",
        signal_name=signal_name, signal_value=0,
        created_at=NOW - timedelta(hours=2), topics=["agent"],
    )
    c.is_new, c.resurfaced, c.velocity = True, False, 0.0
    return c


def gh_c(name="omnigent-ai/omnigent", stars=6653, velocity=120.0):
    c = Candidate(
        source="github", source_id=name, title=name,
        url="https://github.com/" + name, signal_name="stars",
        signal_value=stars, created_at=NOW - timedelta(days=10), topics=["agent"],
    )
    c.is_new, c.resurfaced, c.velocity = True, False, velocity
    return c


def item(sources, what="", why="", for_builders="", kind="post", topics=None,
         resurfaced=False, is_new=True):
    return DigestItem(
        title=sources[0].title, url=sources[0].url, what=what, why=why,
        for_builders=for_builders, kind=kind, topics=topics or ["agent"],
        resurfaced=resurfaced, is_new=is_new, sources=sources,
    )


def feeds(hn_status="ok", gh_status="ok", gh_error=None):
    return [
        FetchResult(source="hackernews", status=hn_status),
        FetchResult(source="github", status=gh_status, error=gh_error),
    ]


class TestRelativeAge(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(relative_age(NOW - timedelta(hours=3), NOW), "3h ago")

    def test_days(self):
        self.assertEqual(relative_age(NOW - timedelta(days=2), NOW), "2d ago")


class TestCards(unittest.TestCase):
    def test_shows_what_why_for_builders_with_labels(self):
        html = render_dashboard([item(
            [hn_c()], what="a new agent framework shipped",
            why="it standardizes orchestration",
            for_builders="swap agents without rewriting glue")],
            WINDOW, feeds(), NOW)
        self.assertIn("a new agent framework shipped", html)
        self.assertIn("it standardizes orchestration", html)
        self.assertIn("swap agents without rewriting glue", html)
        low = html.lower()
        self.assertRegex(low, r"why")
        self.assertRegex(low, r"builder")

    def test_omits_empty_text_fields(self):
        # a fallback item (no LLM text) shows neither why nor for-builders labels
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertNotRegex(html, r"For builders")

    def test_shows_kind(self):
        html = render_dashboard([item([gh_c()], kind="repo")], WINDOW, feeds(), NOW)
        self.assertRegex(html.lower(), r"repo")

    def test_hn_card_shows_points_comments_and_discussion(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertIn("400", html)
        self.assertIn("120", html)
        self.assertIn("https://news.ycombinator.com/item?id=42", html)

    def test_github_card_shows_stars_no_comments(self):
        html = render_dashboard([item([gh_c()], kind="repo")], WINDOW, feeds(), NOW)
        self.assertIn("6653", html)
        self.assertNotIn("comments", html)

    def test_clustered_item_shows_both_source_badges(self):
        html = render_dashboard([item([hn_c(), gh_c()])], WINDOW, feeds(), NOW)
        self.assertRegex(html, r">\s*HN\s*<")
        self.assertRegex(html.lower(), r">\s*github\s*<")

    def test_back_tag_for_resurfaced(self):
        html = render_dashboard([item([hn_c()], resurfaced=True, is_new=False)],
                                WINDOW, feeds(), NOW)
        self.assertRegex(html.lower(), r"\bback\b")

    def test_zero_signal_feed_shows_label_not_zero(self):
        html = render_dashboard([item([zero_c(source="blogs", signal_name="editorial")],
                                      kind="post", what="a release")], WINDOW, feeds(), NOW)
        self.assertNotRegex(html, r"0\s+editorial")   # no meaningless "0 editorial"
        self.assertIn("editorial", html)              # the label still shows

    def test_new_source_badges(self):
        for src, badge in [("arxiv", "arXiv"), ("reddit", "Reddit"), ("blogs", "Blog")]:
            html = render_dashboard([item([zero_c(source=src)], what="x")], WINDOW, feeds(), NOW)
            self.assertRegex(html, badge)

    def test_velocity_marker_when_positive(self):
        html = render_dashboard([item([gh_c(velocity=250.0)], kind="repo")],
                                WINDOW, feeds(), NOW)
        self.assertIn("250", html)

    def test_escapes_html_in_text_fields(self):
        html = render_dashboard(
            [item([hn_c(title="<script>x</script>")], what="<i>w</i>",
                  why="<b>bad</b>", for_builders="<u>fb</u>")],
            WINDOW, feeds(), NOW)
        self.assertNotIn("<script>x", html)
        self.assertNotIn("<b>bad</b>", html)
        self.assertNotIn("<i>w</i>", html)
        self.assertIn("&lt;script&gt;", html)


class TestHealthAndBanners(unittest.TestCase):
    def test_health_line_names_both_feeds(self):
        html = render_dashboard([], WINDOW, feeds(), NOW)
        self.assertRegex(html.lower(), r"hacker news")
        self.assertRegex(html.lower(), r"github")

    def test_feed_failure_banner(self):
        html = render_dashboard([], WINDOW,
                                feeds(gh_status="failed", gh_error="boom"), NOW)
        self.assertIn("boom", html)

    def test_judge_unavailable_banner_when_flagged(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW,
                                judge_failed=True)
        self.assertRegex(html.lower(), r"judge|stand-in|fallback")

    def test_no_judge_banner_when_ok(self):
        html = render_dashboard([item([hn_c()], why="x")], WINDOW, feeds(), NOW)
        self.assertNotRegex(html.lower(), r"judge unavailable|stand-in")

    def test_empty_state_when_no_items(self):
        html = render_dashboard([], WINDOW, feeds(), NOW)
        self.assertRegex(html.lower(), r"nothing|quiet")

    def test_header_and_doctype(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertIn("The Morning Claw", html)
        self.assertTrue(html.strip().lower().startswith("<!doctype html>"))


class TestNewspaperChrome(unittest.TestCase):
    def test_masthead_and_dateline(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertIn("The Morning Claw", html)
        self.assertRegex(html.lower(), r"morning edition")

    def test_rail_lists_feeds_with_logos(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertRegex(html.lower(), r"wire services")
        # every feed row carries an inline SVG mark
        self.assertGreaterEqual(html.count("<svg"), len(feeds()))

    def test_source_chip_carries_logo(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertRegex(html, r'<svg[^>]*>.*?</svg>\s*HN')

    def test_hero_treatment_for_first_story_only(self):
        html = render_dashboard(
            [item([hn_c()], what="lead"), item([gh_c()], kind="repo", what="second")],
            WINDOW, feeds(), NOW)
        self.assertEqual(html.count('class="story hero"'), 1)
        self.assertLess(html.index('class="story hero"'),
                        html.index("second"))

    def test_lead_story_labelled_others_unnumbered(self):
        html = render_dashboard(
            [item([hn_c()]), item([gh_c()], kind="repo")], WINDOW, feeds(), NOW)
        self.assertEqual(html.count("Lead story"), 1)
        self.assertNotRegex(html, r"No\.\s*\d")

    def test_no_new_tag_but_back_survives(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertNotIn(">new<", html.replace(" ", ""))

    def test_masthead_carries_claw_emblem_and_favicon(self):
        html = render_dashboard([item([hn_c()])], WINDOW, feeds(), NOW)
        self.assertIn('class="mastlogo"', html)
        self.assertIn('rel="icon"', html)

    def test_fleuron_separates_stories(self):
        html = render_dashboard(
            [item([hn_c()]), item([gh_c()], kind="repo")], WINDOW, feeds(), NOW)
        self.assertIn("2766", html)  # ❦ printer's ornament in the story divider


if __name__ == "__main__":
    unittest.main()
