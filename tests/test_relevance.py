import unittest
from datetime import datetime, timezone

from newsclaw.models import Candidate
from newsclaw.relevance import find_topics, filter_relevant


def make(title, url="https://example.com/x"):
    return Candidate(
        source="hackernews",
        source_id="1",
        title=title,
        url=url,
        hn_url="https://news.ycombinator.com/item?id=1",
        points=200,
        num_comments=10,
        created_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
    )


class TestFindTopics(unittest.TestCase):
    def test_matches_ai_terms_in_title(self):
        topics = find_topics("New LLM agent framework from Anthropic", "")
        self.assertIn("llm", topics)
        self.assertIn("agent", topics)
        self.assertIn("anthropic", topics)

    def test_case_insensitive(self):
        self.assertIn("gpt", find_topics("GPT-5 released", ""))

    def test_non_ai_title_matches_nothing(self):
        self.assertEqual(find_topics("A new sourdough bread recipe", ""), [])

    def test_short_terms_require_word_boundary(self):
        # "rag" must not match inside "storage"; "ai" not inside "certain"
        self.assertEqual(find_topics("Certain storage improvements", ""), [])

    def test_skilled_workers_is_not_an_ai_skill(self):
        # regression: "skill" must not admit "skilled" (a German labour story
        # slipped into a live run this way)
        self.assertEqual(find_topics("Why skilled workers come to Germany", ""), [])

    def test_matches_term_in_url(self):
        self.assertIn("huggingface", find_topics("Cool release", "https://huggingface.co/models"))

    def test_topics_are_unique_and_sorted(self):
        topics = find_topics("agent agent LLM", "")
        self.assertEqual(topics, sorted(set(topics)))


class TestFilterRelevant(unittest.TestCase):
    def test_keeps_relevant_and_sets_topics(self):
        kept = filter_relevant([make("New LLM agent"), make("Sourdough bread")])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].title, "New LLM agent")
        self.assertIn("llm", kept[0].topics)

    def test_drops_all_when_none_relevant(self):
        self.assertEqual(filter_relevant([make("Sourdough bread")]), [])


if __name__ == "__main__":
    unittest.main()
