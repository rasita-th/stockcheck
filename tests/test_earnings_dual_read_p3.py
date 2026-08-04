import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts.earnings_reader import read_earnings_row, read_metrics  # noqa: E402
from contracts.source_policy import Decision, Domain  # noqa: E402


class EarningsDualReadP3Tests(unittest.TestCase):
    def test_canonical_fields_win_over_conflicting_legacy_source(self):
        row = {
            "ticker": "TEST",
            "earnings_date": "2026-08-20",
            "source_type": "finnhub",
            "provenance": [
                {
                    "contract_version": "1.0.0",
                    "provider": "company_ir",
                    "source_class": "primary",
                    "evidence_kind": "company_disclosure",
                }
            ],
            "domain_policy": {"today_catalyst": "allow"},
        }
        read = read_earnings_row(row, Domain.TODAY_CATALYST)
        self.assertEqual(read.mode, "canonical")
        self.assertEqual(read.provider, "company_ir")
        self.assertEqual(read.decision, Decision.ALLOW)
        self.assertEqual(read.row["source_read_mode"], "canonical")

    def test_legacy_row_falls_back_visibly(self):
        read = read_earnings_row(
            {"ticker": "TEST", "earnings_date": "2026-08-20", "source_type": "finnhub"},
            Domain.TODAY_CATALYST,
        )
        self.assertEqual(read.mode, "legacy_fallback")
        self.assertEqual(read.decision, Decision.REJECT)
        self.assertEqual(read.row["source_policy_decision"], "reject")

    def test_p3_observes_rejection_without_dropping_the_row(self):
        read = read_earnings_row(
            {
                "ticker": "TEST",
                "earnings_date": "2026-08-20",
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
                },
            },
            Domain.TODAY_CATALYST,
        )
        self.assertEqual(read.decision, Decision.REJECT)
        self.assertEqual(read.row["ticker"], "TEST")

    def test_metrics_separate_canonical_and_legacy_reads(self):
        reads = [
            read_earnings_row(
                {
                    "source_type": "company_ir",
                    "provenance": [
                        {
                            "contract_version": "1.0.0",
                            "provider": "company_ir",
                            "source_class": "primary",
                            "evidence_kind": "company_disclosure",
                        }
                    ],
                    "domain_policy": {"today_catalyst": "allow"},
                },
                Domain.TODAY_CATALYST,
            ),
            read_earnings_row({"source_type": "finnhub"}, Domain.TODAY_CATALYST),
        ]
        self.assertEqual(
            read_metrics(reads),
            {"rows": 2, "canonical_rows": 1, "legacy_fallback_rows": 1, "policy_reject_rows": 1},
        )


if __name__ == "__main__":
    unittest.main()
