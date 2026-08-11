from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LiveRefreshWatchdogWorkflowTests(unittest.TestCase):
    def test_watchdog_is_explicitly_receipt_chained_and_single_dispatch(self):
        workflow = (ROOT / ".github/workflows/live-refresh-watchdog.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("producer_run_id:", workflow)
        self.assertIn("getWorkflowRun", workflow)
        self.assertIn("actions: write", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn("listWorkflowRuns", workflow)
        self.assertIn("createWorkflowDispatch", workflow)
        self.assertIn("refresh-live-v9-1.yml", workflow)
        self.assertIn("scripts/live-refresh-watchdog.js", workflow)
        self.assertIn('cron: "13,33,53 * * * 1-5"', workflow)
        self.assertIn("timeout-minutes: 28", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("workflow_run:", workflow)

    def test_existing_producer_remains_the_only_live_data_producer(self):
        producer = (ROOT / ".github/workflows/refresh-live-v9-1.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("actions: write", producer)
        self.assertIn("contents: read", producer)
        self.assertIn("jobs:\n  admission:", producer)
        self.assertIn("Cancel a redundant delayed intraday schedule", producer)
        self.assertIn("scripts/live-refresh-dedupe.js", producer)
        self.assertIn("listWorkflowRuns", producer)
        self.assertIn("cancelWorkflowRun", producer)
        self.assertIn('workflow_id: "publish-production-data.yml"', producer)
        self.assertIn('workflow_id: "live-refresh-watchdog.yml"', producer)
        self.assertIn("needs: admission", producer)
        self.assertIn("if: needs.admission.outputs.run_refresh == 'true'", producer)
        self.assertIn("group: live-data-producer-main", producer)
        self.assertIn("cancel-in-progress: false", producer)
        self.assertNotIn("contents: write", producer)
        self.assertNotIn("git push", producer)

    def test_live_publisher_uses_a_verified_explicit_receipt(self):
        publisher = (ROOT / ".github/workflows/publish-production-data.yml").read_text(
            encoding="utf-8"
        )
        workflow_run_block = publisher.split("workflow_run:", 1)[1].split(
            "permissions:", 1
        )[0]
        self.assertNotIn("Refresh Live Data v10 PR3", workflow_run_block)
        self.assertIn("producer_run_id:", publisher)
        self.assertIn("getWorkflowRun", publisher)
        self.assertIn('run.name !== "Refresh Live Data v10 PR3"', publisher)
        self.assertIn("steps.source.outputs.run_id", publisher)


if __name__ == "__main__":
    unittest.main()
