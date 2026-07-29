from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.check_source_market_freshness import inspect


class SourceMarketFreshnessTests(unittest.TestCase):
    def now(self):
        return datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)

    def test_previous_business_day_is_fresh(self):
        payload = {"rows": [{"symbol": "NVDA", "regularMarketTime": "2026-07-28T20:00:00Z"}]}
        result = inspect(payload, now=self.now(), max_business_day_lag=1, min_coverage=0.8)
        self.assertEqual(result["status"], "fresh")

    def test_two_business_days_old_is_stale(self):
        payload = {"rows": [{"symbol": "NVDA", "regularMarketTime": "2026-07-27T20:00:00Z"}]}
        result = inspect(payload, now=self.now(), max_business_day_lag=1, min_coverage=0.8)
        self.assertEqual(result["status"], "source_stale")
        self.assertEqual(result["stale_count"], 1)

    def test_weekend_does_not_add_business_day_lag(self):
        now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
        payload = {"rows": [{"symbol": "NVDA", "regularMarketTime": "2026-07-31T20:00:00Z"}]}
        result = inspect(payload, now=now, max_business_day_lag=0, min_coverage=0.8)
        self.assertEqual(result["status"], "fresh")

    def test_low_timestamp_coverage_is_partial(self):
        payload = {"rows": [{"symbol": "NVDA"}, {"symbol": "TSLA", "date": "2026-07-29"}]}
        result = inspect(payload, now=self.now(), max_business_day_lag=1, min_coverage=0.8)
        self.assertEqual(result["status"], "source_partial")

    def test_generated_timestamp_is_not_used_as_market_timestamp(self):
        payload = {"generatedAt": "2026-07-29T18:00:00Z", "rows": [{"symbol": "NVDA"}]}
        result = inspect(payload, now=self.now(), max_business_day_lag=1, min_coverage=0.8)
        self.assertEqual(result["status"], "source_partial")


if __name__ == "__main__":
    unittest.main()
