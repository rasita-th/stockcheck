import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("yfinance", MagicMock())

from scripts.generate_market_pulse import coverage_diagnostics
from scripts.validate_market_pulse import validate_diagnostics


def rows(symbols, missing=()):
    missing = set(missing)
    return [
        {
            "symbol": symbol,
            "status": "unavailable" if symbol in missing else "ok",
            "week_pct": None if symbol in missing else 1.0,
        }
        for symbol in symbols
    ]


class MarketPulseDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.globals = rows(["^GSPC", "^IXIC", "^N225", "^TOPX"])
        self.indices = rows(["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX"])
        self.sectors = rows(["XLK", "XLC", "XLY", "XLP", "XLF", "XLV", "XLI", "XLE"])
        self.themes = rows(["SMH", "IGV", "ITA", "URA", "IBB"])

    def diagnose(self, *, globals_=None, indices=None, sectors=None, themes=None):
        return coverage_diagnostics(
            globals_ if globals_ is not None else self.globals,
            indices if indices is not None else self.indices,
            sectors if sectors is not None else self.sectors,
            themes if themes is not None else self.themes,
        )

    def test_complete_coverage_allows_normal_signals(self):
        diagnostics = self.diagnose()
        self.assertEqual(diagnostics["usability"], "usable")
        self.assertEqual(diagnostics["signal_policy"], "generate")
        self.assertEqual(diagnostics["missing_symbols"], [])
        self.assertEqual(diagnostics["sources"][0]["status"], "ok")

    def test_missing_vix_explains_high_impact_caution(self):
        diagnostics = self.diagnose(indices=rows(
            ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX"],
            missing=["^VIX"],
        ))
        self.assertEqual(diagnostics["usability"], "caution")
        self.assertEqual(diagnostics["signal_policy"], "generate-with-caution")
        self.assertIn("^VIX", diagnostics["critical_missing_symbols"])
        component = diagnostics["components"]["us_indices"]
        self.assertEqual(component["impact"], "high")
        self.assertEqual(component["missing_symbols"], ["^VIX"])
        self.assertIn("^VIX", diagnostics["sources"][0]["failed_symbols"])

    def test_missing_most_sector_breadth_suppresses_signals(self):
        symbols = ["XLK", "XLC", "XLY", "XLP", "XLF", "XLV", "XLI", "XLE"]
        diagnostics = self.diagnose(sectors=rows(symbols, missing=symbols[:5]))
        self.assertEqual(diagnostics["usability"], "suppress")
        self.assertEqual(diagnostics["signal_policy"], "suppress")
        self.assertFalse(diagnostics["components"]["us_sectors"]["sufficient"])
        self.assertIn("sector breadth", diagnostics["conclusion_impact"].lower())

    def test_losing_both_primary_us_anchors_suppresses_signals(self):
        diagnostics = self.diagnose(indices=rows(
            ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX"],
            missing=["^GSPC", "^IXIC"],
        ))
        self.assertEqual(diagnostics["usability"], "suppress")
        self.assertCountEqual(diagnostics["critical_missing_symbols"], ["^GSPC", "^IXIC"])

    def test_schema_validator_accepts_consistent_partial_diagnostics(self):
        diagnostics = self.diagnose(indices=rows(
            ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX"],
            missing=["^VIX"],
        ))
        payload = {
            "schema_version": "3.1",
            "status": "partial",
            "diagnostics": diagnostics,
            "today_pulse": [{"symbol": "XLK"}],
            "narrative": {"signals_suppressed": False},
        }
        problems = []
        validate_diagnostics(payload, problems)
        self.assertEqual(problems, [])

    def test_schema_validator_rejects_signals_when_suppressed(self):
        symbols = ["XLK", "XLC", "XLY", "XLP", "XLF", "XLV", "XLI", "XLE"]
        diagnostics = self.diagnose(sectors=rows(symbols, missing=symbols[:5]))
        payload = {
            "schema_version": "3.1",
            "status": "partial",
            "diagnostics": diagnostics,
            "today_pulse": [{"symbol": "XLK"}],
            "narrative": {"signals_suppressed": False},
        }
        problems = []
        validate_diagnostics(payload, problems)
        self.assertTrue(any("today_pulse" in problem for problem in problems))
        self.assertTrue(any("signals_suppressed" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
