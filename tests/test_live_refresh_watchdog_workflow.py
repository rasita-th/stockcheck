from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LiveRefreshWatchdogWorkflowTests(unittest.TestCase):
    def test_watchdog_is_completion_chained_and_single_dispatch(self):
        workflow = (ROOT / ".github/workflows/live-refresh-watchdog.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('workflows: ["Refresh Live Data v10 PR3"]', workflow)
        self.assertIn("types: [completed]", workflow)
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
        self.assertIn("needs: admission", producer)
        self.assertIn("if: needs.admission.outputs.run_refresh == 'true'", producer)
        self.assertIn("group: live-data-producer-main", producer)
        self.assertIn("cancel-in-progress: false", producer)
        self.assertNotIn("contents: write", producer)
        self.assertNotIn("git push", producer)


if __name__ == "__main__":
    unittest.main()
