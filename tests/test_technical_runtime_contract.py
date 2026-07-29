from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TechnicalRuntimeContractTests(unittest.TestCase):
    def test_site_and_static_runtime_match(self):
        site = (ROOT / "site" / "technical-shards-v2.js").read_text(encoding="utf-8")
        static = (ROOT / "static" / "technical-shards-v2.js").read_text(encoding="utf-8")
        self.assertEqual(site, static)

    def test_runtime_uses_index_then_lazy_shards_with_legacy_fallback(self):
        text = (ROOT / "site" / "technical-shards-v2.js").read_text(encoding="utf-8")
        for token in (
            'data/technical/index.json',
            'data/technical/symbols/',
            'falling back to legacy technical.json',
            'schema_version !== "2.0"',
            'shardRequests = new Map()',
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
