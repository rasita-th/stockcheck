import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts.earnings_reader import (  # noqa: E402
    CanonicalEarningsContractError,
    read_earnings_row,
    read_metrics,
)
from contracts.source_policy import Decision, Domain  # noqa: E402


def canonical_row(**overrides):
    row = {
        "symbol": "TEST",
        "source_type": "finnhub",
        "provenance": [
            {
                "contract_version": "1.0.0",
                "provider": "finnhub",
                "source_class": "discovery",
                "evidence_kind": "market_estimate",
            }
        ],
        "domain_policy": {
            "earnings_radar": "allow_estimated",
            "today_catalyst": "reject",
            "technical_watch": "reject",
        },
    }
    row.update(overrides)
    return row


class EarningsCanonicalOnlyP5Tests(unittest.TestCase):
    def test_canonical_row_reads_without_fallback(self):
        read = read_earnings_row(canonical_row(), Domain.EARNINGS_RADAR)
        self.assertEqual(read.mode, "canonical")
        self.assertEqual(read.decision, Decision.ALLOW_ESTIMATED)
        self.assertEqual(read.row["source_read_mode"], "canonical")
        self.assertEqual(read_metrics([read])["legacy_fallback_rows"], 0)

    def test_canonical_policy_controls_today(self):
        read = read_earnings_row(canonical_row(), Domain.TODAY_CATALYST)
        self.assertEqual(read.decision, Decision.REJECT)

    def test_legacy_only_row_fails_closed(self):
        with self.assertRaises(CanonicalEarningsContractError):
            read_earnings_row({"symbol": "OLD", "source_type": "finnhub"}, Domain.EARNINGS_RADAR)

    def test_missing_domain_policy_fails_closed(self):
        row = canonical_row()
        row.pop("domain_policy")
        with self.assertRaises(CanonicalEarningsContractError):
            read_earnings_row(row, Domain.EARNINGS_RADAR)

    def test_missing_target_decision_fails_closed(self):
        row = canonical_row(domain_policy={"today_catalyst": "reject"})
        with self.assertRaises(CanonicalEarningsContractError):
            read_earnings_row(row, Domain.EARNINGS_RADAR)

    def test_invalid_policy_decision_fails_closed(self):
        row = canonical_row(domain_policy={"earnings_radar": "maybe"})
        with self.assertRaises(CanonicalEarningsContractError):
            read_earnings_row(row, Domain.EARNINGS_RADAR)


if __name__ == "__main__":
    unittest.main()
