from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_earnings_radar.py"
spec = importlib.util.spec_from_file_location("generate_earnings_radar", MODULE_PATH)
assert spec and spec.loader
radar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = radar
spec.loader.exec_module(radar)


class EarningsRadarTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 7, 18)
        self.portfolio = [
            {"ticker": "TSLA", "name": "Tesla, Inc.", "portfolio_status": "holding", "role": "Growth platform"},
            {"ticker": "NVDA", "name": "NVIDIA Corporation", "portfolio_status": "holding", "role": "Core AI"},
        ]
        self.relevance = {
            "relations": {
                "TSM": {
                    "related_to": ["NVDA"],
                    "reason_th": "ห่วงโซ่อุปทานเซมิคอนดักเตอร์",
                }
            }
        }
        self.state = {
            "batch": {
                "earnings_calendar": {
                    "window": {"from": "2026-07-17", "to": "2026-08-31"},
                    "data": [
                        {
                            "symbol": "TSLA",
                            "date": "2026-07-18",
                            "hour": "amc",
                            "quarter": 2,
                            "year": 2026,
                            "epsEstimate": 0.5,
                            "revenueEstimate": 24_000_000_000,
                        },
                        {
                            "symbol": "TSM",
                            "date": "2026-07-18",
                            "hour": "bmo",
                            "quarter": 2,
                            "year": 2026,
                            "epsEstimate": 1.5,
                            "revenueEstimate": 20_000_000_000,
                        },
                        {
                            "symbol": "SMALL",
                            "date": "2026-07-18",
                            "hour": "",
                            "quarter": 2,
                            "year": 2026,
                            "epsEstimate": None,
                            "revenueEstimate": None,
                        },
                        {
                            "symbol": "FUTURE",
                            "date": "2026-08-20",
                            "hour": "bmo",
                            "quarter": 2,
                            "year": 2026,
                        },
                    ],
                }
            },
            "endpoints": {
                "company_profile": {
                    "TSM": {
                        "status": "ok",
                        "updated_at": "2026-07-18T00:00:00+00:00",
                        "data": {
                            "ticker": "TSM",
                            "name": "Taiwan Semiconductor Manufacturing",
                            "finnhubIndustry": "Semiconductors",
                            "marketCapitalization": 900000,
                        },
                    }
                },
                "company_earnings": {
                    "NVDA": {"status": "ok", "updated_at": "2026-07-18T00:00:00+00:00", "data": []}
                },
            },
            "runs": [{"universe_count": 408}],
        }

    def test_market_wide_rows_are_not_filtered_to_portfolio(self):
        payload = radar.build_payload(
            self.state,
            {"items": []},
            self.portfolio,
            self.relevance,
            today=self.today,
            days_back=0,
            days_forward=1,
        )
        tickers = {item["ticker"] for item in payload["items"]}
        self.assertEqual(tickers, {"TSLA", "TSM", "SMALL"})
        self.assertEqual(payload["summary"]["total"], 3)
        self.assertEqual(payload["coverage"]["market_source_rows"], 4)
        self.assertEqual(payload["coverage"]["coverage_universe_total"], 408)

    def test_confirmed_official_row_overrides_provider_date_row_and_keeps_estimates(self):
        official = {
            "items": [
                {
                    "ticker": "TSLA",
                    "earnings_date": "2026-07-18",
                    "event_time": "2026-07-18T17:30:00-04:00",
                    "status": "confirmed",
                    "source_type": "company_ir",
                    "source_url": "https://example.com/tsla-ir",
                    "time": "after_market",
                    "confidence": "high",
                }
            ]
        }
        payload = radar.build_payload(
            self.state,
            official,
            self.portfolio,
            self.relevance,
            today=self.today,
            days_back=0,
            days_forward=0,
        )
        tsla = next(item for item in payload["items"] if item["ticker"] == "TSLA")
        self.assertEqual(tsla["status"], "confirmed")
        self.assertEqual(tsla["source_type"], "company_ir")
        self.assertEqual(tsla["time"], "after_market")
        self.assertEqual(tsla["eps_estimate"], 0.5)
        self.assertEqual(tsla["revenue_estimate"], 24_000_000_000)

    def test_relation_classification_is_explicit(self):
        payload = radar.build_payload(
            self.state,
            {"items": []},
            self.portfolio,
            self.relevance,
            today=self.today,
            days_back=0,
            days_forward=0,
        )
        by_ticker = {item["ticker"]: item for item in payload["items"]}
        self.assertEqual(by_ticker["TSLA"]["relation"], "portfolio")
        self.assertEqual(by_ticker["TSM"]["relation"], "related")
        self.assertEqual(by_ticker["TSM"]["related_to"], ["NVDA"])
        self.assertEqual(by_ticker["SMALL"]["relation"], "market")

    def test_summary_counts_timing_and_relations(self):
        payload = radar.build_payload(
            self.state,
            {"items": []},
            self.portfolio,
            self.relevance,
            today=self.today,
            days_back=0,
            days_forward=0,
        )
        summary = payload["summary"]
        self.assertEqual(summary["after_market"], 1)
        self.assertEqual(summary["before_market"], 1)
        self.assertEqual(summary["unknown"], 1)
        self.assertEqual(summary["portfolio"], 1)
        self.assertEqual(summary["related"], 1)
        self.assertEqual(summary["market"], 1)

    def test_missing_values_are_not_fabricated(self):
        payload = radar.build_payload(
            self.state,
            {"items": []},
            self.portfolio,
            self.relevance,
            today=self.today,
            days_back=0,
            days_forward=0,
        )
        small = next(item for item in payload["items"] if item["ticker"] == "SMALL")
        self.assertIsNone(small["eps_estimate"])
        self.assertIsNone(small["revenue_estimate"])
        self.assertEqual(small["name"], "SMALL")
        self.assertEqual(small["time"], "unknown")

    def test_rows_outside_publish_window_are_excluded(self):
        payload = radar.build_payload(
            self.state,
            {"items": []},
            self.portfolio,
            self.relevance,
            today=self.today,
            days_back=0,
            days_forward=14,
        )
        self.assertNotIn("FUTURE", {item["ticker"] for item in payload["items"]})


if __name__ == "__main__":
    unittest.main()
