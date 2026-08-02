#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from typing import Iterable

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
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--no-first-run")
    options.add_argument("--hide-scrollbars")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    return webdriver.Chrome(options=options)


def parse_depth(text: str) -> float | None:
    match = re.search(r"-?([0-9]+(?:\.[0-9]+)?)%", text or "")
    return float(match.group(1)) if match else None


def is_drawdown_visible(element) -> bool:
    return "drawdown-filter-hidden" not in (element.get_attribute("class") or "").split()


def depths(elements: Iterable, metric_selector: str) -> list[float]:
    values: list[float] = []
    for element in elements:
        value = parse_depth(element.find_element(By.CSS_SELECTOR, metric_selector).text)
        if value is None:
            raise AssertionError("Drawdown metric is unavailable in a production Scanner row/card")
        values.append(value)
    return values


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
    wait.until(
        lambda current: current.execute_script(
            "return document.documentElement.dataset.drawdownScreener || ''"
        )
        == "10.9.0"
    )


def clear_storage(driver: webdriver.Chrome, url: str) -> None:
    driver.get(url)
    driver.execute_script("localStorage.clear(); sessionStorage.clear();")
    driver.refresh()


def run_desktop(base_url: str) -> dict:
    driver = chrome()
    driver.set_window_size(1440, 1000)
    wait = WebDriverWait(driver, 45)
    try:
        clear_storage(driver, f"{base_url}/index.html?browser_smoke={int(time.time())}-desktop")
        wait_runtime(driver, wait)
        wait.until(lambda current: len(current.find_elements(By.CSS_SELECTOR, "#technicalTableBody tr")) > 0)
        wait.until(
            lambda current: all(
                row.find_elements(By.CSS_SELECTOR, "[data-drawdown-cell]")
                for row in current.find_elements(By.CSS_SELECTOR, "#technicalTableBody tr")
            )
        )

        rows = driver.find_elements(By.CSS_SELECTOR, "#technicalTableBody tr")
        baseline = len([row for row in rows if is_drawdown_visible(row)])
        values = depths(rows, "[data-drawdown-cell]")
        if baseline != len(rows):
            raise AssertionError(f"Desktop Drawdown filter should start disabled: {baseline}/{len(rows)} visible")

        presets = choose_presets(values)
        toggle = driver.find_element(By.ID, "desktopDrawdownEnabled")
        driver.execute_script("arguments[0].click()", toggle)
        wait.until(lambda current: current.find_element(By.ID, "desktopDrawdownEnabled").is_selected())

        results: list[PresetResult] = []
        for preset in presets:
            button = driver.find_element(
                By.CSS_SELECTOR,
                f'[data-drawdown-filter="desktop"] [data-drawdown-preset="{preset}"]',
            )
            driver.execute_script("arguments[0].click()", button)
            expected = expected_count(values, preset)
            wait.until(
                lambda current, expected=expected: len(
                    [
                        row
                        for row in current.find_elements(By.CSS_SELECTOR, "#technicalTableBody tr")
                        if is_drawdown_visible(row)
                    ]
                )
                == expected
            )
            visible_rows = [
                row
                for row in driver.find_elements(By.CSS_SELECTOR, "#technicalTableBody tr")
                if is_drawdown_visible(row)
            ]
            actual_values = depths(visible_rows, "[data-drawdown-cell]")
            minimum, maximum = PRESETS[preset]
            if not all(minimum <= value < maximum for value in actual_values):
                raise AssertionError(f"Desktop preset {preset} exposed values outside its range: {actual_values[:12]}")
            results.append(PresetResult(preset, expected, len(visible_rows)))

        driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "desktopDrawdownEnabled"))
        wait.until(
            lambda current: len(
                [
                    row
                    for row in current.find_elements(By.CSS_SELECTOR, "#technicalTableBody tr")
                    if is_drawdown_visible(row)
                ]
            )
            == baseline
        )
        return {
            "viewport": "desktop",
            "baseline": baseline,
            "presets": [result.__dict__ for result in results],
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
    try:
        clear_storage(driver, f"{base_url}/index.html?browser_smoke={int(time.time())}-mobile")
        wait_runtime(driver, wait)
        wait.until(lambda current: len(current.find_elements(By.CSS_SELECTOR, "#technicalMobileCards > *")) > 0)
        wait.until(
            lambda current: all(
                card.find_elements(By.CSS_SELECTOR, "[data-drawdown-card-metric] strong")
                for card in current.find_elements(By.CSS_SELECTOR, "#technicalMobileCards > *")
            )
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "#technicalMobileCards > *")
        baseline = len([card for card in cards if is_drawdown_visible(card)])
        values = depths(cards, "[data-drawdown-card-metric] strong")
        if baseline != len(cards):
            raise AssertionError(f"Mobile Drawdown filter should start disabled: {baseline}/{len(cards)} visible")

        open_filters = driver.find_element(By.CSS_SELECTOR, '[data-open-panel="filters"]')
        driver.execute_script("arguments[0].click()", open_filters)
        wait.until(lambda current: current.find_element(By.ID, "filtersSheet").is_displayed())
        wait.until(lambda current: current.find_element(By.ID, "sheetDrawdownEnabled").is_displayed())

        toggle = driver.find_element(By.ID, "sheetDrawdownEnabled")
        driver.execute_script("arguments[0].click()", toggle)
        wait.until(lambda current: current.find_element(By.ID, "sheetDrawdownEnabled").is_selected())

        presets = choose_presets(values)
        results: list[PresetResult] = []
        for preset in presets:
            button = driver.find_element(
                By.CSS_SELECTOR,
                f'[data-drawdown-filter="sheet"] [data-drawdown-preset="{preset}"]',
            )
            driver.execute_script("arguments[0].click()", button)
            expected = expected_count(values, preset)
            wait.until(
                lambda current, expected=expected: len(
                    [
                        card
                        for card in current.find_elements(By.CSS_SELECTOR, "#technicalMobileCards > *")
                        if is_drawdown_visible(card)
                    ]
                )
                == expected
            )
            visible_cards = [
                card
                for card in driver.find_elements(By.CSS_SELECTOR, "#technicalMobileCards > *")
                if is_drawdown_visible(card)
            ]
            actual_values = depths(visible_cards, "[data-drawdown-card-metric] strong")
            minimum, maximum = PRESETS[preset]
            if not all(minimum <= value < maximum for value in actual_values):
                raise AssertionError(f"Mobile preset {preset} exposed values outside its range: {actual_values[:12]}")
            results.append(PresetResult(preset, expected, len(visible_cards)))

        close_sheet = driver.find_element(By.CSS_SELECTOR, "#filtersSheet [data-close-sheet]")
        driver.execute_script("arguments[0].click()", close_sheet)
        wait.until(lambda current: not current.find_element(By.ID, "filtersSheet").is_displayed())
        return {
            "viewport": "mobile",
            "baseline": baseline,
            "presets": [result.__dict__ for result in results],
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
    base_url = args.base_url.rstrip("/")
    try:
        results = [run_desktop(base_url), run_mobile(base_url)]
    except TimeoutException as exc:
        raise SystemExit(f"Production Drawdown browser smoke timed out: {exc}") from exc
    print(json.dumps({"status": "verified", "flows": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
