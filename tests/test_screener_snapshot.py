from __future__ import annotations

import ast
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.build_screener_snapshot import build_snapshot
from scripts.update_quote_data import row_from_downloads

ROOT = Path(__file__).resolve().parents[1]


class ScreenerSnapshotTests(unittest.TestCase):
    NOW = datetime(2026, 7, 31, 15, 5, tzinfo=timezone.utc)

    def quote_payload(self):
        return {
            "schema_version": "1.0",
            "generated_at": "2026-07-31T15:00:00+00:00",
            "market_as_of": "2026-07-31T15:00:00+00:00",
            "stale_after_minutes": 30,
            "rows": [
                {
                    "ticker": "AMD",
                    "price": 493.23,
                    "previous_close": 490.0,
                    "day_change": 3.23,
                    "day_change_pct": 0.6592,
                }
            ],
        }

    def technical_payload(self):
        return {
            "generatedAt": "2026-07-31 15:00:10 UTC",
            "generatedAtTechnical": "2026-07-31 15:00:10 UTC",
            "rows": [
                {
                    "symbol": "AMD",
                    "close": 492.52,
                    "ema5": 483.04,
                    "ema20": 505.51,
                    "ema89": 438.10,
                    "ema200": 340.24,
                    "rsi14": 47.7,
                    "macd1226": 1.0,
                    "macdSignal9": 0.8,
                    "volume": 100,
                    "vol20": 100,
                    "high52w": 520.0,
                    "low52w": 150.0,
                    "score": 73,
                    "signal": "WATCH",
                }
            ],
        }

    def write_shard(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        shard = {
            "schema_version": "2.0",
            "symbol": "AMD",
            "latest": {"symbol": "AMD", "close": 492.52},
            "series": [
                {
                    "date": "2026-07-30",
                    "close": 490.0,
                    "high": 495.0,
                    "low": 480.0,
                    "ema5": 480.0,
                    "ema20": 500.0,
                    "ema89": 435.0,
                    "ema200": 338.0,
                    "rsi14": 46.0,
                    "macd1226": 0.7,
                    "macdSignal9": 0.6,
                    "volume": 100,
                    "vol20": 100,
                },
                {
                    "date": "2026-07-31",
                    "close": 492.52,
                    "high": 494.0,
                    "low": 485.0,
                    "ema5": 483.04,
                    "ema20": 505.51,
                    "ema89": 438.10,
                    "ema200": 340.24,
                    "rsi14": 47.7,
                    "macd1226": 1.0,
                    "macdSignal9": 0.8,
                    "volume": 100,
                    "vol20": 100,
                },
            ],
            "meta": {},
        }
        (root / "AMD.json").write_text(json.dumps(shard), encoding="utf-8")

    def test_live_quote_projects_all_price_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            shards = Path(tmp)
            self.write_shard(shards)
            snapshot = build_snapshot(
                self.quote_payload(), self.technical_payload(), shards, now=self.NOW
            )

        self.assertEqual(snapshot["contract"], "canonical-screener-snapshot")
        self.assertEqual(snapshot["row_count"], 1)
        self.assertEqual(snapshot["live_quote_coverage"], 1.0)
        row = snapshot["rows"][0]
        self.assertEqual(row["price"], 493.23)
        self.assertEqual(row["close"], 493.23)
        self.assertEqual(row["regularMarketPrice"], 493.23)
        self.assertEqual(row["dayPct"], 0.6592)
        self.assertEqual(row["pctVsEma20"], round((493.23 / 505.51 - 1) * 100, 2))
        self.assertEqual(row["snapshotStatus"], "live_quote")
        self.assertEqual(row["snapshotPriceSource"], "quote_latest.json")
        self.assertIsInstance(row["score"], int)
        self.assertTrue(row["signal"])

    def test_stale_quote_is_rejected_before_alert_snapshot_is_written(self):
        quote = self.quote_payload()
        quote["market_as_of"] = "2026-07-31T14:00:00+00:00"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SystemExit, "quote_latest is stale"):
                build_snapshot(quote, self.technical_payload(), Path(tmp), now=self.NOW)

    def test_low_quote_coverage_is_rejected(self):
        technical = self.technical_payload()
        technical["rows"] = [
            {**technical["rows"][0], "symbol": symbol}
            for symbol in ("AMD", "NVDA", "CIFR", "ZETA", "RKLB")
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SystemExit, "coverage too low"):
                build_snapshot(self.quote_payload(), technical, Path(tmp), now=self.NOW)

    def test_batch_quote_parser_uses_intraday_price_and_prior_daily_close(self):
        intraday_index = pd.to_datetime(
            ["2026-07-31T14:59:00Z", "2026-07-31T15:00:00Z"]
        )
        daily_index = pd.to_datetime(["2026-07-30", "2026-07-31"])
        columns = pd.MultiIndex.from_tuples([("AMD", "Close")])
        intraday = pd.DataFrame([[492.50], [493.23]], index=intraday_index, columns=columns)
        daily = pd.DataFrame([[490.00], [493.00]], index=daily_index, columns=columns)

        row = row_from_downloads("AMD", intraday, daily)

        self.assertEqual(row["price"], 493.23)
        self.assertEqual(row["previous_close"], 490.0)
        self.assertEqual(row["quote_mode"], "intraday")
        self.assertAlmostEqual(row["day_change_pct"], (493.23 / 490.0 - 1) * 100)

    def test_batch_quote_parser_falls_back_to_latest_daily_close(self):
        daily_index = pd.to_datetime(["2026-07-30", "2026-07-31"])
        columns = pd.MultiIndex.from_tuples([("AMD", "Close")])
        daily = pd.DataFrame([[490.00], [493.00]], index=daily_index, columns=columns)

        row = row_from_downloads("AMD", None, daily)

        self.assertEqual(row["price"], 493.0)
        self.assertEqual(row["previous_close"], 490.0)
        self.assertEqual(row["quote_mode"], "daily_close")

    def test_intraday_workflow_uses_bounded_quotes_and_isolates_full_technical_scan(self):
        workflow = (ROOT / ".github" / "workflows" / "refresh-live-v9-1.yml").read_text(
            encoding="utf-8"
        )
        quote_step = workflow.find("Refresh latest quotes in bounded batches")
        technical_step = workflow.find("Refresh full technical indicators and ticker shards")
        snapshot_step = workflow.find("Build canonical intraday screener snapshot")
        artifact_step = workflow.find("Build immutable core-data artifact")

        self.assertGreaterEqual(quote_step, 0)
        self.assertGreater(technical_step, quote_step)
        self.assertGreater(snapshot_step, technical_step)
        self.assertGreater(artifact_step, snapshot_step)
        self.assertIn('cron: "*/15 * * * 1-5"', workflow)
        self.assertIn('cron: "35 21 * * 1-5"', workflow)
        self.assertIn("full_technical:", workflow)
        self.assertIn("steps.window.outputs.full_technical == 'true'", workflow)
        self.assertIn("group: live-data-producer-main", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("QUOTE_BATCH_SIZE", workflow)
        self.assertIn("QUOTE_REQUEST_TIMEOUT", workflow)
        self.assertIn("timeout --signal=TERM 10m python scripts/update_quote_data.py", workflow)
        self.assertIn("python scripts/build_screener_snapshot.py", workflow)
        self.assertIn("python scripts/verify_screener_snapshot.py", workflow)
        self.assertNotIn("Refresh PR3 personal Today desk", workflow)
        self.assertNotIn("ATTENTION_NEWS_ENABLED", workflow)
        self.assertNotIn("SEC_USER_AGENT", workflow)
        self.assertNotIn("python scripts/publish_generated_data.py", workflow)
        self.assertNotIn("python scripts/validate_static_data.py", workflow)
        self.assertNotIn("SCREENER_SNAPSHOT_FIXTURE", workflow)
        self.assertNotIn("--allow-stale", workflow)

    def test_quote_refresh_is_batched_bounded_atomic_and_writes_deployable_mirrors(self):
        source = (ROOT / "scripts" / "update_quote_data.py").read_text(encoding="utf-8")
        ast.parse(source, filename="scripts/update_quote_data.py")
        for token in (
            "yf.download",
            "QUOTE_REFRESH_WORKERS",
            "QUOTE_BATCH_SIZE",
            "QUOTE_REQUEST_TIMEOUT",
            "QUOTE_MIN_COVERAGE",
            'group_by="ticker"',
            "timeout=timeout_seconds",
            'ROOT / "site" / "data" / "quote_latest.json"',
            'ROOT / "static" / "data" / "quote_latest.json"',
            "temporary.replace(path)",
            "quote coverage below minimum",
        ):
            self.assertIn(token, source)
        self.assertNotIn("ThreadPoolExecutor", source)
        self.assertNotIn("fast_info", source)
        self.assertNotIn("for symbol in symbols:\n        try:\n            t = yf.Ticker", source)


if __name__ == "__main__":
    unittest.main()
