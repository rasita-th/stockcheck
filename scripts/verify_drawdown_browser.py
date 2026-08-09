#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

PRESETS = {
    "0-5": (0.0, 5.0),
    "5-15": (5.0, 15.0),
    "15-30": (15.0, 30.0),
    "30+": (30.0, float("inf")),
}
EXPECTED_RUNTIME = "10.9.1"


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
    last_error: Exception | None = None
    for _ in range(20):
        try:
            result: list[tuple[bool, float]] = []
            for item in driver.find_elements(By.CSS_SELECTOR, item_selector):
                value = parse_depth(item.find_element(By.CSS_SELECTOR, metric_selector).text)
                if value is None:
                    raise AssertionError("Drawdown metric is unavailable in a production Scanner row/card")
                hidden = "drawdown-filter-hidden" in (item.get_attribute("class") or "").split()
                result.append((not hidden, value))
            return result
        except StaleElementReferenceException as exc:
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"Scanner kept re-rendering before a coherent DOM snapshot could be read: {last_error}")


def snapshot_ready(driver: webdriver.Chrome, item_selector: str, metric_selector: str) -> bool:
    try:
        return bool(read_items(driver, item_selector, metric_selector))
    except (AssertionError, StaleElementReferenceException):
        return False


def reset_scanner_filters(driver: webdriver.Chrome) -> None:
    changed = driver.execute_script("""
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
    """)
    if not changed:
        raise AssertionError("Scanner filter controls were not found for browser reset")


def visible_count(items: list[tuple[bool, float]]) -> int:
    return sum(1 for visible, _ in items if visible)


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


def wait_runtime(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    wait.until(lambda current: current.execute_script(
        "return document.documentElement.dataset.drawdownScreener || ''") == EXPECTED_RUNTIME)


def clear_storage(driver: webdriver.Chrome, url: str) -> None:
    driver.get(url)
    driver.execute_script("localStorage.clear(); sessionStorage.clear();")
    driver.refresh()


def verify_presets(driver, wait, item_selector, metric_selector, control_root, values):
    results: list[PresetResult] = []
    for preset in choose_presets(values):
        button = driver.find_element(By.CSS_SELECTOR, f'{control_root} [data-drawdown-preset="{preset}"]')
        driver.execute_script("arguments[0].click()", button)
        expected = expected_count(values, preset)
        wait.until(lambda current, expected=expected: visible_count(
            read_items(current, item_selector, metric_selector)) == expected)
        filtered = read_items(driver, item_selector, metric_selector)
        visible_values = [value for visible, value in filtered if visible]
        minimum, maximum = PRESETS[preset]
        if not all(minimum <= value < maximum for value in visible_values):
            raise AssertionError(f"Preset {preset} exposed values outside its range: {visible_values[:12]}")
        results.append(PresetResult(preset, expected, visible_count(filtered)))
    return results


def run_desktop(base_url: str) -> dict:
    driver = chrome(); driver.set_window_size(1440, 1000); wait = WebDriverWait(driver, 45)
    item_selector, metric_selector = "#technicalTableBody tr", "[data-drawdown-cell]"
    try:
        clear_storage(driver, f"{base_url}/index.html?browser_smoke={int(time.time())}-desktop")
        wait_runtime(driver, wait)
        reset_scanner_filters(driver)
        wait.until(lambda current: snapshot_ready(current, item_selector, metric_selector))
        baseline_items = read_items(driver, item_selector, metric_selector)
        baseline = visible_count(baseline_items); values = [value for _, value in baseline_items]
        if baseline != len(baseline_items):
            raise AssertionError(f"Desktop filter should start disabled: {baseline}/{len(baseline_items)} visible")
        driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "desktopDrawdownEnabled"))
        wait.until(lambda current: current.find_element(By.ID, "desktopDrawdownEnabled").is_selected())
        results = verify_presets(driver, wait, item_selector, metric_selector,
                                 '[data-drawdown-filter="desktop"]', values)
        driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "desktopDrawdownEnabled"))
        wait.until(lambda current: visible_count(read_items(current, item_selector, metric_selector)) == baseline)
        return {"viewport": "desktop", "baseline": baseline,
                "presets": [asdict(result) for result in results],
                "runtime": driver.execute_script("return document.documentElement.dataset.drawdownScreener")}
    except Exception:
        driver.save_screenshot("/tmp/drawdown-desktop-failure.png"); raise
    finally:
        driver.quit()


def run_mobile(base_url: str) -> dict:
    driver = chrome(); driver.set_window_size(390, 844); wait = WebDriverWait(driver, 45)
    item_selector, metric_selector = "#technicalMobileCards > *", "[data-drawdown-card-metric] strong"
    try:
        clear_storage(driver, f"{base_url}/index.html?browser_smoke={int(time.time())}-mobile")
        wait_runtime(driver, wait)
        reset_scanner_filters(driver)
        wait.until(lambda current: snapshot_ready(current, item_selector, metric_selector))
        baseline_items = read_items(driver, item_selector, metric_selector)
        baseline = visible_count(baseline_items); values = [value for _, value in baseline_items]
        if baseline != len(baseline_items):
            raise AssertionError(f"Mobile filter should start disabled: {baseline}/{len(baseline_items)} visible")
        driver.execute_script("arguments[0].click()", driver.find_element(By.CSS_SELECTOR, '[data-open-panel="filters"]'))
        wait.until(lambda current: current.find_element(By.ID, "filtersSheet").is_displayed())
        wait.until(lambda current: current.find_element(By.ID, "sheetDrawdownEnabled").is_displayed())
        driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "sheetDrawdownEnabled"))
        wait.until(lambda current: current.find_element(By.ID, "sheetDrawdownEnabled").is_selected())
        results = verify_presets(driver, wait, item_selector, metric_selector,
                                 '[data-drawdown-filter="sheet"]', values)
        driver.execute_script("arguments[0].click()", driver.find_element(By.CSS_SELECTOR, "#filtersSheet [data-close-sheet]"))
        wait.until(lambda current: not current.find_element(By.ID, "filtersSheet").is_displayed())
        return {"viewport": "mobile", "baseline": baseline,
                "presets": [asdict(result) for result in results],
                "runtime": driver.execute_script("return document.documentElement.dataset.drawdownScreener")}
    except Exception:
        driver.save_screenshot("/tmp/drawdown-mobile-failure.png"); raise
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    try:
        flows = [run_desktop(args.base_url.rstrip("/")), run_mobile(args.base_url.rstrip("/"))]
    except TimeoutException as exc:
        raise SystemExit(f"Production Drawdown browser smoke timed out: {exc}") from exc
    print(json.dumps({"status": "verified", "flows": flows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
