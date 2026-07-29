from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.technical_shards import build_index, build_shards, write_outputs


class TechnicalShardTests(unittest.TestCase):
    def sample(self):
        return {
            "generatedAt": "2026-07-29 14:42:36 UTC",
            "generatedAtTechnical": "2026-07-29 14:42:36 UTC",
            "range": "1y",
            "interval": "1d",
            "rows": [{"symbol": "NVDA", "close": 123.45, "score": 80}],
            "errors": [],
            "quotes": {
                "NVDA": {
                    "latest": {"symbol": "NVDA", "close": 123.45},
                    "series": [{"date": "2026-07-29", "close": 123.45}],
                    "meta": {"source": "test"},
                }
            },
        }

    def test_index_is_summary_only(self):
        index = build_index(self.sample())
        self.assertEqual(index["schema_version"], "2.0")
        self.assertEqual(index["count"], 1)
        self.assertNotIn("quotes", index)
        self.assertEqual(index["rows"][0]["symbol"], "NVDA")

    def test_shard_preserves_latest_series_and_meta(self):
        shards = build_shards(self.sample())
        self.assertEqual(set(shards), {"NVDA"})
        self.assertEqual(shards["NVDA"]["latest"]["close"], 123.45)
        self.assertEqual(len(shards["NVDA"]["series"]), 1)

    def test_write_outputs_removes_stale_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "technical"
            stale = root / "symbols" / "OLD.json"
            stale.parent.mkdir(parents=True)
            stale.write_text("{}", encoding="utf-8")
            write_outputs(self.sample(), [root])
            self.assertFalse(stale.exists())
            self.assertTrue((root / "index.json").exists())
            self.assertTrue((root / "symbols" / "NVDA.json").exists())
            index = json.loads((root / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["count"], 1)

    def test_symbol_path_traversal_is_rejected(self):
        payload = self.sample()
        payload["quotes"] = {"../BAD": {"latest": {}, "series": [], "meta": {}}}
        with self.assertRaises(ValueError):
            build_shards(payload)


if __name__ == "__main__":
    unittest.main()
