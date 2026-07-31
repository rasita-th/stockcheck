from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ScreenerSnapshotArtifactContractTest(unittest.TestCase):
    def test_snapshot_mirrors_are_tracked_inputs(self) -> None:
        expected = (
            ROOT / "data" / "generated" / "screener_snapshot.json",
            ROOT / "site" / "data" / "screener_snapshot.json",
            ROOT / "static" / "data" / "screener_snapshot.json",
        )
        for path in expected:
            self.assertTrue(path.exists(), f"missing tracked snapshot mirror: {path}")

    def test_live_workflow_artifact_scope_includes_snapshot_directories(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "refresh-live-v9-1.yml").read_text(encoding="utf-8")
        for scope in ("data/generated", "site/data", "static/data"):
            self.assertIn(scope, workflow)


if __name__ == "__main__":
    unittest.main()
