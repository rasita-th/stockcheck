from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException

from scripts import verify_drawdown_browser as verifier


class DrawdownBrowserVerifierTests(unittest.TestCase):
    def test_failure_evidence_survives_screenshot_failure(self) -> None:
        driver = Mock()
        driver.get_log.return_value = [{'level': 'SEVERE', 'message': 'fixture failure'}]
        driver.save_screenshot.side_effect = RuntimeError('browser closed')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(verifier, 'browser_diagnostics', return_value={'settings': {'preset': '5-15'}}),
                patch.object(verifier, 'Path', side_effect=lambda path: root / Path(path).name),
            ):
                verifier.save_failure_evidence(driver, 'desktop')
            diagnostics = json.loads((root / 'drawdown-desktop-failure-diagnostics.json').read_text())
            console = json.loads((root / 'drawdown-desktop-failure-console.json').read_text())
        self.assertEqual(diagnostics['settings']['preset'], '5-15')
        self.assertEqual(console[0]['level'], 'SEVERE')

    def test_momentum_selector_covers_desktop_and_mobile_navigation_owners(self) -> None:
        self.assertIn('[data-screener="momentum"]', verifier.MOMENTUM_CONTROL_SELECTOR)
        self.assertIn('[data-v80-screener="momentum"]', verifier.MOMENTUM_CONTROL_SELECTOR)
        self.assertIn('[data-v71-screener="momentum"]', verifier.MOMENTUM_CONTROL_SELECTOR)

    def test_scanner_selectors_exclude_empty_state_elements(self) -> None:
        self.assertEqual(
            verifier.DESKTOP_ITEM_SELECTOR,
            '#technicalTableBody tr[data-select]',
        )
        self.assertEqual(
            verifier.MOBILE_ITEM_SELECTOR,
            '#technicalMobileCards > [data-select]',
        )

    def test_selects_momentum_as_deterministic_dataset(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = True
        wait = Mock()

        verifier.select_momentum(driver, wait)

        driver.find_element.assert_not_called()
        driver.execute_script.assert_not_called()
        self.assertEqual(wait.until.call_count, 2)

    def test_missing_momentum_control_reports_a_named_wait_stage(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = {'activeScreener': '', 'runtime': '10.9.1'}
        wait = Mock()
        wait.until.side_effect = TimeoutException('')

        with self.assertRaisesRegex(verifier.BrowserStageTimeout, 'render and select Momentum control'):
            verifier.select_momentum(driver, wait)

    def test_momentum_click_can_retry_until_the_control_exists(self) -> None:
        driver = Mock()
        driver.execute_script.side_effect = [False, True]

        self.assertFalse(verifier.click_momentum_if_present(driver))
        self.assertTrue(verifier.click_momentum_if_present(driver))
        driver.find_element.assert_not_called()
        self.assertTrue(all(call.args[-1] == verifier.MOMENTUM_CONTROL_SELECTOR for call in driver.execute_script.call_args_list))

    def test_momentum_active_query_does_not_retain_an_element(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = True

        self.assertTrue(verifier.momentum_active(driver))
        driver.find_element.assert_not_called()

    def test_scanner_snapshot_is_read_atomically_without_element_handles(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = [
            {'visible': True, 'text': '-12.5%', 'currentPct': -12.5},
            {'visible': False, 'text': '-31.0%', 'currentPct': -31.0},
        ]

        self.assertEqual(
            verifier.read_items(driver, '#rows > [data-select]', '[data-drawdown-cell]'),
            [(True, 12.5), (False, 31.0)],
        )
        driver.find_elements.assert_not_called()

    def test_preset_expectations_use_unrounded_canonical_depth(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = [
            {'visible': True, 'text': '-15.0%', 'currentPct': -14.99},
            {'visible': False, 'text': '-15.0%', 'currentPct': -15.0},
            {'visible': False, 'text': '-5.0%', 'currentPct': -4.99},
        ]
        items = verifier.read_items(driver, '#rows', '[data-dd]')
        self.assertEqual(verifier.expected_count([value for _, value in items], '5-15'), 1)
        self.assertEqual(items, [(True, 14.99), (False, 15.0), (False, 4.99)])

    def test_missing_or_invalid_canonical_metric_cannot_pass(self) -> None:
        for current in (None, True, '14.99', float('nan'), float('inf')):
            with self.subTest(current=current):
                driver = Mock()
                driver.execute_script.return_value = [{'visible': True, 'text': '-15.0%', 'currentPct': current}]
                with self.assertRaisesRegex(AssertionError, 'Canonical Drawdown metric'):
                    verifier.read_items(driver, '#rows', '[data-dd]')

    def test_stale_rendered_metric_cannot_pass_with_valid_canonical_metric(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = [{'visible': True, 'text': '-12.0%', 'currentPct': -14.99}]
        with self.assertRaisesRegex(AssertionError, 'disagrees with canonical depth'):
            verifier.read_items(driver, '#rows', '[data-dd]')

    def test_preset_wait_retries_a_partial_scanner_snapshot(self) -> None:
        with patch.object(
            verifier,
            'read_items',
            side_effect=[
                AssertionError('Drawdown metric is unavailable'),
                [(True, 12.5), (False, 31.0)],
            ],
        ):
            self.assertFalse(verifier.read_matching_preset_snapshot(Mock(), '#rows', '[data-dd]', 1))
            self.assertEqual(
                verifier.read_matching_preset_snapshot(Mock(), '#rows', '[data-dd]', 1),
                [(True, 12.5), (False, 31.0)],
            )

    def test_stage_wait_reports_the_failed_stage(self) -> None:
        wait = Mock()
        wait.until.side_effect = TimeoutException('')
        driver = Mock()
        driver.execute_script.return_value = {
            'activeScreener': 'default',
            'desktopRows': 1,
            'mobileCards': 1,
            'runtime': '10.9.1',
        }

        with self.assertRaisesRegex(
            verifier.BrowserStageTimeout,
            'select Momentum dataset.*activeScreener.*default',
        ):
            verifier.wait_stage(driver, wait, 'select Momentum dataset', lambda _: False)


if __name__ == '__main__':
    unittest.main()
