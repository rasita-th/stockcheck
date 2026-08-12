import importlib.util
import sys
import unittest
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
