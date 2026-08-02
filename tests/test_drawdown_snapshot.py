from __future__ import annotations

import unittest

from scripts.enrich_drawdown_snapshot import calculate_drawdown, enrich_payload


class DrawdownCalculationTests(unittest.TestCase):
    def test_rising_series_has_zero_drawdown(self):
        metric = calculate_drawdown([
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-01-02", "close": 11},
            {"date": "2026-01-03", "close": 12},
        ])
        self.assertEqual(metric["currentPct"], 0.0)
        self.assertEqual(metric["maxPct"], 0.0)
        self.assertEqual(metric["currentPeakDate"], "2026-01-03")

    def test_peak_trough_and_current_drawdown(self):
        metric = calculate_drawdown([
            {"date": "2026-01-01", "close": 100},
            {"date": "2026-01-02", "close": 120},
            {"date": "2026-01-03", "close": 90},
            {"date": "2026-01-04", "close": 108},
        ])
        self.assertEqual(metric["maxPct"], -25.0)
        self.assertEqual(metric["currentPct"], -10.0)
        self.assertEqual(metric["maxPeakDate"], "2026-01-02")
        self.assertEqual(metric["maxTroughDate"], "2026-01-03")
        self.assertEqual(metric["daysSincePeak"], 2)

    def test_live_price_replaces_latest_close(self):
        metric = calculate_drawdown(
            [
                {"date": "2026-01-01", "close": 100},
                {"date": "2026-01-02", "close": 90},
            ],
            latest_price=95,
            latest_date="2026-01-02",
        )
        self.assertEqual(metric["currentPct"], -5.0)
        self.assertEqual(metric["maxPct"], -5.0)

    def test_insufficient_history_is_explicit(self):
        metric = calculate_drawdown([{"date": "2026-01-01", "close": 10}])
        self.assertEqual(metric["status"], "unavailable")
        self.assertNotIn("currentPct", metric)


class DrawdownPayloadTests(unittest.TestCase):
    def test_empty_payload_is_versioned_without_division_error(self):
        payload = enrich_payload({"rows": []})
        self.assertEqual(payload["schema_version"], "1.1")
        self.assertEqual(payload["drawdown_schema_version"], "1.0")
        self.assertEqual(payload["drawdown_coverage"], 0.0)


if __name__ == "__main__":
    unittest.main()
