import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts.attention_policy import evaluate_attention_event, filter_attention_events  # noqa: E402
from contracts.source_policy import Decision  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
