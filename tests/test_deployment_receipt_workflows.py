from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'


class DeploymentReceiptWorkflowTests(unittest.TestCase):
    def read(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding='utf-8')

    def test_deployer_uploads_verified_exact_source_receipt(self) -> None:
        workflow = self.read('deploy-pages.yml')
        self.assertIn("'source_commit': os.environ['DEPLOY_SOURCE_COMMIT']", workflow)
        self.assertIn('production-deploy-receipt-${{ github.run_id }}', workflow)
        self.assertIn('actions/upload-artifact@v4', workflow)

    def test_unified_verifier_downloads_receipt_before_exact_checkout(self) -> None:
        workflow = self.read('verify-production-deployment.yml')
        self.assertNotIn('Derive deployment receipt from Pages event', workflow)
        self.assertIn('production-deploy-receipt-${{ steps.deploy.outputs.run_id }}', workflow)
        self.assertIn('ref: ${{ needs.identity.outputs.source_commit }}', workflow)
        self.assertNotIn('SOURCE_SHA: ${{ github.event.workflow_run.head_sha }}', workflow)

    def test_all_completion_consumers_use_receipt_identity(self) -> None:
        for name in ('report-pages-10-8.yml', 'verify-production-screener.yml'):
            workflow = self.read(name)
            self.assertIn('production-deploy-receipt-', workflow, name)
            self.assertNotIn('github.event.workflow_run.head_sha', workflow, name)


if __name__ == '__main__':
    unittest.main()
