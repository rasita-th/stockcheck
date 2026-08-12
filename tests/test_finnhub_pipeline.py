from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "finnhub_pipeline.py"
sys.path.insert(0, str(MODULE_PATH.parent))
spec = importlib.util.spec_from_file_location("finnhub_pipeline", MODULE_PATH)
assert spec and spec.loader
pipeline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pipeline
spec.loader.exec_module(pipeline)


class FinnhubPipelineTests(unittest.TestCase):
    def test_confirmed_calendar_item_overrides_finnhub_estimate(self):
        incoming = [{"ticker": "TSLA", "earnings_date": "2026-07-22", "status": "estimated", "source_type": "finnhub"}]
        confirmed = [{"ticker": "TSLA", "earnings_date": "2026-07-22", "status": "confirmed", "source_type": "company_ir"}]
        merged = pipeline.merge_earnings_items(confirmed, incoming)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["status"], "confirmed")
        self.assertEqual(merged[0]["source_type"], "company_ir")

    def test_due_tickers_are_unique_and_missing_first(self):
        now = datetime.now(timezone.utc)
        state = pipeline.default_state()
        state["endpoints"]["recommendation_trends"]["AAPL"] = {
            "updated_at": now.isoformat(), "status": "ok", "data": []
        }
        state["endpoints"]["recommendation_trends"]["MSFT"] = {
            "updated_at": (now - timedelta(hours=30)).isoformat(), "status": "ok", "data": []
        }
        due = pipeline.due_tickers(state, "recommendation_trends", ["AAPL", "MSFT", "NVDA", "NVDA"])
        self.assertEqual(due[0], "NVDA")
        self.assertIn("MSFT", due)
        self.assertNotIn("AAPL", due)
        self.assertEqual(due.count("NVDA"), 1)

    def test_public_contracts_preserve_legacy_shapes(self):
        state = pipeline.default_state()
        state["endpoints"]["recommendation_trends"]["NVDA"] = {
            "status": "ok", "updated_at": "2026-07-18T00:00:00+00:00", "data": [{"period": "2026-07-01"}]
        }
        state["endpoints"]["company_earnings"]["NVDA"] = {
            "status": "ok", "updated_at": "2026-07-18T00:00:00+00:00", "data": [{"period": "2026-Q2"}]
        }
        with mock.patch.object(pipeline, "load_json", return_value={"items": []}):
            contracts = pipeline.public_contracts(state, ["NVDA"])
        recommendation = contracts["recommendation_trends.json"]
        self.assertIn("items", recommendation)
        self.assertIn("NVDA", recommendation)
        self.assertEqual(recommendation["items"]["NVDA"]["rows"][0]["period"], "2026-07-01")
        self.assertIn("surprises", contracts["eps_surprises.json"])
        calendar = contracts["earnings_calendar.json"]
        self.assertEqual(calendar["schema_version"], "2.0")
        self.assertTrue(calendar["features"]["canonical_provenance"])
        self.assertTrue(calendar["features"]["legacy_fields_preserved"])
        self.assertEqual(calendar["contract_metrics"]["canonical_provenance_rows"], len(calendar["items"]))

    def test_public_calendar_dual_write_enriches_official_and_provider_rows(self):
        state = pipeline.default_state()
        state["batch"]["earnings_calendar"] = {
            "status": "ok",
            "updated_at": "2026-08-04T12:00:00+00:00",
            "data": [
                {
                    "symbol": "NVDA",
                    "date": "2026-08-26",
                    "quarter": 2,
                    "year": 2027,
                    "hour": "amc",
                    "epsEstimate": 1.23,
                },
                {
                    "symbol": "TSLA",
                    "date": "2026-07-22",
                    "quarter": 2,
                    "year": 2026,
                    "hour": "amc",
                },
            ],
        }
        legacy_calendar = {
            "items": [
                {
                    "ticker": "TSLA",
                    "earnings_date": "2026-07-22",
                    "status": "confirmed",
                    "source_type": "company_ir",
                    "source_url": "https://example.com/tesla-ir",
                }
            ]
        }
        with mock.patch.object(pipeline, "load_json", return_value=legacy_calendar):
            calendar = pipeline.public_contracts(state, ["NVDA", "TSLA"])["earnings_calendar.json"]
        by_ticker = {row["ticker"]: row for row in calendar["items"]}

        nvda = by_ticker["NVDA"]
        self.assertEqual(nvda["source_type"], "finnhub")
        self.assertEqual(nvda["domain_policy"]["earnings_radar"], "allow_estimated")
        self.assertEqual(nvda["domain_policy"]["today_catalyst"], "reject")
        self.assertEqual(nvda["verification"]["level"], "estimated")

        tsla = by_ticker["TSLA"]
        self.assertEqual(tsla["source_type"], "company_ir")
        self.assertEqual(tsla["domain_policy"]["today_catalyst"], "allow")
        self.assertEqual(tsla["verification"]["level"], "confirmed")
        self.assertEqual(tsla["provenance"][0]["provider"], "company_ir")

    def test_secret_validation_rejects_leak(self):
        with self.assertRaises(RuntimeError):
            pipeline.validate_no_secret({"token": "secret-123"}, ["secret-123"])
        pipeline.validate_no_secret({"status": "ok"}, ["secret-123"])

    def test_update_ticker_endpoints_respects_budget(self):
        class FakeClient:
            def recommendation_trends(self, ticker):
                return [{"symbol": ticker, "period": "2026-07-01", "buy": 1}]
            def price_target(self, ticker):
                return {"symbol": ticker, "targetMean": 100}
            def company_profile2(self, symbol):
                return {"ticker": symbol}
            def company_basic_financials(self, ticker, metric):
                return {"symbol": ticker, "metric": {"peBasicExclExtraTTM": 20}}

        state = pipeline.default_state()
        result = pipeline.update_ticker_endpoints(state, "analyst", ["AAPL", "MSFT"], FakeClient(), 3, 0)
        self.assertEqual(result["calls_used"], 3)
        self.assertLessEqual(sum(len(v) for v in result["refreshed"].values()), 3)

    def test_sec_filing_normalizer_keeps_only_official_sec_records(self):
        rows = pipeline.normalize_sec_filings([
            {
                "symbol": "RKLB",
                "form": "8-K",
                "accessNumber": "0001819994-26-000001",
                "filedDate": "2026-08-12",
                "acceptedDate": "2026-08-12 16:05:00",
                "reportUrl": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000001/rklb-8k.htm",
            },
            {
                "symbol": "RKLB",
                "form": "8-K",
                "accessNumber": "0001819994-26-000002",
                "filedDate": "2026-08-12",
                "reportUrl": "https://example.invalid/not-sec.htm",
            },
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["accessionNumber"], "0001819994-26-000001")
        self.assertEqual(rows[0]["primaryDocument"], "rklb-8k.htm")
        self.assertEqual(rows[0]["sourceUrl"], "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000001/rklb-8k.htm")

    def test_sec_filing_endpoint_uses_bounded_recent_window(self):
        class FakeClient:
            def filings(self, **kwargs):
                self.kwargs = kwargs
                return []

        client = FakeClient()
        pipeline.endpoint_call(client, "sec_filings", "RKLB")
        self.assertEqual(client.kwargs["symbol"], "RKLB")
        self.assertIn("_from", client.kwargs)
        self.assertIn("to", client.kwargs)

    def test_sec_filing_queue_is_limited_to_portfolio_universe(self):
        state = pipeline.default_state()
        with mock.patch.object(pipeline, "load_portfolio_tickers", return_value=["RKLB"]):
            due = pipeline.due_tickers(state, "sec_filings", ["AAPL", "RKLB", "MSFT"])
        self.assertEqual(due, ["RKLB"])

    def test_output_does_not_expose_key_presence(self):
        state = pipeline.default_state()
        with mock.patch.object(pipeline, "load_json", return_value={"items": []}):
            contracts = pipeline.public_contracts(state, [])
        payload = json.dumps(contracts)
        self.assertNotIn("FINNHUB_API_KEY", payload)
        self.assertIsNone(contracts["eps_surprises.json"]["api_key_present"])


if __name__ == "__main__":
    unittest.main()
