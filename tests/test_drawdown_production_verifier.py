from __future__ import annotations

import json
import unittest

from scripts import verify_drawdown_production as verifier


def snapshot() -> dict:
    row = {
        "symbol": "NVDA",
        "drawdown": {
            "schemaVersion": "1.0",
            "status": "complete",
            "currentPct": -8.5,
            "maxPct": -31.2,
            "daysSincePeak": 21,
            "observations": 251,
            "asOf": "2026-07-31",
        },
        "drawdownCurrentPct": -8.5,
        "drawdownMaxPct": -31.2,
        "drawdownDaysSincePeak": 21,
        "drawdownAsOf": "2026-07-31",
        "drawdownStatus": "complete",
    }
    return {
        "schema_version": "1.1",
        "contract": "canonical-screener-snapshot",
        "drawdown_schema_version": "1.0",
        "drawdown_available_count": 1,
        "drawdown_coverage": 1.0,
        "rows": [row],
    }


def payload(url: str) -> bytes:
    if "index.html" in url:
        return b'<script src="memo-only-fix.js?v=10.8.0"></script>'
    if "memo-only-fix.js" in url:
        return b'const DRAWDOWN_VERSION = "10.9.0"; drawdown-screener-v10-9.js?v=${DRAWDOWN_VERSION}'
    if "drawdown-screener-v10-9.js" in url:
        return b'const VERSION = "10.9.0"; dataset.drawdownScreener drawdownCurrentPct currentPct status === "unavailable"'
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
        value["rows"].extend(
            {
                "symbol": f"X{i}",
                "drawdown": {"status": "unavailable"},
                "drawdownCurrentPct": None,
                "drawdownStatus": "unavailable",
            }
            for i in range(4)
        )
        value["drawdown_coverage"] = 0.2
        with self.assertRaises(verifier.DrawdownVerificationError):
            verifier.validate_snapshot(value)

    def test_rejects_stale_loader_version(self) -> None:
        def stale(url: str) -> bytes:
            return payload(url).replace(b"10.9.0", b"10.8.0")

        with self.assertRaises(verifier.DrawdownVerificationError):
            verifier.verify_once("https://example.test", "1", fetcher=stale)


if __name__ == "__main__":
    unittest.main()
