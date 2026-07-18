import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from attention_pr3 import enrich_payload  # noqa: E402
from attention_sources.regulators import collect_regulator_events  # noqa: E402

NOW = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)


def sample_payload(priority="Watch", price=100.0, event_count=1):
    events = [
        {
            "event_id": "earnings:TEST:2026-07-22:confirmed",
            "ticker": "TEST",
            "event_type": "earnings",
            "event_subtype": "earnings_upcoming",
            "event_time": "2026-07-22",
            "verification_status": "confirmed",
            "source": {"type": "company_ir", "quality": "primary", "url": "https://example.com/earnings"},
        }
    ]
    while len(events) < event_count:
        events.append({**events[0], "event_id": f"earnings:TEST:extra:{len(events)}"})
    return {
        "items": [
            {
                "ticker": "TEST",
                "name": "Test Company",
                "portfolio_status": "holding",
                "priority": priority,
                "priority_score": 50,
                "event_type": "earnings",
                "event_subtype": "earnings_upcoming",
                "event_time": "2026-07-22",
                "price": price,
                "events": events,
            }
        ],
        "technical_watch": [],
        "features": {},
    }


class AttentionPR3Tests(unittest.TestCase):
    def test_first_run_marks_item_new_and_applies_personal_score(self):
        output, state = enrich_payload(
            sample_payload(),
            {},
            {"holding_priority_boost": 8, "event_type_boosts": {"earnings": 7}},
            NOW,
        )
        item = output["items"][0]
        self.assertEqual(item["change"]["status"], "new")
        self.assertEqual(item["change"]["label_th"], "เพิ่มเข้ามาวันนี้")
        self.assertEqual(item["personal_priority_score"], 65)
        self.assertEqual(item["impact"]["change_pct"], 0.0)
        self.assertIn("earnings:TEST:2026-07-22:confirmed", state["items"])

    def test_second_run_tracks_impact_and_escalation(self):
        _, state = enrich_payload(sample_payload(priority="Watch", price=100), {}, {}, NOW)
        later = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)
        second, _ = enrich_payload(sample_payload(priority="Action", price=110), state, {}, later)
        item = second["items"][0]
        self.assertEqual(item["change"]["status"], "escalated")
        self.assertEqual(item["change"]["active_days"], 1)
        self.assertEqual(item["impact"]["change_pct"], 10.0)

    def test_more_events_marks_item_updated(self):
        _, state = enrich_payload(sample_payload(event_count=1), {}, {}, NOW)
        later = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)
        second, _ = enrich_payload(sample_payload(event_count=2), state, {}, later)
        self.assertEqual(second["items"][0]["change"]["status"], "updated")

    def test_missing_item_moves_to_recently_resolved(self):
        _, state = enrich_payload(sample_payload(), {}, {}, NOW)
        empty, _ = enrich_payload({"items": [], "technical_watch": [], "features": {}}, state, {}, NOW)
        self.assertEqual(empty["changes_summary"]["resolved"], 1)
        self.assertEqual(empty["recently_resolved"][0]["ticker"], "TEST")

    def test_regulator_bootstrap_then_new_matched_event(self):
        portfolio = [{"ticker": "RKLB", "name": "Rocket Lab USA, Inc."}]
        registry = {"items": {"RKLB": {"aliases": ["Rocket Lab"]}}}
        config = {
            "sources": {
                "FAA": {
                    "name": "Federal Aviation Administration",
                    "url": "https://www.faa.gov/newsroom/press_releases",
                    "mode": "page",
                }
            },
            "assignments": {"RKLB": ["FAA"]},
        }
        first_html = b'<html><a href="/newsroom/existing">FAA general update</a></html>'
        first = collect_regulator_events(
            portfolio, registry, config, {}, True, fetch_bytes_fn=lambda _: first_html, now=NOW
        )
        self.assertEqual(first.events, [])
        second_html = (
            b'<html>'
            b'<a href="/newsroom/existing">FAA general update</a>'
            b'<a href="/newsroom/rocket-lab-approval">FAA approval for Rocket Lab launch operations</a>'
            b'</html>'
        )
        second = collect_regulator_events(
            portfolio, registry, config, first.state, True, fetch_bytes_fn=lambda _: second_html, now=NOW
        )
        self.assertEqual(len(second.events), 1)
        event = second.events[0]
        self.assertEqual(event["ticker"], "RKLB")
        self.assertEqual(event["event_type"], "regulatory")
        self.assertEqual(event["verification_status"], "confirmed")
        self.assertEqual(event["source"]["quality"], "primary")
        self.assertEqual(event["regulator"], "FAA")


if __name__ == "__main__":
    unittest.main()
