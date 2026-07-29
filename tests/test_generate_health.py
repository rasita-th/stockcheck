import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.generate_health import inspect, parse_dt


class GenerateHealthTests(unittest.TestCase):
    def test_parse_utc_suffix(self):
        parsed = parse_dt("2026-07-29 07:49:15 UTC")
        self.assertEqual(parsed, datetime(2026, 7, 29, 7, 49, 15, tzinfo=timezone.utc))

    def test_inspect_uses_fundamental_timestamp_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fundamental.json"
            path.write_text(json.dumps({
                "generatedAtFundamental": "2026-07-29 07:49:15 UTC",
                "count": 408,
            }), encoding="utf-8")
            with patch("scripts.generate_health.datetime") as mocked_datetime:
                mocked_datetime.now.return_value = datetime(2026, 7, 29, 8, 0, tzinfo=timezone.utc)
                mocked_datetime.fromisoformat = datetime.fromisoformat
                mocked_datetime.strptime = datetime.strptime
                result = inspect(path, 60)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["row_count"], 408)


if __name__ == "__main__":
    unittest.main()
