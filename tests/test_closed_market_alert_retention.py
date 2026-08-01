from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClosedMarketAlertRetentionContractTest(unittest.TestCase):
    def test_runtime_keeps_latest_session_alerts_after_close(self) -> None:
        site = (ROOT / "site" / "technical-shards-v2.js").read_text(encoding="utf-8")
        static = (ROOT / "static" / "technical-shards-v2.js").read_text(encoding="utf-8")
        for runtime in (site, static):
            self.assertIn("function snapshotCanDriveAlerts", runtime)
            self.assertIn("if (session.marketOpen) return false", runtime)
            self.assertIn("session.businessDay ? 18 * 60 : 72 * 60", runtime)
            self.assertIn("!snapshotCanDriveAlerts()", runtime)
            self.assertNotIn("!snapshotIsFresh()) return []", runtime)

    def test_runtime_mirrors_share_alert_contract(self) -> None:
        site = (ROOT / "site" / "technical-shards-v2.js").read_text(encoding="utf-8")
        static = (ROOT / "static" / "technical-shards-v2.js").read_text(encoding="utf-8")
        for token in (
            "snapshotCanDriveAlerts",
            "Latest completed market session",
            "ตลาดปิด · คง alerts จาก session ล่าสุด",
        ):
            self.assertIn(token, site)
            self.assertIn(token, static)


if __name__ == "__main__":
    unittest.main()
