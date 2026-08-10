from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.sync_attention_market_fields import sync_paths


class SyncAttentionMarketFieldsTests(unittest.TestCase):
    def test_projects_market_fields_and_preserves_event_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            technical = root / "technical.json"
            attention_paths = tuple(root / name for name in ("a.json", "b.json", "c.json"))
            technical.write_text(json.dumps({
                "rows": [{
                    "symbol": "AMD",
                    "price": 105.0,
                    "dayPct": 2.5,
                    "volumeRatio20": 1.4,
                }],
            }), encoding="utf-8")
            payload = {
                "updated_at": "2026-08-10T16:17:58+00:00",
                "items": [{
                    "ticker": "AMD",
                    "price": 100.0,
                    "day_change_pct": -1.0,
                    "relative_volume": 0.5,
                    "events": [{"event_id": "event-1"}],
                    "impact": {"baseline_price": 100.0, "current_price": 100.0},
                }],
                "technical_watch": [{"ticker": "AMD", "price": 100.0}],
            }
            attention_paths[0].write_text(json.dumps(payload), encoding="utf-8")

            self.assertEqual(sync_paths(technical, attention_paths), 2)

            rendered = attention_paths[0].read_bytes()
            self.assertTrue(all(path.read_bytes() == rendered for path in attention_paths))
            result = json.loads(rendered)
            item = result["items"][0]
            self.assertEqual(result["updated_at"], payload["updated_at"])
            self.assertEqual(item["events"], payload["items"][0]["events"])
            self.assertEqual(item["price"], 105.0)
            self.assertEqual(item["day_change_pct"], 2.5)
            self.assertEqual(item["relative_volume"], 1.4)
            self.assertEqual(item["impact"]["current_price"], 105.0)
            self.assertEqual(item["impact"]["change_pct"], 5.0)
            self.assertEqual(result["technical_watch"][0]["price"], 105.0)


if __name__ == "__main__":
    unittest.main()
