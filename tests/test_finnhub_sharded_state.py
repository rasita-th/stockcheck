from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "finnhub_sharded_state.py"
spec = importlib.util.spec_from_file_location("finnhub_sharded_state", MODULE_PATH)
assert spec and spec.loader
store = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = store
spec.loader.exec_module(store)


class FinnhubShardedStateTests(unittest.TestCase):
    def sample_state(self):
        return {
            "schema_version": "1.0.0",
            "updated_at": "2026-07-28T00:00:00+00:00",
            "endpoints": {
                "recommendation_trends": {
                    "NVDA": {"status": "ok", "updated_at": "2026-07-28T00:00:00+00:00", "data": [{"buy": 1}]},
                    "AMZN": {"status": "empty", "updated_at": "2026-07-28T00:00:00+00:00", "data": []},
                },
                "price_target": {
                    "NVDA": {"status": "ok", "updated_at": "2026-07-28T00:00:00+00:00", "data": {"targetMean": 200}},
                },
            },
            "batch": {"earnings_calendar": {"status": "ok", "updated_at": "2026-07-28T00:00:00+00:00", "data": []}},
            "runs": [{"mode": "analyst"}],
        }

    def configure(self, root: Path):
        finnhub = root / "data" / "finnhub"
        return mock.patch.multiple(
            store,
            ROOT=root,
            FINNHUB_DIR=finnhub,
            LEGACY_PATH=finnhub / "state.json",
            SHARD_ROOT=finnhub / "state",
            INDEX_PATH=finnhub / "state" / "index.json",
        )

    def test_shard_then_hydrate_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp, self.configure(Path(tmp)):
            store.atomic_write(store.LEGACY_PATH, self.sample_state())
            result = store.shard_state(delete_legacy=True)
            self.assertTrue(result["legacy_deleted"])
            self.assertFalse(store.LEGACY_PATH.exists())
            self.assertTrue(store.INDEX_PATH.exists())
            self.assertTrue((store.SHARD_ROOT / "endpoints" / "recommendation_trends" / "NVDA.json").exists())
            store.hydrate_state()
            hydrated = json.loads(store.LEGACY_PATH.read_text(encoding="utf-8"))
            self.assertEqual(hydrated["endpoints"]["price_target"]["NVDA"]["data"]["targetMean"], 200)
            self.assertEqual(hydrated["batch"]["earnings_calendar"]["status"], "ok")

    def test_shard_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp, self.configure(Path(tmp)):
            stale = store.SHARD_ROOT / "endpoints" / "price_target" / "OLD.json"
            store.atomic_write(stale, {"status": "ok"})
            store.atomic_write(store.LEGACY_PATH, self.sample_state())
            result = store.shard_state(delete_legacy=False)
            self.assertGreaterEqual(result["removed_stale_shards"], 1)
            self.assertFalse(stale.exists())

    def test_hydrate_uses_legacy_when_index_missing(self):
        with tempfile.TemporaryDirectory() as tmp, self.configure(Path(tmp)):
            store.atomic_write(store.LEGACY_PATH, self.sample_state())
            result = store.hydrate_state()
            self.assertEqual(result["status"], "legacy")

    def test_rejects_path_escape_in_index(self):
        with tempfile.TemporaryDirectory() as tmp, self.configure(Path(tmp)):
            store.atomic_write(store.INDEX_PATH, {
                "schema_version": store.SCHEMA_VERSION,
                "endpoints": {"price_target": {"NVDA": "../../outside.json"}},
                "batch": {},
                "runs": [],
            })
            with self.assertRaises(ValueError):
                store.hydrate_state()

    def test_rejects_unsafe_ticker(self):
        with tempfile.TemporaryDirectory() as tmp, self.configure(Path(tmp)):
            state = self.sample_state()
            state["endpoints"]["price_target"]["../NVDA"] = state["endpoints"]["price_target"].pop("NVDA")
            store.atomic_write(store.LEGACY_PATH, state)
            with self.assertRaises(ValueError):
                store.shard_state(delete_legacy=False)


class FinnhubWorkflowContractTests(unittest.TestCase):
    def test_current_repository_rehearsal_is_shard_native(self):
        workflow = (MODULE_PATH.parents[1] / ".github" / "workflows" / "validate-finnhub-pipeline.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("Rehearse legacy-to-sharded migration on current data", workflow)
        self.assertIn("Rehearse shard-native Finnhub state round trip", workflow)
        self.assertIn("git diff --exit-code -- data/finnhub/state", workflow)

        round_trip = workflow.index("Rehearse shard-native Finnhub state round trip")
        lifecycle = workflow.index("Rehearse hydrated producer lifecycle")
        hydrate = workflow.index("finnhub_sharded_state.py hydrate", lifecycle)
        compact = workflow.index("compact_finnhub_state.py --write", lifecycle)
        shard = workflow.index("finnhub_sharded_state.py shard --delete-legacy", lifecycle)
        self.assertLess(round_trip, lifecycle)
        self.assertLess(hydrate, compact)
        self.assertLess(compact, shard)

        self.assertNotIn("Verify current migration patch transport budget", workflow)
        self.assertNotIn("Verify migration patch applies to a clean base", workflow)


if __name__ == "__main__":
    unittest.main()
