import unittest
from datetime import datetime, timezone

from newsclaw.models import Candidate
from newsclaw.rank import rank, MAX_ITEMS


def make(points, source_id="1"):
    return Candidate(
        source="hackernews",
        source_id=source_id,
        title=f"story {source_id}",
        url="https://example.com/x",
        hn_url="https://news.ycombinator.com/item?id=1",
        points=points,
        num_comments=0,
        created_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
    )


class TestRank(unittest.TestCase):
    def test_sorts_by_points_descending(self):
        ranked = rank([make(150, "a"), make(400, "b"), make(200, "c")])
        self.assertEqual([c.points for c in ranked], [400, 200, 150])

    def test_drops_items_at_or_below_threshold(self):
        # threshold is > 100; a 100-point item must be excluded
        ranked = rank([make(400, "a"), make(100, "b"), make(50, "c")])
        self.assertEqual([c.points for c in ranked], [400])

    def test_caps_at_max_items(self):
        many = [make(200 + i, str(i)) for i in range(20)]
        ranked = rank(many)
        self.assertEqual(len(ranked), MAX_ITEMS)

    def test_cap_keeps_the_highest(self):
        many = [make(200 + i, str(i)) for i in range(20)]
        ranked = rank(many)
        self.assertEqual(ranked[0].points, 219)
        self.assertEqual(ranked[-1].points, 219 - (MAX_ITEMS - 1))


if __name__ == "__main__":
    unittest.main()
