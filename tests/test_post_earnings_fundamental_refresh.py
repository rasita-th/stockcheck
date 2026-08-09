from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

from scripts.update_fundamental_data import merge_targeted_snapshot, select_post_earnings_symbols


class PostEarningsFundamentalRefreshTests(unittest.TestCase):
    def test_owner_workflow_has_targeted_post_earnings_cadence(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "update-fundamental.yml").read_text(encoding="utf-8")

        self.assertIn('cron: "47 */6 * * *"', workflow)
        self.assertIn("targeted-post-earnings", workflow)
        self.assertIn("steps.generate.outputs.changed", workflow)

    def test_selects_only_recent_past_events_on_the_watchlist(self) -> None:
        calendar = {
            "items": [
                {"ticker": "AMD", "earnings_date": "2026-08-04"},
                {"ticker": "HOOD", "earnings_date": "2026-08-09"},
                {"ticker": "HOOD", "earnings_date": "2026-08-09"},
                {"ticker": "NVDA", "earnings_date": "2026-08-10"},
                {"ticker": "OLD", "earnings_date": "2026-07-01"},
                {"ticker": "NOPE", "earnings_date": "2026-08-08"},
            ]
        }

        selected = select_post_earnings_symbols(
            ["AMD", "HOOD", "NVDA", "OLD"],
            calendar,
            as_of=dt.date(2026, 8, 9),
            lookback_days=7,
        )

        self.assertEqual(selected, ["AMD", "HOOD"])

    def test_targeted_merge_replaces_targets_and_preserves_other_rows(self) -> None:
        current = {
            "generatedAtFundamental": "2026-08-09 00:00:00 UTC",
            "count": 2,
            "watchlist": ["AMD", "NVDA"],
            "rows": [
                {"symbol": "AMD", "latestQuarter": "Q1 2026", "fundamentalScore": 40},
                {"symbol": "NVDA", "latestQuarter": "Q1 2027", "fundamentalScore": 80},
            ],
            "fundamentals": {
                "AMD": {"latest": {"symbol": "AMD", "latestQuarter": "Q1 2026"}},
                "NVDA": {"latest": {"symbol": "NVDA", "latestQuarter": "Q1 2027"}},
            },
            "errors": [{"symbol": "OLD", "error": "old"}],
        }
        refreshed_row = {"symbol": "AMD", "latestQuarter": "Q2 2026", "fundamentalScore": 60}
        refreshed_detail = {"symbol": "AMD", "latest": refreshed_row, "fundamental": refreshed_row}

        merged = merge_targeted_snapshot(
            current,
            refreshed_rows=[refreshed_row],
            refreshed_fundamentals={"AMD": refreshed_detail},
            refreshed_symbols=["AMD"],
            errors=[],
            generated_at="2026-08-09 06:00:00 UTC",
            duration_seconds=12.5,
        )

        by_symbol = {row["symbol"]: row for row in merged["rows"]}
        self.assertEqual(by_symbol["AMD"]["latestQuarter"], "Q2 2026")
        self.assertEqual(by_symbol["NVDA"]["latestQuarter"], "Q1 2027")
        self.assertEqual(merged["count"], 2)
        self.assertEqual(merged["refreshMode"], "targeted-post-earnings")
        self.assertEqual(merged["refreshedSymbols"], ["AMD"])


if __name__ == "__main__":
    unittest.main()
