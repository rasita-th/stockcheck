from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException

from scripts import verify_drawdown_browser as verifier


class DrawdownBrowserVerifierTests(unittest.TestCase):
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
        driver.execute_script.assert_called_once_with(
            """
      const button = document.querySelector('[data-screener="momentum"]');
      if (!button) return false;
      button.click();
      return true;
    """
        )
        wait.until.assert_called_once()

    def test_fails_immediately_when_momentum_control_is_missing(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = False

        with self.assertRaisesRegex(AssertionError, 'Momentum screener control was not found'):
            verifier.select_momentum(driver, Mock())

    def test_momentum_active_query_does_not_retain_an_element(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = True

        self.assertTrue(verifier.momentum_active(driver))
        driver.find_element.assert_not_called()

    def test_scanner_snapshot_is_read_atomically_without_element_handles(self) -> None:
        driver = Mock()
        driver.execute_script.return_value = [
            {'visible': True, 'text': '-12.5%'},
            {'visible': False, 'text': '-31.0%'},
        ]

        self.assertEqual(
            verifier.read_items(driver, '#rows > [data-select]', '[data-drawdown-cell]'),
            [(True, 12.5), (False, 31.0)],
        )
        driver.find_elements.assert_not_called()

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
