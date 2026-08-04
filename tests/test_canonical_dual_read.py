import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_earnings_radar_p3 as radar_p3  # noqa: E402
import generate_attention_pr3_p3 as attention_p3  # noqa: E402


class CanonicalFirstDualReadTests(unittest.TestCase):
    def setUp(self):
        radar_p3.READ_METRICS.clear()
        attention_p3.READ_METRICS.clear()

    def test_radar_prefers_canonical_provenance(self):
        row = {
            "ticker": "NVDA",
            "earnings_date": "2026-08-26",
            "status": "estimated",
            "source_type": "legacy-wrong",
            "provenance": [{"provider": "finnhub", "source_class": "discovery", "evidence_kind": "market_estimate"}],
            "domain_policy": {"earnings_radar": "allow_estimated"},
            "verification": {"level": "estimated"},
        }
        item = radar_p3.normalize_official_row(row)
        self.assertEqual(item["source_type"], "finnhub")
        self.assertEqual(item["contract_read_path"], "canonical")
        self.assertEqual(radar_p3.READ_METRICS["canonical_rows"], 1)

    def test_radar_legacy_fallback_is_observable(self):
        item = radar_p3.normalize_official_row({
            "ticker": "TSLA", "earnings_date": "2026-07-22", "status": "confirmed", "source_type": "company_ir"
        })
        self.assertEqual(item["contract_read_path"], "legacy_fallback")
        self.assertEqual(radar_p3.READ_METRICS["legacy_fallback_rows"], 1)

    def test_attention_prefers_canonical_and_counts_fallback(self):
        rows = [
            {
                "ticker": "NVDA", "earnings_date": __import__("datetime").date(2026, 8, 26), "status": "estimated",
                "source_type": "legacy-wrong",
                "provenance": [{"provider": "finnhub", "source_class": "discovery", "evidence_kind": "market_estimate"}],
                "domain_policy": {"today_catalyst": "reject"},
                "verification": {"level": "estimated"},
            },
            {"ticker": "TSLA", "earnings_date": __import__("datetime").date(2026, 7, 22), "status": "confirmed", "source_type": "company_ir"},
        ]
        with mock.patch.object(attention_p3, "_ORIGINAL_LOAD", return_value=rows):
            output = attention_p3.load_earnings_calendar()
        self.assertEqual(output[0]["source_type"], "finnhub")
        self.assertEqual(output[0]["contract_read_path"], "canonical")
        self.assertEqual(output[1]["contract_read_path"], "legacy_fallback")
        self.assertEqual(attention_p3.READ_METRICS["canonical_rows"], 1)
        self.assertEqual(attention_p3.READ_METRICS["legacy_fallback_rows"], 1)


if __name__ == "__main__":
    unittest.main()
