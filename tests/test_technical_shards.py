from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_generated_file_sizes import MIB, budget_for
from scripts.technical_shards import build_index, build_legacy_summary, build_shards, write_outputs

ROOT = Path(__file__).resolve().parents[1]


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

    def test_legacy_fallback_does_not_duplicate_full_history(self):
        summary = build_legacy_summary(self.sample(), mode="test-summary")
        self.assertEqual(summary["schema_version"], "2.0-summary")
        self.assertEqual(summary["quotes"], {})
        self.assertEqual(summary["rows"][0]["symbol"], "NVDA")
        self.assertEqual(summary["detailContract"], "technical/symbols/{symbol}.json")
        self.assertNotIn("series", json.dumps(summary))

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

    def test_site_and_static_runtime_match(self):
        site = (ROOT / "site" / "technical-shards-v2.js").read_text(encoding="utf-8")
        static = (ROOT / "static" / "technical-shards-v2.js").read_text(encoding="utf-8")
        self.assertEqual(site, static)

    def test_runtime_uses_index_then_lazy_shards_with_legacy_fallback(self):
        text = (ROOT / "site" / "technical-shards-v2.js").read_text(encoding="utf-8")
        for token in (
            "data/technical/index.json",
            "data/technical/symbols/",
            "falling back to legacy technical.json",
            'schema_version !== "2.0"',
            "shardRequests = new Map()",
        ):
            self.assertIn(token, text)

    def test_runtime_does_not_treat_summary_or_fundamental_quote_as_loaded_series(self):
        text = (ROOT / "site" / "technical-shards-v2.js").read_text(encoding="utf-8")
        self.assertIn("function hasSeries(quote)", text)
        self.assertIn("if (hasSeries(cached)) return cached;", text)
        self.assertIn("!hasSeries(state.quotes[ticker])", text)
        self.assertIn("fundamental: existing.fundamental || {}", text)
        self.assertNotIn("if (state.quotes[ticker]) return state.quotes[ticker];", text)

    def test_monolith_exception_is_removed_and_shards_are_bounded(self):
        self.assertEqual(budget_for("site/data/technical.json"), (10 * MIB, 25 * MIB))
        self.assertEqual(budget_for("site/data/scanner.json"), (10 * MIB, 25 * MIB))
        self.assertEqual(budget_for("site/data/technical/index.json"), (3 * MIB, 5 * MIB))
        self.assertEqual(budget_for("site/data/technical/symbols/NVDA.json"), (512 * 1024, 1 * MIB))


if __name__ == "__main__":
    unittest.main()
