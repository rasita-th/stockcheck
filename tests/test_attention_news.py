import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from attention_sources import (  # noqa: E402
    build_registry_entry,
    canonical_url,
    collect_gdelt,
    collect_ir,
    deduplicate_events,
    entity_confidence,
)

FIXTURES = ROOT / "tests" / "fixtures" / "attention_news"
GOLDEN = ROOT / "tests" / "golden" / "attention_today_v2_0.json"
NOW = datetime(2026, 7, 18, 8, 15, tzinfo=timezone.utc)


class AttentionNewsTests(unittest.TestCase):
    def setUp(self):
        self.stock = {
            "ticker": "RKLB",
            "name": "Rocket Lab USA, Inc.",
            "company_ir_url": "https://investors.rocketlabusa.com/",
        }
        self.entry = build_registry_entry(
            self.stock,
            {
                "aliases": ["Rocket Lab"],
                "domains": ["investors.rocketlabusa.com"],
                "ir_feeds": ["https://investors.rocketlabusa.com/rss"],
            },
        )

    def test_canonical_url_removes_tracking(self):
        self.assertEqual(
            canonical_url("https://example.com/item?utm_source=x&id=1"),
            "https://example.com/item?id=1",
        )

    def test_ambiguous_ticker_does_not_match_generic_phrase(self):
        entry = build_registry_entry({"ticker": "OPEN", "name": "Opendoor Technologies Inc."}, {})
        confidence, _ = entity_confidence("Open door design trends for summer", "https://example.com", entry)
        self.assertEqual(confidence, "rejected")

    def test_ir_primary_and_gdelt_secondary_merge(self):
        feed = (FIXTURES / "ir_feed.xml").read_bytes()
        gdelt = json.loads((FIXTURES / "gdelt_articles.json").read_text(encoding="utf-8"))
        ir_events, _, status, _ = collect_ir(
            self.entry,
            {},
            fetch_bytes_fn=lambda _: feed,
            now=NOW,
            bootstrap_hours=12,
        )
        self.assertEqual(status, "ok")
        gdelt_events, _, status, _ = collect_gdelt(
            self.entry,
            {},
            fetch_json=lambda _: gdelt,
            now=NOW,
            bootstrap_hours=12,
        )
        self.assertEqual(status, "ok")
        merged = deduplicate_events(ir_events + gdelt_events)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["verification_status"], "confirmed")
        self.assertEqual(merged[0]["verification_level"], "corroborated")
        self.assertEqual(merged[0]["source"]["quality"], "primary")
        self.assertGreaterEqual(merged[0]["secondary_source_count"], 1)

    def test_gdelt_duplicate_domains_are_one_event(self):
        gdelt = json.loads((FIXTURES / "gdelt_articles.json").read_text(encoding="utf-8"))
        events, _, _, _ = collect_gdelt(
            self.entry,
            {},
            fetch_json=lambda _: gdelt,
            now=NOW,
            bootstrap_hours=12,
        )
        merged = deduplicate_events(events)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["verification_status"], "unverified")
        self.assertEqual(merged[0]["verification_level"], "corroborated_secondary")

    def test_golden_contract_remains_backward_compatible(self):
        payload = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertTrue(str(payload.get("schema_version", "")).startswith("2.0"))
        self.assertIsInstance(payload.get("items"), list)
        item = payload["items"][0]
        for field in ("ticker", "priority", "why_today", "events", "source", "verification_status"):
            self.assertIn(field, item)


if __name__ == "__main__":
    unittest.main()
