from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.check_source_market_freshness import inspect


class SourceMarketFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 6, 15, 0, tzinfo=timezone.utc)

    def test_single_stale_outlier_is_allowed_within_ratio(self) -> None:
        rows = [
            {"symbol": f"FRESH{i}", "regularMarketTime": "2026-08-05"}
            for i in range(406)
        ]
        rows.append({"symbol": "EA", "regularMarketTime": "2026-08-04"})

        result = inspect(
            {"rows": rows},
            now=self.now,
            max_business_day_lag=1,
            min_coverage=0.80,
            max_stale_ratio=0.01,
        )

        self.assertEqual(result["status"], "fresh")
        self.assertEqual(result["stale_count"], 1)
        self.assertTrue(result["stale_within_tolerance"])
        self.assertEqual(result["stale_symbols"][0]["symbol"], "EA")

    def test_same_outlier_remains_failure_without_explicit_tolerance(self) -> None:
        result = inspect(
            {
                "rows": [
                    {"symbol": "FRESH", "regularMarketTime": "2026-08-05"},
                    {"symbol": "EA", "regularMarketTime": "2026-08-04"},
                ]
            },
            now=self.now,
            max_business_day_lag=1,
            min_coverage=0.80,
        )

        self.assertEqual(result["status"], "source_stale")
        self.assertFalse(result["stale_within_tolerance"])

    def test_excessive_stale_ratio_still_fails(self) -> None:
        result = inspect(
            {
                "rows": [
                    {"symbol": "FRESH1", "regularMarketTime": "2026-08-05"},
                    {"symbol": "FRESH2", "regularMarketTime": "2026-08-05"},
                    {"symbol": "STALE1", "regularMarketTime": "2026-08-04"},
                    {"symbol": "STALE2", "regularMarketTime": "2026-08-04"},
                ]
            },
            now=self.now,
            max_business_day_lag=1,
            min_coverage=0.80,
            max_stale_ratio=0.01,
        )

        self.assertEqual(result["status"], "source_stale")
        self.assertEqual(result["stale_count"], 2)
        self.assertFalse(result["stale_within_tolerance"])


if __name__ == "__main__":
    unittest.main()
