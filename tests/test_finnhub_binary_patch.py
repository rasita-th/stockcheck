from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class FinnhubBinaryPatchTests(unittest.TestCase):
    def git(self, root: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            text=True,
            capture_output=capture,
        )

    def write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_large_legacy_migration_uses_applyable_binary_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.git(root, "init", "-q")
            self.git(root, "config", "user.name", "test")
            self.git(root, "config", "user.email", "test@example.com")

            attributes = "\n".join([
                "data/finnhub/state.json binary",
                "/data/finnhub_features.json binary",
                "/site/data/finnhub_features.json binary",
                "/static/data/finnhub_features.json binary",
                "/data/generated/finnhub_features.json binary",
                "",
            ])
            (root / ".gitattributes").write_text(attributes, encoding="utf-8")

            repeated = [{"ticker": f"T{i:04d}", "payload": "x" * 2048} for i in range(1500)]
            legacy = {"schema_version": "1.0.0", "endpoints": {"basic_financials": repeated}}
            legacy_paths = [
                root / "data/finnhub/state.json",
                root / "data/finnhub_features.json",
                root / "site/data/finnhub_features.json",
                root / "static/data/finnhub_features.json",
                root / "data/generated/finnhub_features.json",
            ]
            for path in legacy_paths:
                self.write_json(path, legacy)

            self.git(root, "add", ".")
            self.git(root, "commit", "-qm", "legacy")
            base = self.git(root, "rev-parse", "HEAD", capture=True).stdout.strip()

            (root / "data/finnhub/state.json").unlink()
            compact = {"schema_version": "1.1.0", "features": {"basic_financials": {}}}
            for path in legacy_paths[1:]:
                self.write_json(path, compact)
            self.write_json(
                root / "data/finnhub/state/index.json",
                {"schema_version": "2.0.0", "endpoints": {}, "batch": {}, "runs": []},
            )
            self.git(root, "add", "-N", "data/finnhub/state")

            patch_path = root / "migration.patch"
            result = self.git(root, "diff", "--binary", "HEAD", "--", ".", capture=True)
            patch_path.write_text(result.stdout, encoding="utf-8")

            self.assertIn("GIT binary patch", result.stdout)
            self.assertIn("data/finnhub/state/index.json", result.stdout)
            self.assertLess(patch_path.stat().st_size, 5 * 1024 * 1024)

            clone = Path(tmp) / "clone"
            self.git(Path(tmp), "clone", "-q", str(root), str(clone))
            self.git(clone, "checkout", "-q", base)
            subprocess.run(
                ["git", "apply", "--check", str(patch_path)],
                cwd=clone,
                check=True,
            )
            subprocess.run(
                ["git", "apply", str(patch_path)],
                cwd=clone,
                check=True,
            )
            self.assertFalse((clone / "data/finnhub/state.json").exists())
            self.assertTrue((clone / "data/finnhub/state/index.json").exists())
            self.assertEqual(
                json.loads((clone / "data/finnhub_features.json").read_text(encoding="utf-8"))["schema_version"],
                "1.1.0",
            )


if __name__ == "__main__":
    unittest.main()
