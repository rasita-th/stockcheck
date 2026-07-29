import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.check_data_freshness import validate


class DataFreshnessTests(unittest.TestCase):
    def write(self, root: Path, payload: dict) -> Path:
        path = root / "data.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_accepts_recent_iso_dataset(self):
        now = datetime(2026, 7, 29, 7, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), {
                "generatedAtTechnical": "2026-07-29T06:55:00+00:00",
                "rows": [{"symbol": "NVDA"}],
            })
            result = validate(path, ["generatedAtTechnical"], 30, 1, now=now)
            self.assertEqual(result["row_count"], 1)

    def test_accepts_utc_timestamp_format(self):
        now = datetime(2026, 7, 29, 7, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), {
                "generatedAtFundamental": "2026-07-29 06:50:00 UTC",
                "count": 1,
                "rows": [{"symbol": "NVDA"}],
            })
            result = validate(path, ["generatedAtFundamental"], 30, 1, now=now)
            self.assertEqual(result["row_count"], 1)

    def test_rejects_stale_timestamp(self):
        now = datetime(2026, 7, 29, 7, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), {
                "generatedAt": "2026-07-27T19:21:51+00:00",
                "rows": [{}],
            })
            with self.assertRaisesRegex(ValueError, "STALE_GENERATED_DATA"):
                validate(path, ["generatedAt"], 30, 1, now=now)

    def test_rejects_empty_rows(self):
        now = datetime(2026, 7, 29, 7, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), {
                "generatedAt": now.isoformat(),
                "rows": [],
            })
            with self.assertRaisesRegex(ValueError, "INSUFFICIENT_GENERATED_ROWS"):
                validate(path, ["generatedAt"], 30, 1, now=now)


if __name__ == "__main__":
    unittest.main()
