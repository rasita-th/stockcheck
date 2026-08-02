from __future__ import annotations

import json
import unittest

from scripts import verify_drawdown_production as verifier


def snapshot() -> dict:
    row = {
        "symbol": "NVDA",
        "drawdown": {"status": "available", "currentPct": -8.5, "maxPct": -31.2, "daysSincePeak": 21},
        "drawdownCurrentPct": -8.5,
        "drawdownMaxPct": -31.2,
    }
    return {
        "schema_version": "1.1",
        "contract": "canonical-screener-snapshot",
        "drawdown": {"schema_version": "1.0", "available_count": 1, "coverage": 1.0},
        "rows": [row],
    }


def payload(url: str) -> bytes:
    if "index.html" in url:
        return b'drawdown-screener-v10-9.js?v=10.9.0'
    if "drawdown-screener-v10-9.js" in url:
        return b'data-drawdown-screener drawdownCurrentPct drawdownMaxPct unavailable'
    if "screener_snapshot.json" in url:
        return json.dumps(snapshot()).encode()
    raise AssertionError(url)


class DrawdownProductionVerifierTests(unittest.TestCase):
    def test_accepts_valid_production_contract(self) -> None:
        summary = verifier.verify_once("https://example.test", "1", fetcher=payload)
        self.assertEqual(summary["available_count"], 1)

    def test_rejects_legacy_schema(self) -> None:
        value = snapshot()
        value["schema_version"] = "1.0"
        with self.assertRaises(verifier.DrawdownVerificationError):
            verifier.validate_snapshot(value)

    def test_rejects_invalid_drawdown_domain(self) -> None:
        value = snapshot()
        value["rows"][0]["drawdown"]["maxPct"] = -5.0
        with self.assertRaises(verifier.DrawdownVerificationError):
            verifier.validate_snapshot(value)

    def test_rejects_low_coverage(self) -> None:
        value = snapshot()
        value["rows"].extend({"symbol": f"X{i}", "drawdown": {"status": "unavailable"}} for i in range(4))
        value["drawdown"]["coverage"] = 0.2
        with self.assertRaises(verifier.DrawdownVerificationError):
            verifier.validate_snapshot(value)

    def test_rejects_stale_runtime_reference(self) -> None:
        def stale(url: str) -> bytes:
            return payload(url).replace(b"v=10.9.0", b"v=10.8.0")
        with self.assertRaises(verifier.DrawdownVerificationError):
            verifier.verify_once("https://example.test", "1", fetcher=stale)


if __name__ == "__main__":
    unittest.main()
