from __future__ import annotations

import json
import unittest
import urllib.error

from scripts import verify_production_deployment as verifier


MANIFEST = {
    "schema_version": "1.0",
    "release": "10.7.1",
    "production_base_url": "https://example.test/stockcheck",
    "assets": {
        "memo_only_fix_js": "10.7.1",
        "memo_only_fix_css": "10.7.1",
        "attention_pr4_js": "10.7.1",
        "attention_pr4_css": "10.4.4",
        "earnings_radar_pr4_js": "10.7.1",
        "earnings_radar_pr4_css": "10.5.1",
    },
    "data_contracts": {"attention_today": "3.0", "earnings_radar": "1.0"},
}
RECEIPT = {
    "status": "verified",
    "production_smoke_passed": True,
    "asset_version": "10.7.1",
    "source_commit": "abcdef1234567890",
}


def valid_payload(url: str) -> bytes:
    if "index.html" in url:
        return b'memo-only-fix.js?v=10.7.1 memo-only-fix.css?v=10.7.1'
    if "memo-only-fix.js" in url:
        return b'attention-pr4.js?v=10.7.1 earnings-radar-pr4.js?v=10.7.1'
    if "memo-only-fix.css" in url:
        return b'attention-pr4.css?v=10.4.4 earnings-radar-pr4.css?v=10.5.1'
    if "attention_today" in url:
        return json.dumps({"contract_version": "3.0.1", "items": [], "technical_watch": []}).encode()
    if "earnings_radar" in url:
        return json.dumps({"schema_version": "1.0", "items": [], "daily_summary": []}).encode()
    raise AssertionError(url)


class ProductionVerifierTests(unittest.TestCase):
    def test_identity_accepts_verified_receipt(self) -> None:
        self.assertEqual(verifier.validate_identity(MANIFEST, RECEIPT), "https://example.test/stockcheck")

    def test_identity_rejects_release_mismatch_without_network(self) -> None:
        receipt = dict(RECEIPT, asset_version="10.8.0")
        with self.assertRaises(verifier.VerificationError):
            verifier.validate_identity(MANIFEST, receipt)

    def test_successful_public_contract(self) -> None:
        verifier.verify_once("https://example.test/stockcheck", MANIFEST, "1", fetcher=valid_payload)

    def test_stale_asset_is_rejected(self) -> None:
        def stale(url: str) -> bytes:
            payload = valid_payload(url)
            return payload.replace(b"attention-pr4.js?v=10.7.1", b"attention-pr4.js?v=10.6.0")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify_once("https://example.test/stockcheck", MANIFEST, "1", fetcher=stale)

    def test_invalid_json_is_retried_then_succeeds(self) -> None:
        calls = {"attention": 0}
        def flaky(url: str) -> bytes:
            if "attention_today" in url:
                calls["attention"] += 1
                if calls["attention"] == 1:
                    return b"not-json"
            return valid_payload(url)
        verifier.verify_with_retries("https://example.test/stockcheck", MANIFEST, 2, 0, fetcher=flaky, sleeper=lambda _: None)
        self.assertEqual(calls["attention"], 2)

    def test_transient_network_failure_is_retried(self) -> None:
        state = {"calls": 0}
        def flaky(url: str) -> bytes:
            state["calls"] += 1
            if state["calls"] == 1:
                raise urllib.error.URLError("temporary")
            return valid_payload(url)
        verifier.verify_with_retries("https://example.test/stockcheck", MANIFEST, 2, 0, fetcher=flaky, sleeper=lambda _: None)
        self.assertGreater(state["calls"], 1)


if __name__ == "__main__":
    unittest.main()
