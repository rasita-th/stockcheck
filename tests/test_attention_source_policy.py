import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_attention_pr3 import _attention_eligible_events  # noqa: E402


class AttentionSourcePolicyTests(unittest.TestCase):
    def test_finnhub_discovery_rows_do_not_enter_attention_events(self):
        finnhub = {
            "event_id": "earnings:TEST:2026-08-05",
            "ticker": "TEST",
            "event_type": "earnings",
            "source": {"type": "Finnhub", "quality": "secondary"},
        }
        company_ir = {
            "event_id": "earnings:KEEP:2026-08-05",
            "ticker": "KEEP",
            "event_type": "earnings",
            "source": {"type": "company_ir", "quality": "primary", "url": "https://example.com"},
        }
        technical = {
            "event_id": "technical:KEEP:price-move:2026-08-04",
            "ticker": "KEEP",
            "event_type": "technical",
            "source": {"type": "technical_json", "quality": "internal"},
        }

        result = _attention_eligible_events([finnhub, company_ir, technical])

        self.assertEqual([event["event_id"] for event in result], [company_ir["event_id"], technical["event_id"]])

    def test_source_filter_is_case_insensitive(self):
        rows = [
            {"event_id": "one", "source": {"type": "fInNhUb"}},
            {"event_id": "two", "source": {"type": "regulator"}},
        ]
        self.assertEqual([event["event_id"] for event in _attention_eligible_events(rows)], ["two"])


if __name__ == "__main__":
    unittest.main()
