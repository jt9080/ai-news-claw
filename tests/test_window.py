import unittest
from datetime import datetime, timedelta, timezone

from newsclaw.window import compute_window


class TestComputeWindow(unittest.TestCase):
    def test_window_is_the_previous_utc_day(self):
        # A run just after midnight UTC reports the calendar day that just ended.
        now = datetime(2026, 7, 8, 0, 0, 30, tzinfo=timezone.utc)
        start, end = compute_window(now)
        self.assertEqual(end, datetime(2026, 7, 8, 0, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(start, datetime(2026, 7, 7, 0, 0, 0, tzinfo=timezone.utc))

    def test_end_is_start_of_current_utc_day_regardless_of_time(self):
        # Any time within a day floors to that day's 00:00 boundary.
        now = datetime(2026, 7, 8, 15, 42, 11, tzinfo=timezone.utc)
        start, end = compute_window(now)
        self.assertEqual(end, datetime(2026, 7, 8, 0, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(start, datetime(2026, 7, 7, 0, 0, 0, tzinfo=timezone.utc))

    def test_span_is_24_hours(self):
        now = datetime(2026, 7, 8, 9, 0, 0, tzinfo=timezone.utc)
        start, end = compute_window(now)
        self.assertEqual(end - start, timedelta(hours=24))

    def test_bounds_are_timezone_aware_utc(self):
        start, end = compute_window(datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(start.tzinfo, timezone.utc)
        self.assertEqual(end.tzinfo, timezone.utc)

    def test_defaults_to_now_and_produces_a_past_day(self):
        start, end = compute_window()
        self.assertLess(start, end)
        self.assertLessEqual(end, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
