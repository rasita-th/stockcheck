#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

PRESETS: dict[str, tuple[float, float]] = {
    "0-5": (0.0, 5.0),
    "5-15": (5.0, 15.0),
    "15-30": (15.0, 30.0),
    "30+": (30.0, float("inf")),
}


@dataclass(frozen=True)
class PresetResult:
    preset: str
    expected: int
    actual: int


def chrome() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    for flag in (
        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
        "--disable-background-networking", "--disable-default-apps", "--disable-extensions",
        "--disable-sync", "--metrics-recording-only", "--no-first-run", "--hide-scrollbars",
    ):
        options.add_argument(flag)
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    return webdriver.Chrome(options=options)


def parse_depth(text: str) -> float | None:
    match = re.search(r"-?([0-9]+(?:\.[0-9]+)?)%", text or "")
    return float(match.group(1)) if match else None


def read_items(driver: webdriver.Chrome, item_selector: str, metric_selector: str) -> list[tuple[bool, float]]:
    raw = driver.execute_script(
        """
        const itemSelector = arguments[0];
        const metricSelector = arguments[1];
        return [...document.querySelectorAll(itemSelector)].map(item => ({
          visible: !item.classList.contains('drawdown-filter-hidden'),
          metric: item.querySelector(metricSelector)?.textContent || ''
        }));
        """,
        item_selector,
        metric_selector,
    )
    result: list[tuple[bool, float]] = []
    for item in raw or []:
        value = parse_depth(str(item.get("metric") or ""))
        if value is None:
            raise AssertionError("Drawdown metric is unavailable in a production Scanner row/card")
        result.append((bool(item.get("visible")), value))
    return result


def reset_scanner_filters(driver: webdriver.Chrome) -> None:
    changed = driver.execute_script(
        """
        let count = 0;
        document.querySelectorAll('input[type="range"]').forEach(input => {
          input.value = input.min || '0';
          input.dispatchEvent(new Event('input', {bubbles: true}));
          input.dispatchEvent(new Event('change', {bubbles: true}));
          count += 1;
        });
        document.querySelectorAll('input[type="checkbox"]').forEach(input => {
          if (!['desktopDrawdownEnabled', 'sheetDrawdownEnabled'].includes(input.id) && input.checked) {
            input.click();
            count += 1;
          }
        });
        return count;
        """
    )
    if not changed:
        raise AssertionError("Scanner filter controls were not found for browser reset")


def expected_count(values: list[float], preset: str) -> int:
    minimum, maximum = PRESETS[preset]
    return sum(1 for value in values if minimum <= value < maximum)


def choose_presets(values: list[float]) -> list[str]:
    counts = {preset: expected_count(values, preset) for preset in PRESETS}
    candidates = [preset for preset, count in counts.items() if 0 < count < len(values)]
    if not candidates:
        raise AssertionError(f"No Drawdown preset produces a non-empty filtered subset: {counts}")
    first = candidates[0]
    second = next((preset for preset in candidates[1:] if counts[preset] != counts[first]), None)
    return [first] if second is None else [first, second]


def runtime_settings(driver: webdriver.Chrome) -> dict:
    return driver.execute_script(
        "return window.StockRadarDrawdownScreener?.settings || null"
    ) or {}


def visible_values(items: list[tuple[bool, float]]) -> list[float]:
    return [value for visible, value in items if visible]


def wait_for_items(driver: webdriver.Chrome, wait: WebDriverWait, item_selector: str, metric_selector: str) -> list[tuple[bool, float]]:
    wait.until(lambda current: len(read_items(current, item_selector, metric_selector)) > 0)
    return read_items(driver, item_selector, metric_selector)


def verify_presets(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    item_selector: str,
    metric_selector: str,
    control_root: str,
    values: list[float],
) -> list[PresetResult]:
    results: list[PresetResult] = []
    for preset in choose_presets(values):
        button = driver.find_element(By.CSS_SELECTOR, f'{control_root} [data-drawdown-preset="{preset}"]')
        driver.execute_script("arguments[0].click()", button)
        wait.until(lambda current, preset=preset: (
            runtime_settings(current).get("enabled") is True
            and runtime_settings(current).get("preset") == preset
        ))
        expected = expected_count(values, preset)
        wait.until(lambda current, expected=expected: len(visible_values(
            read_items(current, item_selector, metric_selector)
        )) == expected)
        filtered = read_items(driver, item_selector, metric_selector)
        actual_values = visible_values(filtered)
        minimum, maximum = PRESETS[preset]
        if not all(minimum <= value < maximum for value in actual_values):
            raise AssertionError(f"Preset {preset} exposed values outside its range: {actual_values[:12]}")
        results.append(PresetResult(preset, expected, len(actual_values)))
    return results


def prepare(driver: webdriver.Chrome, wait: WebDriverWait, url: str) -> None:
    driver.get(url)
    driver.execute_script("localStorage.clear(); sessionStorage.clear();")
    driver.refresh()
    wait.until(lambda current: current.execute_script(
        "return document.documentElement.dataset.drawdownScreener || ''"
    ) == "10.9.0")
    reset_scanner_filters(driver)


def run_desktop(base_url: str) -> dict:
    driver = chrome()
    driver.set_window_size(1440, 1000)
    wait = WebDriverWait(driver, 45)
    item_selector = "#technicalTableBody tr"
    metric_selector = "[data-drawdown-cell]"
    try:
        prepare(driver, wait, f"{base_url}/index.html?browser_smoke={int(time.time())}-desktop")
        baseline_items = wait_for_items(driver, wait, item_selector, metric_selector)
        baseline_values = visible_values(baseline_items)
        if len(baseline_values) != len(baseline_items):
            raise AssertionError("Desktop Drawdown filter should start disabled")
        driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "desktopDrawdownEnabled"))
        wait.until(lambda current: runtime_settings(current).get("enabled") is True)
        results = verify_presets(
            driver, wait, item_selector, metric_selector,
            '[data-drawdown-filter="desktop"]', baseline_values,
        )
        driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "desktopDrawdownEnabled"))
        wait.until(lambda current: runtime_settings(current).get("enabled") is False)
        wait.until(lambda current: len(visible_values(read_items(current, item_selector, metric_selector))) == len(baseline_values))
        return {
            "viewport": "desktop",
            "baseline": len(baseline_values),
            "presets": [asdict(result) for result in results],
            "runtime": driver.execute_script("return document.documentElement.dataset.drawdownScreener"),
        }
    except Exception:
        driver.save_screenshot("/tmp/drawdown-desktop-failure.png")
        raise
    finally:
        driver.quit()


def run_mobile(base_url: str) -> dict:
    driver = chrome()
    driver.set_window_size(390, 844)
    wait = WebDriverWait(driver, 45)
    item_selector = "#technicalMobileCards > *"
    metric_selector = "[data-drawdown-card-metric] strong"
    try:
        prepare(driver, wait, f"{base_url}/index.html?browser_smoke={int(time.time())}-mobile")
        baseline_items = wait_for_items(driver, wait, item_selector, metric_selector)
        baseline_values = visible_values(baseline_items)
        if len(baseline_values) != len(baseline_items):
            raise AssertionError("Mobile Drawdown filter should start disabled")
        driver.execute_script(
            "arguments[0].click()",
            driver.find_element(By.CSS_SELECTOR, '[data-open-panel="filters"]'),
        )
        wait.until(lambda current: current.find_element(By.ID, "filtersSheet").is_displayed())
        driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "sheetDrawdownEnabled"))
        wait.until(lambda current: runtime_settings(current).get("enabled") is True)
        results = verify_presets(
            driver, wait, item_selector, metric_selector,
            '[data-drawdown-filter="sheet"]', baseline_values,
        )
        driver.execute_script(
            "arguments[0].click()",
            driver.find_element(By.CSS_SELECTOR, "#filtersSheet [data-close-sheet]"),
        )
        wait.until(lambda current: not current.find_element(By.ID, "filtersSheet").is_displayed())
        return {
            "viewport": "mobile",
            "baseline": len(baseline_values),
            "presets": [asdict(result) for result in results],
            "runtime": driver.execute_script("return document.documentElement.dataset.drawdownScreener"),
        }
    except Exception:
        driver.save_screenshot("/tmp/drawdown-mobile-failure.png")
        raise
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    try:
        flows = [run_desktop(args.base_url.rstrip("/")), run_mobile(args.base_url.rstrip("/"))]
    except TimeoutException as exc:
        raise SystemExit(f"Production Drawdown browser smoke timed out: {exc}") from exc
    print(json.dumps({"status": "verified", "flows": flows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
