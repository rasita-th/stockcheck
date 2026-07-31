from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.build_screener_snapshot import build_snapshot


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


if __name__ == "__main__":
    unittest.main()
