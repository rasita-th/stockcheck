import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts.source_policy import (  # noqa: E402
    Decision,
    Domain,
    EvidenceKind,
    SourceClass,
    SourceDescriptor,
    allows,
    decide,
    describe_source,
)


class SourcePolicyContractTests(unittest.TestCase):
    def test_finnhub_is_an_estimate_for_earnings_and_rejected_from_today(self):
        descriptor = describe_source({"type": "Finnhub", "quality": "secondary"})
        self.assertEqual(descriptor.source_class, SourceClass.DISCOVERY)
        self.assertEqual(descriptor.evidence_kind, EvidenceKind.MARKET_ESTIMATE)
        self.assertEqual(decide(descriptor, Domain.EARNINGS_RADAR), Decision.ALLOW_ESTIMATED)
        self.assertEqual(decide(descriptor, Domain.TODAY_CATALYST), Decision.REJECT)

    def test_primary_company_and_regulator_evidence_is_allowed_for_today(self):
        company = describe_source({"type": "company_ir", "quality": "primary"})
        regulator = describe_source({"type": "regulator", "quality": "primary"})
        self.assertEqual(decide(company, Domain.TODAY_CATALYST), Decision.ALLOW)
        self.assertEqual(decide(regulator, Domain.TODAY_CATALYST), Decision.ALLOW)

    def test_public_news_discovery_is_unverified_not_confirmed(self):
        descriptor = describe_source({"type": "GDELT", "quality": "discovery"})
        self.assertEqual(decide(descriptor, Domain.TODAY_CATALYST), Decision.ALLOW_UNVERIFIED)
        self.assertFalse(decide(descriptor, Domain.TODAY_CATALYST) is Decision.ALLOW)

    def test_internal_technical_evidence_only_enters_technical_watch(self):
        descriptor = describe_source({"type": "technical_json", "quality": "internal"})
        self.assertEqual(decide(descriptor, Domain.TECHNICAL_WATCH), Decision.ALLOW_INTERNAL_ONLY)
        self.assertEqual(decide(descriptor, Domain.TODAY_CATALYST), Decision.REJECT)
        self.assertEqual(decide(descriptor, Domain.EARNINGS_RADAR), Decision.REJECT)

    def test_unknown_source_fails_closed_for_every_domain(self):
        descriptor = describe_source({"type": "new-provider-without-policy"})
        self.assertEqual(descriptor.source_class, SourceClass.UNKNOWN)
        for domain in Domain:
            self.assertEqual(decide(descriptor, domain), Decision.REJECT)
            self.assertFalse(allows(decide(descriptor, domain)))

    def test_explicit_canonical_fields_win_over_legacy_mapping(self):
        descriptor = describe_source(
            {
                "type": "finnhub",
                "provider": "verified-exchange-feed",
                "source_class": "primary",
                "evidence_kind": "official_record",
            }
        )
        self.assertEqual(
            descriptor,
            SourceDescriptor(
                provider="verified-exchange-feed",
                source_class=SourceClass.PRIMARY,
                evidence_kind=EvidenceKind.OFFICIAL_RECORD,
            ),
        )
        self.assertEqual(decide(descriptor, Domain.TODAY_CATALYST), Decision.ALLOW)

    def test_invalid_canonical_fields_do_not_fall_back_to_provider_guessing(self):
        descriptor = describe_source(
            {
                "provider": "company_ir",
                "source_class": "trusted-ish",
                "evidence_kind": "press-ish",
            }
        )
        self.assertEqual(descriptor.source_class, SourceClass.UNKNOWN)
        self.assertEqual(descriptor.evidence_kind, EvidenceKind.UNKNOWN)
        self.assertEqual(decide(descriptor, Domain.TODAY_CATALYST), Decision.REJECT)


if __name__ == "__main__":
    unittest.main()
