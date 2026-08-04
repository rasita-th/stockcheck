import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts.attention_policy import evaluate_attention_event, filter_attention_events  # noqa: E402
from contracts.source_policy import Decision  # noqa: E402
import generate_attention_p4 as p4  # noqa: E402


class AttentionPolicyP4Tests(unittest.TestCase):
    def test_finnhub_market_estimate_is_rejected_from_today(self):
        event = {
            "event_id": "earnings:TEST:2026-08-10",
            "ticker": "TEST",
            "event_type": "earnings",
            "source": {"type": "finnhub"},
        }
        result = evaluate_attention_event(event)
        self.assertFalse(result.allowed)
        self.assertEqual(result.decision, Decision.REJECT)

    def test_company_ir_is_allowed_for_today(self):
        event = {
            "event_id": "earnings:TEST:confirmed",
            "ticker": "TEST",
            "event_type": "earnings",
            "source": {"type": "company_ir"},
        }
        result = evaluate_attention_event(event)
        self.assertTrue(result.allowed)
        self.assertEqual(result.decision, Decision.ALLOW)

    def test_internal_technical_is_allowed_only_in_technical_watch(self):
        event = {
            "event_id": "technical:TEST:risk",
            "ticker": "TEST",
            "event_type": "technical",
            "source": {"type": "technical_json"},
        }
        result = evaluate_attention_event(event)
        self.assertTrue(result.allowed)
        self.assertEqual(result.decision, Decision.ALLOW_INTERNAL_ONLY)

    def test_unknown_source_fails_closed(self):
        accepted, metrics = filter_attention_events([
            {"event_id": "unknown:TEST", "ticker": "TEST", "event_type": "earnings", "source": {"type": "mystery"}}
        ])
        self.assertEqual(accepted, [])
        self.assertEqual(metrics["rejected_events"], 1)
        self.assertEqual(metrics["reject_reasons"][0]["provider"], "mystery")

    def test_public_report_is_allowed_unverified(self):
        event = {
            "event_id": "news:TEST",
            "ticker": "TEST",
            "event_type": "news",
            "source": {"type": "gdelt"},
        }
        result = evaluate_attention_event(event)
        self.assertTrue(result.allowed)
        self.assertEqual(result.decision, Decision.ALLOW_UNVERIFIED)

    def test_complete_event_set_is_gated_before_section_build(self):
        events = [
            {
                "event_id": "news:TEST:retained",
                "ticker": "TEST",
                "event_type": "news",
                "source": {"type": "gdelt"},
            },
            {
                "event_id": "news:BAD:retained",
                "ticker": "BAD",
                "event_type": "news",
                "source": {"type": "mystery"},
            },
        ]
        captured = {}

        def fake_build_sections(filtered, *args, **kwargs):
            captured["events"] = filtered
            return (filtered, [], [], 0)

        with patch.object(p4, "_ORIGINAL_BUILD_SECTIONS", fake_build_sections):
            result = p4.build_sections_with_policy(events)

        self.assertEqual([event["event_id"] for event in captured["events"]], ["news:TEST:retained"])
        self.assertEqual(result[0][0]["attention_policy_decision"], "allow_unverified")
        self.assertEqual(p4._LAST_EVENT_METRICS["evaluated_events"], 2)
        self.assertEqual(p4._LAST_EVENT_METRICS["rejected_events"], 1)


if __name__ == "__main__":
    unittest.main()
