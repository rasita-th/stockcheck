import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from attention_sources.pipeline import collect_news_events  # noqa: E402


class AttentionIrRegistryTests(unittest.TestCase):
    def setUp(self):
        self.portfolio = json.loads((ROOT / "data" / "portfolio.json").read_text(encoding="utf-8"))
        self.registry = json.loads((ROOT / "data" / "source_registry.json").read_text(encoding="utf-8"))

    def test_registry_covers_every_applicable_portfolio_identity(self):
        items = self.registry["items"]
        expected = {str(row["ticker"]).upper() for row in self.portfolio}
        self.assertEqual(set(items), expected)
        self.assertEqual(
            {ticker for ticker, entry in items.items() if entry.get("disabled")},
            {"JEPQ", "COPX", "NASA"},
        )
        configured = {
            ticker
            for ticker, entry in items.items()
            if not entry.get("disabled") and (entry.get("ir_urls") or entry.get("ir_feeds"))
        }
        self.assertEqual(configured, expected - {"JEPQ", "COPX", "NASA"})

    def test_official_ir_urls_are_https_and_match_explicit_domains(self):
        for ticker, entry in self.registry["items"].items():
            for url in entry.get("ir_urls") or []:
                parsed = urlparse(url)
                self.assertEqual(parsed.scheme, "https", ticker)
                self.assertTrue(parsed.hostname, ticker)
                allowed = entry.get("domains") or []
                self.assertTrue(
                    any(parsed.hostname == domain or parsed.hostname.endswith(f".{domain}") for domain in allowed),
                    f"{ticker}: {parsed.hostname} is outside {allowed}",
                )

    def test_health_exposes_registry_coverage_separately_from_live_batch(self):
        result = collect_news_events(
            self.portfolio,
            self.registry,
            {},
            True,
            fetch_json=lambda _: None,
            fetch_bytes_fn=lambda _: b"<html><body>official IR</body></html>",
            now=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(
            result.health["ir"]["registry"],
            {"applicable": 35, "configured": 35, "missing": 0, "not_applicable": 3},
        )
        self.assertEqual(result.health["ir"]["checked"], 10)
        self.assertEqual(result.health["ir"]["ok"], 10)


if __name__ == "__main__":
    unittest.main()
