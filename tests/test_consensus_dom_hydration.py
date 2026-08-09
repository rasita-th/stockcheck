from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_MIRRORS = (ROOT / "site" / "app.js", ROOT / "static" / "app.js")


def function_body(source: str, name: str) -> str:
    marker = f"function {name}("
    start = source.index(marker)
    body_start = source.index("{", start)
    depth = 0
    for index in range(body_start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[body_start + 1 : index]
    raise AssertionError(f"unterminated function: {name}")


class ConsensusDomHydrationTests(unittest.TestCase):
    def test_analyst_tab_loads_static_cache_before_final_render(self) -> None:
        for path in APP_MIRRORS:
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text(encoding="utf-8")
                body = function_body(source, "setFundSubTab")
                analyst_branch = body.split('state.fundSubTab === "analyst"', 1)[1]

                load_index = analyst_branch.index("await loadRecommendationTrendsCache()")
                render_index = analyst_branch.index("renderDetail()", load_index)
                self.assertLess(load_index, render_index)

    def test_runtime_app_mirrors_remain_identical(self) -> None:
        self.assertEqual(
            APP_MIRRORS[0].read_bytes(),
            APP_MIRRORS[1].read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
