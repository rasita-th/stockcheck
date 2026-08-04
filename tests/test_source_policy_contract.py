import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contracts.earnings_contract import (  # noqa: E402
    EARNINGS_ITEM_CONTRACT_VERSION,
    enrich_earnings_document,
    enrich_earnings_item,
)
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


class EarningsDualWriteContractTests(unittest.TestCase):
    def test_finnhub_row_preserves_legacy_fields_and_adds_estimated_policy(self):
        legacy = {
            "ticker": "NVDA",
            "earnings_date": "2026-08-26",
            "status": "estimated",
            "source_type": "finnhub",
            "source_url": None,
            "eps_estimate": 1.23,
            "note": "legacy note",
        }
        enriched = enrich_earnings_item(legacy, retrieved_at="2026-08-04T12:00:00+00:00")
        for key, value in legacy.items():
            self.assertEqual(enriched[key], value)
        self.assertEqual(enriched["contract_version"], EARNINGS_ITEM_CONTRACT_VERSION)
        self.assertEqual(enriched["identity"]["event_id"], "earnings:NVDA:2026-08-26")
        self.assertEqual(enriched["provenance"][0]["provider"], "finnhub")
        self.assertEqual(enriched["provenance"][0]["source_class"], "discovery")
        self.assertEqual(enriched["verification"]["level"], "estimated")
        self.assertEqual(enriched["domain_policy"]["earnings_radar"], "allow_estimated")
        self.assertEqual(enriched["domain_policy"]["today_catalyst"], "reject")

    def test_company_ir_confirmed_row_is_allowed_for_today(self):
        enriched = enrich_earnings_item(
            {
                "ticker": "TSLA",
                "earnings_date": "2026-07-22",
                "status": "confirmed",
                "source_type": "company_ir",
                "source_url": "https://example.com/ir",
            }
        )
        self.assertEqual(enriched["verification"]["level"], "confirmed")
        self.assertEqual(enriched["verification"]["confirmed_by"], ["company_ir"])
        self.assertEqual(enriched["domain_policy"]["earnings_radar"], "allow")
        self.assertEqual(enriched["domain_policy"]["today_catalyst"], "allow")

    def test_enrichment_is_idempotent(self):
        once = enrich_earnings_item(
            {
                "ticker": "AMD",
                "earnings_date": "2026-08-04",
                "status": "estimated",
                "source_type": "finnhub",
            },
            retrieved_at="2026-08-04T12:00:00+00:00",
        )
        twice = enrich_earnings_item(once, retrieved_at="2026-08-05T12:00:00+00:00")
        self.assertEqual(twice, once)

    def test_unknown_source_is_preserved_but_fails_closed(self):
        enriched = enrich_earnings_item(
            {
                "ticker": "TEST",
                "earnings_date": "2026-08-05",
                "status": "estimated",
                "source_type": "new_feed",
                "custom_legacy_field": "keep-me",
            }
        )
        self.assertEqual(enriched["custom_legacy_field"], "keep-me")
        self.assertEqual(enriched["provenance"][0]["source_class"], "unknown")
        self.assertEqual(enriched["domain_policy"]["earnings_radar"], "reject")
        self.assertEqual(enriched["domain_policy"]["today_catalyst"], "reject")

    def test_document_dual_write_preserves_root_schema_and_reports_metrics(self):
        payload = {
            "schema_version": "2.0",
            "updated_at": "2026-08-04T12:00:00+00:00",
            "policy": "legacy policy",
            "items": [
                {
                    "ticker": "NVDA",
                    "earnings_date": "2026-08-26",
                    "status": "estimated",
                    "source_type": "finnhub",
                },
                {
                    "ticker": "TSLA",
                    "earnings_date": "2026-07-22",
                    "status": "confirmed",
                    "source_type": "company_ir",
                },
            ],
        }
        enriched = enrich_earnings_document(payload)
        self.assertEqual(enriched["schema_version"], "2.0")
        self.assertEqual(enriched["policy"], "legacy policy")
        self.assertTrue(enriched["features"]["dual_write"])
        self.assertTrue(enriched["features"]["legacy_fields_preserved"])
        self.assertEqual(enriched["contract_metrics"]["item_count"], 2)
        self.assertEqual(enriched["contract_metrics"]["canonical_provenance_rows"], 2)
        self.assertEqual(enriched["contract_metrics"]["unknown_source_rows"], 0)


if __name__ == "__main__":
    unittest.main()
