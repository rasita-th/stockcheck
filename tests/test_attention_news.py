import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_attention_pr2 as pr2  # noqa: E402
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

    def test_recent_technical_scan_candidate_uses_real_scanner_fields(self):
        scan_date = pr2.p0.now_et().date().isoformat()
        events = pr2._technical_scan_candidates(
            [{"ticker": "TEST", "portfolio_status": "holding"}],
            {
                "TEST": {
                    "score": 95,
                    "signal": "BUY ZONE / Trend Confirmed",
                    "regularMarketTime": scan_date,
                    "rsi14": 61.2,
                    "pctVsEma20": 4.3,
                    "pctVsEma200": 18.7,
                    "volumeRatio20": 1.45,
                }
            },
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_subtype"], "technical_setup")
        self.assertEqual(events[0]["verification_status"], "confirmed")
        self.assertEqual(events[0]["source"]["type"], "technical_json")
        self.assertIn("score 95/100", events[0]["why_today"])
        self.assertIn("context, not a recommendation", events[0]["summary"])

    def test_internal_technical_verification_survives_dedupe(self):
        scan_date = pr2.p0.now_et().date().isoformat()
        event = pr2._technical_scan_candidates(
            [{"ticker": "TEST", "portfolio_status": "holding"}],
            {"TEST": {"score": 95, "signal": "BUY ZONE", "regularMarketTime": scan_date}},
        )[0]
        merged = pr2._dedupe_with_provenance([event])
        self.assertEqual(merged[0]["verification_status"], "confirmed")
        self.assertEqual(merged[0]["verification_level"], "confirmed_internal")
        self.assertIn("technical.json", merged[0]["verification_reason"])

    def test_technical_context_uses_ratio_not_average_share_volume(self):
        technical = {
            "RATIO": {
                "regularMarketPrice": 10,
                "volumeRatio20": 1.45,
                "vol20": 1_000_000,
            },
            "NO_RATIO": {
                "regularMarketPrice": 20,
                "vol20": 2_000_000,
            },
        }
        contexts = pr2._technical_contexts(
            technical,
            {
                "RATIO": {"ticker": "RATIO"},
                "NO_RATIO": {"ticker": "NO_RATIO"},
            },
        )
        self.assertEqual(contexts["RATIO"]["relative_volume"], 1.45)
        self.assertIsNone(contexts["NO_RATIO"]["relative_volume"])

    def test_stale_technical_scan_candidate_is_rejected(self):
        stale_date = (pr2.p0.now_et().date() - timedelta(days=pr2.MAX_TECHNICAL_AGE_DAYS + 1)).isoformat()
        events = pr2._technical_scan_candidates(
            [{"ticker": "STALE", "portfolio_status": "holding"}],
            {"STALE": {"score": 100, "signal": "BUY ZONE", "regularMarketTime": stale_date}},
        )
        self.assertEqual(events, [])

    def test_quiet_list_is_filled_only_to_configured_minimum(self):
        today = pr2.p0.now_et().date().isoformat()
        portfolio = [
            {"ticker": "A", "name": "A", "portfolio_status": "holding"},
            {"ticker": "B", "name": "B", "portfolio_status": "holding"},
            {"ticker": "C", "name": "C", "portfolio_status": "holding"},
            {"ticker": "D", "name": "D", "portfolio_status": "holding"},
        ]
        technical = {
            "A": {"score": 100, "signal": "BUY ZONE", "regularMarketTime": today},
            "B": {"score": 5, "signal": "SELL / Weak", "regularMarketTime": today},
            "C": {"score": 92, "signal": "Trend Confirmed", "regularMarketTime": today},
            "D": {"score": 55, "signal": "Neutral", "regularMarketTime": today},
        }
        portfolio_map = {row["ticker"]: row for row in portfolio}
        contexts = pr2._technical_contexts(technical, portfolio_map)
        merged, fill_count = pr2._add_technical_fill([], portfolio, technical, portfolio_map, contexts)
        self.assertEqual(fill_count, pr2.MIN_ATTENTION_ITEMS)
        self.assertEqual(len(merged), pr2.MIN_ATTENTION_ITEMS)
        self.assertEqual(len({event["ticker"] for event in merged}), pr2.MIN_ATTENTION_ITEMS)
        self.assertTrue(all(event["verification_status"] == "confirmed" for event in merged))

    def test_golden_contract_remains_backward_compatible(self):
        payload = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertTrue(str(payload.get("schema_version", "")).startswith("2.0"))
        self.assertIsInstance(payload.get("items"), list)
        item = payload["items"][0]
        for field in ("ticker", "priority", "why_today", "events", "source", "verification_status"):
            self.assertIn(field, item)


if __name__ == "__main__":
    unittest.main()
