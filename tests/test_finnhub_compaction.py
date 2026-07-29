from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compact = load_module("compact_finnhub_state", ROOT / "scripts" / "compact_finnhub_state.py")
sizes = load_module("check_generated_file_sizes", ROOT / "scripts" / "check_generated_file_sizes.py")


class FinnhubCompactionTests(unittest.TestCase):
    def test_basic_financials_drops_unknown_metrics_and_limits_history(self):
        payload = {
            "symbol": "NVDA",
            "metric": {
                "peBasicExclExtraTTM": 20,
                "roeTTM": 0.42,
                "unknownMetric": 999,
            },
            "series": {
                "quarterly": {
                    "revenue": [
                        {"period": f"2024-Q{i}", "v": i}
                        for i in range(1, 13)
                    ],
                    "unknownSeries": [{"period": "2024-Q1", "v": 1}],
                }
            },
        }
        result = compact.compact_basic_financials(payload)
        self.assertEqual(set(result["metric"]), {"peBasicExclExtraTTM", "roeTTM"})
        self.assertEqual(len(result["series"]["quarterly"]), 8)
        self.assertFalse(any(row["metric"] == "unknownSeries" for row in result["series"]["quarterly"]))

    def test_compact_state_is_idempotent_and_prunes_old_removed_ticker(self):
        state = {
            "schema_version": "1.0.0",
            "endpoints": {
                "basic_financials": {
                    "NVDA": {
                        "status": "ok",
                        "updated_at": "2026-07-27T00:00:00+00:00",
                        "data": {"metric": {"roeTTM": 0.4, "junk": 1}},
                    },
                    "OLD": {
                        "status": "ok",
                        "updated_at": "2020-01-01T00:00:00+00:00",
                        "data": {"metric": {"roeTTM": 0.1}},
                    },
                }
            },
            "runs": list(range(40)),
        }
        first = compact.compact_state(state, {"NVDA"})
        second = compact.compact_state(first, {"NVDA"})
        self.assertNotIn("OLD", first["endpoints"]["basic_financials"])
        self.assertEqual(first["endpoints"], second["endpoints"])
        self.assertEqual(len(first["runs"]), 20)

    def test_public_projection_omits_runs_and_batch(self):
        state = compact.compact_state({
            "endpoints": {
                "price_target": {
                    "NVDA": {"status": "ok", "updated_at": "2026-07-27T00:00:00+00:00", "data": {"targetMean": 100}}
                }
            },
            "batch": {"internal": {"status": "ok"}},
            "runs": [{"secret": "diagnostic"}],
        }, {"NVDA"})
        projection = compact.public_projection(state, {"NVDA"})
        self.assertNotIn("runs", projection)
        self.assertNotIn("batch", projection)
        self.assertEqual(projection["features"]["price_target"]["NVDA"]["data"]["targetMean"], 100)

    def test_size_guard_rejects_oversized_finnhub_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_root = sizes.ROOT
            try:
                sizes.ROOT = Path(tmp)
                path = sizes.ROOT / "data" / "finnhub" / "state.json"
                path.parent.mkdir(parents=True)
                path.write_bytes(b"x" * (15 * sizes.MIB + 1))
                with self.assertRaises(SystemExit) as ctx:
                    sizes.inspect(["data/finnhub/state.json"])
                self.assertIn("REJECTED_FILE_TOO_LARGE", str(ctx.exception))
            finally:
                sizes.ROOT = old_root

    def test_patch_override_is_scoped_and_does_not_change_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_root = sizes.ROOT
            try:
                sizes.ROOT = Path(tmp)
                path = sizes.ROOT / "publish-artifact" / "production-data.patch"
                path.parent.mkdir(parents=True)
                path.write_bytes(b"x" * (45 * sizes.MIB))
                with self.assertRaises(SystemExit):
                    sizes.inspect(["publish-artifact/production-data.patch"])
                sizes.inspect(
                    ["publish-artifact/production-data.patch"],
                    patch_hard_limit_mib=50,
                )
            finally:
                sizes.ROOT = old_root


if __name__ == "__main__":
    unittest.main()
