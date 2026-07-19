from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "harden_earnings_radar.py"
spec = importlib.util.spec_from_file_location("harden_earnings_radar", MODULE_PATH)
assert spec and spec.loader
hardener = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hardener
spec.loader.exec_module(hardener)


class EarningsRadarHardeningTests(unittest.TestCase):
    def base_payload(self):
        return {
            "schema_version": "1.0",
            "window": {"from": "2026-07-18", "to": "2026-09-02", "days_forward": 45},
            "coverage": {"market_source_rows": 2, "portfolio_total": 1, "published_rows": 2},
            "items": [
                {
                    "ticker": "MARKET",
                    "earnings_date": "2026-08-10",
                    "source_type": "finnhub",
                    "relation": "market",
                    "related_to": [],
                },
                {
                    "ticker": "OFFICIAL",
                    "earnings_date": "2026-07-22",
                    "source_type": "company_ir",
                    "status": "confirmed",
                    "relation": "portfolio",
                    "related_to": ["OFFICIAL"],
                },
            ],
            "policy": {},
        }

    def state(self, dates=("2026-08-10", "2026-08-11")):
        return {
            "batch": {
                "earnings_calendar": {
                    "data": [
                        {"symbol": f"T{index}", "date": value}
                        for index, value in enumerate(dates)
                    ]
                }
            }
        }

    def test_optional_fields_are_explicit_nulls(self):
        payload = hardener.harden_payload(self.base_payload(), self.state())
        official = next(item for item in payload["items"] if item["ticker"] == "OFFICIAL")
        for field in hardener.OPTIONAL_ITEM_FIELDS:
            self.assertIn(field, official)
        self.assertIsNone(official["eps_estimate"])
        self.assertIsNone(official["revenue_estimate"])
        self.assertIsNone(official["source_url"])

    def test_source_window_must_overlap_publish_window(self):
        with self.assertRaises(SystemExit):
            hardener.harden_payload(
                self.base_payload(),
                self.state(("2026-10-10", "2026-10-11")),
            )

    def test_market_row_must_survive_normalization_in_window(self):
        payload = self.base_payload()
        payload["items"] = [payload["items"][1]]
        with self.assertRaises(SystemExit):
            hardener.harden_payload(payload, self.state())

    def test_coverage_records_actual_source_and_overlap_ranges(self):
        payload = hardener.harden_payload(self.base_payload(), self.state())
        coverage = payload["coverage"]
        self.assertEqual(coverage["market_rows_in_window"], 1)
        self.assertEqual(
            coverage["market_source_date_range"],
            {"from": "2026-08-10", "to": "2026-08-11"},
        )
        self.assertEqual(
            coverage["provider_window_overlap"],
            {"from": "2026-08-10", "to": "2026-08-11"},
        )
        self.assertTrue(coverage["provider_window_overlaps_publish_window"])


if __name__ == "__main__":
    unittest.main()
