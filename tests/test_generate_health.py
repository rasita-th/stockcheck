import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import generate_health as health


class GenerateHealthTests(unittest.TestCase):
    def test_parse_utc_suffix(self):
        parsed = health.parse_dt("2026-07-29 07:49:15 UTC")
        self.assertEqual(parsed, datetime(2026, 7, 29, 7, 49, 15, tzinfo=timezone.utc))

    def test_inspect_uses_fundamental_timestamp_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fundamental.json"
            path.write_text(json.dumps({
                "generatedAtFundamental": "2026-07-29 07:49:15 UTC",
                "count": 408,
            }), encoding="utf-8")
            with patch("scripts.generate_health.datetime") as mocked_datetime:
                mocked_datetime.now.return_value = datetime(2026, 7, 29, 8, 0, tzinfo=timezone.utc)
                mocked_datetime.fromisoformat = datetime.fromisoformat
                mocked_datetime.strptime = datetime.strptime
                result = health.inspect(path, 60)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["row_count"], 408)

    def test_quote_is_fresh_during_regular_market_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote_latest.json"
            path.write_text(json.dumps({
                "market_as_of": "2026-08-12T17:40:00+00:00",
                "rows": [{"ticker": "TEST", "price": 10}],
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "fresh")
            self.assertEqual(result["session"]["phase"], "market-open")

    def test_quote_is_stale_during_regular_market_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote_latest.json"
            path.write_text(json.dumps({
                "market_as_of": "2026-08-12T17:20:00+00:00",
                "rows": [{"ticker": "TEST", "price": 10}],
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "stale")

    def test_quote_from_latest_close_is_not_stale_after_market(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote_latest.json"
            path.write_text(json.dumps({
                "market_as_of": "2026-08-12T20:05:00+00:00",
                "rows": [{"ticker": "TEST", "price": 10}],
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 12, 22, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "latest-completed-session")
            self.assertEqual(result["session"]["latest_completed_session"], "2026-08-12")

    def test_quote_from_friday_close_is_current_on_weekend(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote_latest.json"
            path.write_text(json.dumps({
                "market_as_of": "2026-08-14T20:05:00+00:00",
                "rows": [{"ticker": "TEST", "price": 10}],
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "latest-completed-session")
            self.assertEqual(result["session"]["phase"], "weekend")

    def test_quote_from_previous_close_is_current_before_market(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote_latest.json"
            path.write_text(json.dumps({
                "market_as_of": "2026-08-11T20:05:00+00:00",
                "rows": [{"ticker": "TEST", "price": 10}],
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "latest-completed-session")
            self.assertEqual(result["session"]["phase"], "pre-market")

    def test_missing_quote_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = health.inspect(
                Path(tmp) / "quote_latest.json",
                30,
                now=datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "unavailable")

    def test_source_market_latest_session_is_not_stale_after_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source_freshness.json"
            path.write_text(json.dumps({
                "checked_at": "2026-08-12T22:00:00+00:00",
                "status": "fresh",
                "newest_market_date": "2026-08-12",
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 12, 22, 1, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "latest-completed-session")
            self.assertEqual(result["upstream_status"], "fresh")

    def test_source_market_previous_session_is_stale_while_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source_freshness.json"
            path.write_text(json.dumps({
                "checked_at": "2026-08-12T18:00:00+00:00",
                "status": "fresh",
                "newest_market_date": "2026-08-11",
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 12, 18, 1, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "stale")

    def test_unavailable_source_is_partial_but_unavailable_quote_is_error(self):
        healthy = {"status": "fresh"}
        self.assertEqual(health.overall_status({
            "quote": healthy,
            "source_market": {"status": "unavailable"},
        }), "partial")
        self.assertEqual(health.overall_status({
            "quote": {"status": "unavailable"},
            "source_market": healthy,
        }), "error")

    def test_market_holiday_uses_previous_completed_session(self):
        session = health.market_session(datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc))
        self.assertEqual(session["phase"], "market-holiday")
        self.assertEqual(session["latest_completed_session"], "2026-09-04")

    def test_explicit_fallback_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote_latest.json"
            path.write_text(json.dumps({
                "market_as_of": "2026-08-12T17:55:00+00:00",
                "fallback_count": 2,
                "rows": [{"ticker": "TEST", "price": 10}],
            }), encoding="utf-8")
            result = health.inspect(
                path,
                30,
                now=datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "degraded-fallback")
            self.assertEqual(result["fallback_count"], 2)

    def test_market_pulse_ttl_covers_twelve_hour_schedule(self):
        self.assertEqual(health.FILES["market_pulse"][1], 13 * 60)

    def test_main_writes_byte_identical_health_mirrors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = root / "data" / "generated"
            generated.mkdir(parents=True)
            timestamp = datetime.now(timezone.utc).isoformat()
            for filename, _ttl in health.FILES.values():
                (generated / filename).write_text(
                    json.dumps({"generated_at": timestamp, "rows": [{"ticker": "TEST"}]}),
                    encoding="utf-8",
                )
            outputs = (
                generated / "health.json",
                root / "site" / "data" / "health.json",
                root / "static" / "data" / "health.json",
            )
            with patch.object(health, "DATA", generated), patch.object(health, "OUTPUTS", outputs):
                health.main()
            canonical = outputs[0].read_bytes()
            self.assertTrue(canonical)
            self.assertTrue(all(output.read_bytes() == canonical for output in outputs[1:]))


if __name__ == "__main__":
    unittest.main()
