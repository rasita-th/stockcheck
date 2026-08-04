import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_attention_pr3 import _hydrate_technical_watch_metrics  # noqa: E402


class AttentionTechnicalMetricHydrationTests(unittest.TestCase):
    def test_incomplete_legacy_event_uses_canonical_technical_snapshot(self):
        rows = [
            {
                "ticker": "CIFR",
                "relative_volume": 1.30,
                "events": [
                    {
                        "event_type": "technical",
                        "event_subtype": "technical_risk",
                        "rsi14": None,
                        "pct_vs_ema20": 0.0,
                        "pct_vs_ema200": 0.0,
                        "volume_ratio20": 1.30,
                    }
                ],
            }
        ]
        technical = {
            "CIFR": {
                "score": 100,
                "signal": "BUY ZONE / Trend Confirmed",
                "rsi14": 54.53,
                "pctVsEma20": 9.47,
                "pctVsEma200": 31.30,
                "volumeRatio20": 1.30,
            }
        }

        repaired = _hydrate_technical_watch_metrics(rows, technical)
        event = rows[0]["events"][0]

        self.assertEqual(repaired, 1)
        self.assertEqual(event["technical_score"], 100.0)
        self.assertEqual(event["technical_signal"], "BUY ZONE / Trend Confirmed")
        self.assertEqual(event["rsi14"], 54.53)
        self.assertEqual(event["pct_vs_ema20"], 9.47)
        self.assertEqual(event["pct_vs_ema200"], 31.30)
        self.assertEqual(event["technical_metrics_source"], "canonical_technical_snapshot")

    def test_valid_event_metrics_are_not_overwritten(self):
        rows = [
            {
                "ticker": "EOSE",
                "events": [
                    {
                        "event_type": "technical",
                        "rsi14": 42.0,
                        "pct_vs_ema20": -3.0,
                        "pct_vs_ema200": 12.0,
                    }
                ],
            }
        ]
        technical = {
            "EOSE": {
                "rsi14": 55.0,
                "pctVsEma20": 8.0,
                "pctVsEma200": 20.0,
            }
        }

        _hydrate_technical_watch_metrics(rows, technical)
        event = rows[0]["events"][0]

        self.assertEqual(event["rsi14"], 42.0)
        self.assertEqual(event["pct_vs_ema20"], -3.0)
        self.assertEqual(event["pct_vs_ema200"], 12.0)

    def test_nontechnical_items_are_ignored(self):
        rows = [{"ticker": "CIFR", "events": [{"event_type": "earnings"}]}]
        repaired = _hydrate_technical_watch_metrics(rows, {"CIFR": {"rsi14": 50}})
        self.assertEqual(repaired, 0)
        self.assertNotIn("rsi14", rows[0]["events"][0])


if __name__ == "__main__":
    unittest.main()
