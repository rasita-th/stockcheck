from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTopologyTests(unittest.TestCase):
    def make_checkout(self) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp_dir)
        shutil.copytree(ROOT / ".github" / "workflows", temp_dir / ".github" / "workflows")
        (temp_dir / "config").mkdir()
        shutil.copy2(ROOT / "config" / "release-manifest.json", temp_dir / "config" / "release-manifest.json")
        (temp_dir / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts" / "check_workflow_topology.py", temp_dir / "scripts" / "check_workflow_topology.py")
        shutil.copy2(ROOT / "scripts" / "verify_production_deployment.py", temp_dir / "scripts" / "verify_production_deployment.py")
        return temp_dir

    def run_check(self, checkout: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/check_workflow_topology.py"],
            cwd=checkout,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_repository_has_one_exact_commit_pages_dispatcher(self) -> None:
        result = self.run_check(self.make_checkout())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_pages_owner_is_rejected(self) -> None:
        checkout = self.make_checkout()
        shutil.copy2(
            ROOT / "tests" / "fixtures" / "workflow_topology" / "duplicate-deploy.yml",
            checkout / ".github" / "workflows" / "duplicate-deploy.yml",
        )
        result = self.run_check(checkout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Pages deploy owner must be exactly", result.stdout + result.stderr)

    def test_duplicate_pages_dispatcher_is_rejected(self) -> None:
        checkout = self.make_checkout()
        shutil.copy2(
            ROOT / "tests" / "fixtures" / "workflow_topology" / "duplicate-dispatch.yml",
            checkout / ".github" / "workflows" / "duplicate-dispatch.yml",
        )
        result = self.run_check(checkout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Pages dispatcher must be exactly", result.stdout + result.stderr)

    def test_deployer_must_dispatch_receipt_verifier_for_manual_runs(self) -> None:
        checkout = self.make_checkout()
        deployer = checkout / ".github" / "workflows" / "deploy-pages.yml"
        deployer.write_text(
            deployer.read_text(encoding="utf-8").replace(
                "gh workflow run verify-production-deployment.yml",
                "gh workflow run missing-verifier.yml",
            ),
            encoding="utf-8",
        )
        result = self.run_check(checkout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing single-trigger contract token", result.stdout + result.stderr)

    def test_manual_verifier_must_publish_receipt_bound_status(self) -> None:
        checkout = self.make_checkout()
        verifier = checkout / ".github" / "workflows" / "verify-production-deployment.yml"
        verifier.write_text(
            verifier.read_text(encoding="utf-8").replace(
                "if: always() && needs.identity.result == 'success'",
                "if: always() && github.event_name == 'workflow_run' && needs.identity.result == 'success'",
            ),
            encoding="utf-8",
        )
        result = self.run_check(checkout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing verifier contract token", result.stdout + result.stderr)

    def test_verifier_dispatch_must_name_repository_without_checkout(self) -> None:
        checkout = self.make_checkout()
        deployer = checkout / ".github" / "workflows" / "deploy-pages.yml"
        deployer.write_text(
            deployer.read_text(encoding="utf-8").replace(
                '--repo "$GITHUB_REPOSITORY"',
                "",
            ),
            encoding="utf-8",
        )
        result = self.run_check(checkout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing single-trigger contract token", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
