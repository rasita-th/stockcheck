from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import finnhub_pipeline as pipeline
import run_finnhub_free_tier as runner


class FinnhubFreeTierTests(unittest.TestCase):
    def setUp(self):
        self.original_endpoints = dict(pipeline.ENDPOINTS)

    def tearDown(self):
        pipeline.ENDPOINTS.clear()
        pipeline.ENDPOINTS.update(self.original_endpoints)

    def test_premium_endpoints_are_disabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            skipped = runner.configure_endpoints()
        self.assertIn("eps_estimates", skipped)
        self.assertIn("revenue_estimates", skipped)
        self.assertIn("price_target", skipped)
        self.assertIn("company_earnings", pipeline.ENDPOINTS)
        self.assertIn("recommendation_trends", pipeline.ENDPOINTS)

    def test_premium_endpoint_can_be_opted_in(self):
        with mock.patch.dict(os.environ, {"FINNHUB_ENABLE_PREMIUM_ESTIMATES": "1"}, clear=True):
            skipped = runner.configure_endpoints()
        self.assertNotIn("eps_estimates", skipped)
        self.assertNotIn("revenue_estimates", skipped)
        self.assertIn("eps_estimates", pipeline.ENDPOINTS)

    def test_calendar_error_preserves_last_known_good(self):
        state = pipeline.default_state()
        old_rows = [{"symbol": "NVDA", "date": "2026-07-19"}]
        state["batch"]["earnings_calendar"] = {
            "status": "ok",
            "updated_at": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
            "data": old_rows,
        }

        class FailingClient:
            def earnings_calendar(self, **kwargs):
                return {"error": "API limit reached"}

        result = runner.safe_update_earnings_calendar(state, FailingClient())
        self.assertEqual(result["status"], "error")
        self.assertEqual(state["batch"]["earnings_calendar"]["data"], old_rows)
        self.assertEqual(state["batch"]["earnings_calendar"]["last_error_type"], "provider_error")

    def test_failed_ticker_call_preserves_good_data_and_remains_due(self):
        state = pipeline.default_state()
        old_stamp = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        state["endpoints"]["company_earnings"]["NVDA"] = {
            "status": "ok",
            "updated_at": old_stamp,
            "data": [{"actual": 1.0}],
        }

        class FailingClient:
            def company_earnings(self, ticker, limit=8):
                raise RuntimeError("429 rate limit")

        with mock.patch.dict(os.environ, {}, clear=True):
            runner.configure_endpoints()
            result = runner.safe_update_ticker_endpoints(
                state, "events", ["NVDA"], FailingClient(), 1, 0
            )
        entry = state["endpoints"]["company_earnings"]["NVDA"]
        self.assertEqual(entry["data"], [{"actual": 1.0}])
        self.assertEqual(entry["updated_at"], old_stamp)
        self.assertEqual(entry["last_error_type"], "rate_limited")
        self.assertIn("NVDA", pipeline.due_tickers(state, "company_earnings", ["NVDA"]))
        self.assertEqual(result["errors"][0]["type"], "rate_limited")

    def test_calendar_estimates_are_derived_without_premium_calls(self):
        contract = {
            "items": [{
                "ticker": "NVDA",
                "earnings_date": "2026-07-19",
                "source_type": "finnhub",
                "eps_estimate": 1.23,
                "revenue_estimate": 5000000000,
                "time": "after_market",
                "updated_at": "2026-07-18T00:00:00+00:00",
            }]
        }
        estimates = runner.derive_calendar_estimates(contract)
        self.assertEqual(estimates["NVDA"]["eps_estimate"], 1.23)
        self.assertEqual(estimates["NVDA"]["revenue_estimate"], 5000000000)
        self.assertEqual(estimates["NVDA"]["source"], "finnhub_earnings_calendar")


class FinnhubTodayIntegrationTests(unittest.TestCase):
    def test_earnings_calendar_contract_creates_today_event(self):
        import generate_attention_p0 as attention_p0

        contract = {
            "schema_version": "2.0",
            "updated_at": "2026-07-18T00:00:00+00:00",
            "items": [{
                "ticker": "NVDA",
                "earnings_date": "2026-07-19",
                "status": "estimated",
                "time": "after_market",
                "source_type": "finnhub",
                "source_url": None,
                "confidence": "medium",
                "eps_estimate": 1.23,
                "note": "Finnhub earnings calendar",
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "earnings_calendar.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            fixed_now = datetime(2026, 7, 18, 12, 0, tzinfo=ZoneInfo("America/New_York"))
            with mock.patch.object(attention_p0, "EARNINGS_PATHS", [path]), mock.patch.object(
                attention_p0, "now_et", return_value=fixed_now
            ):
                calendar = attention_p0.load_earnings_calendar()
                events = attention_p0.earnings_events(
                    calendar,
                    {"NVDA": {"ticker": "NVDA", "portfolio_status": "holding"}},
                )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["ticker"], "NVDA")
        self.assertEqual(events[0]["event_subtype"], "earnings_upcoming")
        self.assertEqual(events[0]["source"]["type"], "finnhub")


if __name__ == "__main__":
    unittest.main()
