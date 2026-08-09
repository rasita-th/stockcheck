from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import validate_fundamental_snapshot as contract


class FundamentalSnapshotContractTests(unittest.TestCase):
    def payload(self, generated: str, quarter: str = "Q2 2026") -> dict:
        row = {
            "symbol": "AMD",
            "latestQuarter": quarter,
            "periodEnd": "2026-06-30" if quarter == "Q2 2026" else "2026-03-31",
            "filedDate": "2026-08-04" if quarter == "Q2 2026" else "2026-05-06",
        }
        return {
            "generatedAtFundamental": generated,
            "count": 1,
            "rows": [row],
            "fundamentals": {"AMD": {"latest": row, "fundamental": row}},
        }

    def test_rejects_top_level_timestamp_rollback(self) -> None:
        current = self.payload("2026-08-09 10:00:00 UTC")
        candidate = self.payload("2026-08-08 10:00:00 UTC")
        with self.assertRaises(contract.FundamentalContractError):
            contract.validate_candidate(candidate, current)

    def test_rejects_ticker_period_rollback(self) -> None:
        current = self.payload("2026-08-08 10:00:00 UTC", "Q2 2026")
        candidate = self.payload("2026-08-09 10:00:00 UTC", "Q1 2026")
        with self.assertRaises(contract.FundamentalContractError):
            contract.validate_candidate(candidate, current)

    def test_requires_identical_canonical_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name for name in ("canonical.json", "site.json", "static.json")]
            paths[0].write_text('{"ok":true}\n', encoding="utf-8")
            paths[1].write_text('{"ok":true}\n', encoding="utf-8")
            paths[2].write_text('{"ok":false}\n', encoding="utf-8")
            with self.assertRaises(contract.FundamentalContractError):
                contract.validate_mirrors(paths)

    def test_fundamental_code_changes_trigger_the_owner_workflow(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "update-fundamental.yml").read_text(encoding="utf-8")
        for owned_path in (
            "sec_v1_fundamentals.py",
            "scripts/update_fundamental_data.py",
            "scripts/validate_fundamental_snapshot.py",
            ".github/workflows/update-fundamental.yml",
        ):
            self.assertIn(f'- "{owned_path}"', workflow)


if __name__ == "__main__":
    unittest.main()
