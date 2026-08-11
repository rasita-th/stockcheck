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

    def test_refreshes_price_event_semantics_and_nested_technical_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            technical = root / "technical.json"
            attention = root / "attention.json"
            technical.write_text(json.dumps({
                "rows": [{
                    "symbol": "TEM",
                    "price": 54.58,
                    "dayPct": 6.4563,
                    "volumeRatio20": 0.83,
                    "score": 78,
                    "rsi14": 61.2,
                    "pctVsEma20": 4.5,
                    "pctVsEma200": 16.0,
                    "signal": "BUY ZONE / Trend Confirmed",
                }],
            }), encoding="utf-8")
            attention.write_text(json.dumps({
                "technical_summary": {"risk": 0, "setup": 0, "total": 1},
                "technical_watch": [{
                    "ticker": "TEM",
                    "portfolio_status": "holding",
                    "priority": "Action",
                    "priority_score": 67,
                    "personal_priority_score": 75,
                    "severity": "medium",
                    "event_type": "technical",
                    "event_subtype": "price_move",
                    "primary_trigger": "price_move",
                    "why_today": ["The stock moved +7.2% today."],
                    "signals": ["The stock moved +7.2% today."],
                    "events": [{
                        "event_id": "technical:TEM:price-move:2026-08-10",
                        "event_type": "technical",
                        "event_subtype": "price_move",
                        "headline": "Price +7.2%",
                        "why_today": "The stock moved +7.2% today.",
                        "materiality": "medium",
                        "urgency": "today",
                        "verification_status": "confirmed",
                        "source": {"quality": "internal"},
                        "priority": "Action",
                        "priority_score": 67,
                    }],
                }],
            }), encoding="utf-8")

            self.assertEqual(sync_paths(technical, (attention,)), 1)

            item = json.loads(attention.read_text(encoding="utf-8"))["technical_watch"][0]
            event = item["events"][0]
            self.assertEqual(event["headline"], "Price +6.5%")
            self.assertEqual(event["why_today"], "The stock moved +6.5% today.")
            self.assertEqual(item["why_today"], [event["why_today"]])
            self.assertEqual(item["signals"], [event["why_today"]])
            self.assertEqual(event["materiality"], "medium")
            self.assertEqual(event["technical_score"], 78.0)
            self.assertEqual(event["technical_signal"], "BUY ZONE / Trend Confirmed")
            self.assertEqual(event["rsi14"], 61.2)
            self.assertEqual(event["pct_vs_ema20"], 4.5)
            self.assertEqual(event["pct_vs_ema200"], 16.0)
            self.assertEqual(event["volume_ratio20"], 0.83)
            self.assertEqual(item["priority_score"], 75)
            self.assertEqual(item["priority"], "Risk")
            self.assertEqual(item["personal_priority_score"], 83)

    def test_removes_stale_price_watch_below_large_move_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            technical = root / "technical.json"
            attention = root / "attention.json"
            technical.write_text(json.dumps({
                "rows": [{"symbol": "TEM", "price": 50.0, "dayPct": 4.99}],
            }), encoding="utf-8")
            attention.write_text(json.dumps({
                "technical_summary": {"risk": 1, "setup": 0, "total": 1},
                "technical_watch": [{
                    "ticker": "TEM",
                    "event_subtype": "price_drop",
                    "events": [{
                        "event_id": "technical:TEM:price-drop:2026-08-10",
                        "event_type": "technical",
                        "event_subtype": "price_drop",
                    }],
                }],
            }), encoding="utf-8")

            self.assertEqual(sync_paths(technical, (attention,)), 1)

            payload = json.loads(attention.read_text(encoding="utf-8"))
            self.assertEqual(payload["technical_watch"], [])
            self.assertEqual(payload["technical_summary"], {"risk": 0, "setup": 0, "total": 0})

    def test_updates_price_event_identity_when_direction_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            technical = root / "technical.json"
            attention = root / "attention.json"
            technical.write_text(json.dumps({
                "rows": [{"symbol": "TEM", "price": 60.0, "dayPct": 8.5}],
            }), encoding="utf-8")
            attention.write_text(json.dumps({
                "technical_watch": [{
                    "ticker": "TEM",
                    "portfolio_status": "holding",
                    "priority_score": 75,
                    "personal_priority_score": 83,
                    "events": [{
                        "event_id": "technical:TEM:price-drop:2026-08-10",
                        "event_type": "technical",
                        "event_subtype": "price_drop",
                        "materiality": "medium",
                        "urgency": "today",
                        "verification_status": "confirmed",
                        "source": {"quality": "internal"},
                    }],
                }],
            }), encoding="utf-8")

            self.assertEqual(sync_paths(technical, (attention,)), 1)

            item = json.loads(attention.read_text(encoding="utf-8"))["technical_watch"][0]
            event = item["events"][0]
            self.assertEqual(event["event_id"], "technical:TEM:price-move:2026-08-10")
            self.assertEqual(event["event_subtype"], "price_move")
            self.assertEqual(item["event_subtype"], "price_move")
            self.assertEqual(event["materiality"], "high")
            self.assertEqual(item["priority"], "Critical")

    def test_single_publisher_ci_paths_cover_synchronizer_and_test(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "validate-single-publisher.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(workflow.count('      - "scripts/sync_attention_market_fields.py"'), 2)
        self.assertEqual(workflow.count('      - "tests/test_sync_attention_market_fields.py"'), 2)


if __name__ == "__main__":
    unittest.main()
