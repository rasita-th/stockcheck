import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_attention_p0.py"
spec = importlib.util.spec_from_file_location("attention_p0", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


class AttentionP0Tests(unittest.TestCase):
    def test_sec_classification_capital_raise(self):
        self.assertEqual(mod.classify_sec_filing("S-3", "")["subtype"], "capital_raise")

    def test_sec_classification_earnings_8k(self):
        row = mod.classify_sec_filing("8-K", "2.02,9.01")
        self.assertEqual(row["event_type"], "earnings")
        self.assertEqual(row["subtype"], "earnings_reported")

    def test_zone_requires_crossing(self):
        stock = {"ticker": "TEST", "buy_zone": 100, "trim_zone": 120}
        no_cross = mod.technical_events(stock, {"price": 99, "previous_close": 98, "day_change_pct": 1})
        self.assertFalse(any(event["event_subtype"] == "buy_zone_cross" for event in no_cross))
        cross = mod.technical_events(stock, {"price": 99, "previous_close": 101, "day_change_pct": -2})
        self.assertTrue(any(event["event_subtype"] == "buy_zone_cross" for event in cross))

    def test_capital_raise_is_risk_for_holding(self):
        event = {"event_subtype": "capital_raise", "materiality": "high", "urgency": "today", "verification_status": "confirmed", "source": {"quality": "primary"}}
        stock = {"portfolio_status": "holding"}
        context = {"day_change_pct": -6}
        score = mod.event_score(event, stock, context)
        self.assertIn(mod.priority_label(event, score, stock, context), {"Critical", "Risk"})

    def test_aggregate_groups_events_by_ticker(self):
        stock = {"ticker": "TEST", "name": "Test Co", "portfolio_status": "holding", "exchange": "NASDAQ"}
        events = [
            {"event_id": "a", "ticker": "TEST", "event_type": "sec_filing", "event_subtype": "current_report", "headline": "8-K", "why_today": "New 8-K", "materiality": "medium", "urgency": "today", "verification_status": "confirmed", "source": {"quality": "primary", "url": "https://example.com"}},
            {"event_id": "b", "ticker": "TEST", "event_type": "technical", "event_subtype": "price_move", "headline": "Move", "why_today": "Price +5%", "materiality": "medium", "urgency": "today", "verification_status": "confirmed", "source": {"quality": "internal", "url": "data/technical.json"}},
        ]
        items = mod.aggregate_items(events, {"TEST": stock}, {"TEST": {"price": 10, "day_change_pct": 5}})
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0]["events"]), 2)


if __name__ == "__main__":
    unittest.main()
