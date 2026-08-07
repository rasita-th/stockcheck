import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.resolve_live_refresh_mode import resolve_refresh_mode


class LiveRefreshModeTests(unittest.TestCase):
    def test_promotes_stale_market_hours_baseline_to_full_refresh(self):
        now = datetime(2026, 8, 7, 11, 34, tzinfo=ZoneInfo("America/New_York"))
        result = resolve_refresh_mode(
            now=now,
            event_name="schedule",
            event_schedule="*/15 * * * 1-5",
            requested_full=False,
            technical_payload={"generatedAtTechnical": "2026-08-07 01:05:57 UTC"},
        )
        self.assertTrue(result["market_open"])
        self.assertTrue(result["full_technical"])
        self.assertEqual(result["full_reason"], "stale_market_hours_baseline")

    def test_keeps_recent_market_hours_baseline_on_fast_refresh(self):
        now = datetime(2026, 8, 7, 11, 34, tzinfo=ZoneInfo("America/New_York"))
        result = resolve_refresh_mode(
            now=now,
            event_name="schedule",
            event_schedule="*/15 * * * 1-5",
            requested_full=False,
            technical_payload={"generatedAtTechnical": "2026-08-07 15:05:00 UTC"},
        )
        self.assertTrue(result["run_refresh"])
        self.assertFalse(result["full_technical"])
        self.assertEqual(result["full_reason"], "fast_quote_refresh")

    def test_missing_baseline_fails_safe_to_full_refresh_during_market_hours(self):
        now = datetime(2026, 8, 7, 11, 34, tzinfo=ZoneInfo("America/New_York"))
        result = resolve_refresh_mode(
            now=now,
            event_name="schedule",
            event_schedule="*/15 * * * 1-5",
            requested_full=False,
            technical_payload={},
        )
        self.assertTrue(result["full_technical"])

    def test_does_not_promote_stale_baseline_outside_market_hours(self):
        now = datetime(2026, 8, 7, 18, 0, tzinfo=ZoneInfo("America/New_York"))
        result = resolve_refresh_mode(
            now=now,
            event_name="schedule",
            event_schedule="*/15 * * * 1-5",
            requested_full=False,
            technical_payload={"generatedAtTechnical": "2026-08-07 01:05:57 UTC"},
        )
        self.assertFalse(result["run_refresh"])
        self.assertFalse(result["full_technical"])


if __name__ == "__main__":
    unittest.main()
