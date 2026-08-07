import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import generate_health as health


class GenerateHealthTests(unittest.TestCase):
    def test_parse_utc_suffix(self):
        parsed = health.parse_dt("2026-07-29 07:49:15 UTC")
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
                result = health.inspect(path, 60)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["row_count"], 408)

    def test_market_pulse_ttl_covers_twelve_hour_schedule(self):
        self.assertEqual(health.FILES["market_pulse"][1], 13 * 60)

    def test_main_writes_byte_identical_health_mirrors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = root / "data" / "generated"
            generated.mkdir(parents=True)
            timestamp = datetime.now(timezone.utc).isoformat()
            for filename, _ttl in health.FILES.values():
                (generated / filename).write_text(
                    json.dumps({"generated_at": timestamp, "rows": [{"ticker": "TEST"}]}),
                    encoding="utf-8",
                )
            outputs = (
                generated / "health.json",
                root / "site" / "data" / "health.json",
                root / "static" / "data" / "health.json",
            )
            with patch.object(health, "DATA", generated), patch.object(health, "OUTPUTS", outputs):
                health.main()
            canonical = outputs[0].read_bytes()
            self.assertTrue(canonical)
            self.assertTrue(all(output.read_bytes() == canonical for output in outputs[1:]))


if __name__ == "__main__":
    unittest.main()
