import unittest
from datetime import datetime, timedelta, timezone

from newsclaw.window import compute_window


class TestComputeWindow(unittest.TestCase):
    def test_span_is_24_hours_ending_at_now(self):
        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
        start, end = compute_window(now)
        self.assertEqual(end, now)
        self.assertEqual(start, now - timedelta(hours=24))

    def test_start_before_end(self):
        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
        start, end = compute_window(now)
        self.assertLess(start, end)

    def test_bounds_are_timezone_aware_utc(self):
        now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
        start, end = compute_window(now)
        self.assertEqual(start.tzinfo, timezone.utc)
        self.assertEqual(end.tzinfo, timezone.utc)

    def test_defaults_to_current_utc_time(self):
        before = datetime.now(timezone.utc)
        start, end = compute_window()
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(end, before)
        self.assertLessEqual(end, after)


if __name__ == "__main__":
    unittest.main()
