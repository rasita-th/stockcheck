from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from scripts import validate_production_artifact as contract


class ProductionArtifactContractTests(unittest.TestCase):
    def test_allowed_event_path(self) -> None:
        contract.validate_paths("Refresh Finnhub Earnings Events", ["data/earnings_calendar.json", "site/data/attention_today.json"])

    def test_allowed_live_data_paths(self) -> None:
        contract.validate_paths("Refresh Live Data v10 PR3", ["data/generated/attention_today.json", "data/source_state/attention.json", "site/data/technical.json", "static/data/scanner.json"])

    def test_live_data_cannot_publish_runtime_assets(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            contract.validate_paths("Refresh Live Data v10 PR3", ["static/attention-pr3.js"])
        self.assertIn("REJECTED_PATH", str(raised.exception))

    def test_market_pulse_paths_are_narrow(self) -> None:
        contract.validate_paths("Refresh Market Pulse v9.6", ["data/generated/market_pulse.json", "data/market_pulse.json", "site/data/market_pulse.json", "static/data/market_pulse.json"])
        with self.assertRaises(SystemExit) as raised:
            contract.validate_paths("Refresh Market Pulse v9.6", ["site/data/scanner.json"])
        self.assertIn("REJECTED_PATH", str(raised.exception))

    def test_consensus_paths_include_canonical_generated_projection(self) -> None:
        canonical = ["data/generated/recommendation_trends.json"]
        contract.validate_paths("Refresh Finnhub Analyst Features", canonical)
        contract.validate_paths("Refresh Finnhub Full Backfill", canonical)

    def test_fundamental_paths_are_narrow(self) -> None:
        self.assertIn("push", contract.PRODUCERS["Update static fundamental data"]["events"])
        contract.validate_paths(
            "Update static fundamental data",
            [
                "data/generated/fundamental.json",
                "site/data/fundamental.json",
                "static/data/fundamental.json",
            ],
        )
        with self.assertRaises(SystemExit) as raised:
            contract.validate_paths("Update static fundamental data", ["site/data/technical.json"])
        self.assertIn("REJECTED_PATH", str(raised.exception))

    def test_non_fundamental_producers_cannot_publish_fundamental_mirrors(self) -> None:
        fundamental_paths = (
            "data/generated/fundamental.json",
            "site/data/fundamental.json",
            "static/data/fundamental.json",
        )
        for producer in contract.PRODUCERS:
            if producer == "Update static fundamental data":
                continue
            for path in fundamental_paths:
                with self.subTest(producer=producer, path=path):
                    with self.assertRaises(SystemExit) as raised:
                        contract.validate_paths(producer, [path])
                    self.assertIn("REJECTED_PATH", str(raised.exception))

    def test_blocked_workflow_path(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            contract.validate_paths("Refresh Finnhub Earnings Events", [".github/workflows/deploy-pages.yml"])
        self.assertIn("REJECTED_PATH", str(raised.exception))

    def test_unknown_producer(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            contract.validate_paths("Unknown Producer", [])
        self.assertIn("REJECTED_UNKNOWN_PRODUCER", str(raised.exception))

    def test_hash_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "patch"
            path.write_bytes(b"immutable")
            self.assertEqual(contract.sha256(path), hashlib.sha256(b"immutable").hexdigest())

    def test_replay_is_successful_noop_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            data = root / "data"
            data.mkdir()
            target = data / "earnings_calendar.json"
            target.write_text('{"old": true}\n', encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            target.write_text('{"new": true}\n', encoding="utf-8")
            patch_path = root / "production-data.patch"
            patch_path.write_text(subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=root, text=True), encoding="utf-8")
            digest = contract.sha256(patch_path)
            metadata = {
                "schema_version": "2.0", "repository": contract.REPOSITORY,
                "producer": "Refresh Finnhub Earnings Events", "producer_run_id": "42",
                "producer_run_attempt": 1, "producer_event": "schedule", "producer_branch": "main",
                "producer_sha": "abc", "base_sha": "base", "produced_at": "2026-07-25T12:00:00+00:00",
                "patch_sha256": digest, "changed_paths": ["data/earnings_calendar.json"],
            }
            metadata_path = root / "metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            ledger_path = root / "ledger.json"
            ledger_path.write_text(json.dumps({"schema_version": "1.0", "producers": {"Refresh Finnhub Earnings Events": {"last_run_id": 42, "last_run_attempt": 1, "last_patch_sha256": digest, "last_produced_at": "2026-07-25T12:00:00+00:00"}}}), encoding="utf-8")
            output_path = root / "outputs"
            args = Namespace(patch=str(patch_path), metadata=str(metadata_path), ledger=str(ledger_path), repository=contract.REPOSITORY, workflow_name="Refresh Finnhub Earnings Events", run_id="42", run_attempt="1", source_sha="abc", branch="main", event="schedule")
            previous = Path.cwd()
            os.chdir(root)
            try:
                with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
                    contract.validate_artifact(args)
            finally:
                os.chdir(previous)
            self.assertIn("status=SKIPPED_REPLAY", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
