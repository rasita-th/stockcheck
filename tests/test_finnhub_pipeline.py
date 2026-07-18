from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "finnhub_pipeline.py"
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
        self.assertEqual(contracts["earnings_calendar.json"]["schema_version"], "2.0")

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

    def test_output_does_not_expose_key_presence(self):
        state = pipeline.default_state()
        with mock.patch.object(pipeline, "load_json", return_value={"items": []}):
            contracts = pipeline.public_contracts(state, [])
        payload = json.dumps(contracts)
        self.assertNotIn("FINNHUB_API_KEY", payload)
        self.assertIsNone(contracts["eps_surprises.json"]["api_key_present"])


if __name__ == "__main__":
    unittest.main()
