import importlib.util
import json
import sys
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

P0_PATH = ROOT / "scripts" / "generate_attention_p0.py"
spec = importlib.util.spec_from_file_location("attention_p0_pr4", P0_PATH)
p0 = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(p0)

import attention_sources.pipeline as pipeline  # noqa: E402


class AttentionPR4ReliabilityTests(unittest.TestCase):
    def setUp(self):
        p0._SEC_BLOCKED_HOSTS.clear()

    def test_http_wrappers_execute_their_expected_transport(self):
        with patch.object(p0, "_pace_sec_request"), patch.object(p0.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b'{"ok": true}'
            self.assertEqual(p0.http_json("https://data.sec.gov/test.json"), {"ok": True})
        with patch.object(p0, "_pace_sec_request"), patch.object(p0.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b"<feed />"
            self.assertEqual(p0.http_bytes("https://www.sec.gov/test.atom"), b"<feed />")

    def test_sec_ticker_map_bootstraps_from_versioned_registry(self):
        registry = {
            "items": {
                "RKLB": {
                    "status": "applicable",
                    "cik": "0001819994",
                    "verified_at": "2026-08-12",
                }
            }
        }
        with patch.object(p0, "http_json", return_value=None):
            mapping, status = p0.fetch_sec_ticker_map({}, registry=registry)
        self.assertEqual(status, "registry")
        self.assertEqual(mapping["RKLB"]["cik_str"], "0001819994")
        self.assertEqual(mapping["RKLB"]["identity_status"], "verified_registry")

    def test_non_issuer_is_not_reported_as_cik_error(self):
        events, state, status, error = p0.fetch_sec_events(
            {"ticker": "JEPQ"},
            {"JEPQ": {"status": "not_applicable", "reason": "ETF"}},
            {},
        )
        self.assertEqual(events, [])
        self.assertEqual(status, "not_applicable")
        self.assertIsNone(error)
        self.assertEqual(state["identity_status"], "not_applicable")

    def test_sec_atom_transport_parses_important_filing(self):
        payload = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>8-K - Current report</title>
            <updated>2026-08-12T12:00:00-04:00</updated>
            <category term="8-K" />
            <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/1819994/000181999426000001/rklb-8k.htm" />
            <id>urn:tag:sec.gov,2008:accession-number=0001819994-26-000001</id>
          </entry>
        </feed>"""
        rows = p0.parse_sec_atom(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["form"], "8-K")
        self.assertEqual(rows[0]["accessionNumber"], "0001819994-26-000001")
        self.assertEqual(rows[0]["primaryDocument"], "rklb-8k.htm")

    def test_sec_registry_covers_every_portfolio_identity(self):
        registry = json.loads((ROOT / "data" / "sec_registry.json").read_text(encoding="utf-8"))
        expected = {
            "RKLB", "AMZN", "HOOD", "NVDA", "IREN", "ASTS", "OKLO", "TSLA",
            "GOOGL", "BMNR", "NBIS", "TEM", "MP", "IONQ", "AMD", "ORCL", "EQT",
            "TMDX", "EOSE", "PLTR", "UUUU", "PSIX", "CIFR", "RXRX", "JEPQ",
            "SYM", "TMC", "OSCR", "COPX", "RR", "ZETA", "OPEN", "COST", "BEAM",
            "NOW", "TE", "NASA", "INDI",
        }
        self.assertEqual(set(registry["items"]), expected)
        self.assertTrue(all(
            entry.get("status") == "not_applicable" or str(entry.get("cik", "")).isdigit()
            for entry in registry["items"].values()
        ))

    def test_required_filing_forms_have_stable_classification(self):
        expected = {
            "8-K": "current_report",
            "10-Q": "periodic_report",
            "6-K": "foreign_issuer_report",
            "4": "insider_activity",
            "S-3": "capital_raise",
        }
        for form, subtype in expected.items():
            with self.subTest(form=form):
                self.assertEqual(p0.classify_sec_filing(form)["subtype"], subtype)

    def test_sec_ticker_map_falls_back_to_last_verified_cik(self):
        state = {"tickers": {"RKLB": {"cik": "0001819994", "last_successful_check": "2026-08-11T00:00:00+00:00"}}}
        with patch.object(p0, "http_json", return_value=None):
            mapping, status = p0.fetch_sec_ticker_map(state)
        self.assertEqual(status, "cached")
        self.assertEqual(mapping["RKLB"]["cik_str"], "0001819994")

    def test_sec_event_uses_last_verified_cik_when_live_map_is_unavailable(self):
        submissions = {"filings": {"recent": {"form": [], "accessionNumber": [], "filingDate": []}}}
        with patch.object(p0, "http_json", return_value=submissions):
            events, state, status, error = p0.fetch_sec_events(
                {"ticker": "RKLB"},
                {},
                {"cik": "0001819994", "seen_accessions": []},
            )
        self.assertEqual(events, [])
        self.assertEqual(status, "ok")
        self.assertIsNone(error)
        self.assertEqual(state["cik"], "0001819994")

    def test_sec_transport_circuit_breaker_stops_repeating_blocked_host(self):
        denied = urllib.error.HTTPError(
            "https://data.sec.gov/submissions/test.json", 403, "Forbidden", {}, None
        )
        with patch.object(p0, "_pace_sec_request"), patch.object(
            p0.urllib.request, "urlopen", side_effect=denied
        ) as urlopen:
            self.assertIsNone(p0.http_json("https://data.sec.gov/submissions/one.json"))
            self.assertIsNone(p0.http_json("https://data.sec.gov/submissions/two.json"))
        self.assertEqual(urlopen.call_count, 1)

    def test_verified_finnhub_sec_index_is_used_when_official_transport_is_blocked(self):
        fallback = {
            "status": "ok",
            "updated_at": "2026-08-12T12:00:00+00:00",
            "data": [{
                "form": "8-K",
                "accessionNumber": "0001819994-26-000001",
                "filingDate": "2026-08-12",
                "acceptanceDateTime": "2026-08-12T16:05:00-04:00",
                "primaryDocument": "rklb-8k.htm",
                "items": "2.02",
                "reportDate": "2026-06-30",
                "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000001/rklb-8k.htm",
            }],
        }
        with (
            patch.object(p0, "http_json", return_value=None),
            patch.object(p0, "fetch_sec_atom", return_value=[]),
        ):
            events, state, status, error = p0.fetch_sec_events(
                {"ticker": "RKLB"},
                {"RKLB": {"cik_str": "0001819994", "identity_status": "verified_registry"}},
                {},
                fallback_entry=fallback,
            )
        self.assertEqual(status, "ok")
        self.assertIsNone(error)
        self.assertEqual(state["transport"], "finnhub_sec_index")
        self.assertEqual(events[0]["source"]["url"], fallback["data"][0]["sourceUrl"])
        self.assertEqual(events[0]["source"]["discovered_via"], "finnhub_sec_index")

    def test_invalid_discovery_link_cannot_claim_sec_coverage(self):
        fallback = {
            "status": "ok",
            "updated_at": "2026-08-12T12:00:00+00:00",
            "data": [{
                "form": "8-K",
                "accessionNumber": "0001819994-26-000001",
                "sourceUrl": "https://example.invalid/fake-filing",
            }],
        }
        with (
            patch.object(p0, "http_json", return_value=None),
            patch.object(p0, "fetch_sec_atom", return_value=[]),
        ):
            events, _state, status, error = p0.fetch_sec_events(
                {"ticker": "RKLB"},
                {"RKLB": {"cik_str": "0001819994"}},
                {},
                fallback_entry=fallback,
            )
        self.assertEqual(events, [])
        self.assertEqual(status, "error")
        self.assertIn("unavailable", error)

    def test_optional_gdelt_failure_does_not_downgrade_verified_ir(self):
        now = datetime(2026, 8, 12, 4, 0, tzinfo=timezone.utc)
        with (
            patch.object(pipeline, "collect_ir", return_value=([], {"seen_urls": []}, "ok", None)),
            patch.object(pipeline, "collect_gdelt", return_value=([], {}, "error", "GDELT response unavailable")),
        ):
            result = pipeline.collect_news_events(
                portfolio=[{"ticker": "RKLB", "name": "Rocket Lab", "company_ir_url": "https://investors.rocketlabusa.com/"}],
                registry={"defaults": {"batch_size": 1}, "items": {}},
                old_state={},
                enabled=True,
                now=now,
            )
        self.assertEqual(result.health["news"]["status"], "ok")
        self.assertEqual(result.health["gdelt"]["status"], "optional_unavailable")
        self.assertEqual(result.health["gdelt"]["role"], "discovery_only")
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
