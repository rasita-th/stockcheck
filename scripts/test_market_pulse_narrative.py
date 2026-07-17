#!/usr/bin/env python3
from __future__ import annotations

from generate_market_pulse import build_narrative

MODES = ("balanced", "portfolio", "action", "news", "risk")


def row(symbol: str, label: str, week: float, day: float = 0.0) -> dict:
    return {"symbol": symbol, "label": label, "week_pct": week, "day_pct": day, "price": 100.0, "status": "ok"}


def validate(narrative: dict) -> None:
    assert narrative["default_mode"] == "balanced"
    assert narrative["regime"] in {"risk-on", "mixed", "risk-off"}
    assert narrative["risk_level"] in {"contained", "moderate", "elevated"}
    assert set(narrative["modes"]) == set(MODES)
    for key in MODES:
        mode = narrative["modes"][key]
        assert isinstance(mode["headline"], str) and len(mode["headline"]) >= 8
        assert isinstance(mode["deck"], str) and len(mode["deck"]) >= 8
        assert 5 <= len(mode["summary"]) <= 10
        assert all(isinstance(line, str) and len(line) >= 8 for line in mode["summary"])
        assert isinstance(mode["positive"], list)
        assert isinstance(mode["watch"], list)
        assert isinstance(mode["risk"], list)


def main() -> None:
    globals_ = [row("^GSPC", "S&P 500", 2.0), row("^N225", "Nikkei 225", -1.0), row("^HSI", "Hang Seng", 3.0)]
    us = [row("^GSPC", "S&P 500", 2.0), row("^IXIC", "Nasdaq", 2.5), row("^VIX", "VIX", -8.0)]
    sectors_up = [row(f"S{i}", f"Sector {i}", 1.0 + i / 10) for i in range(9)] + [row("S9", "Sector 9", -0.2)]
    themes = [row("SMH", "Semiconductor", 4.0), row("URA", "Uranium", 2.0), row("ARKG", "Biotech", -1.0), row("ITA", "Defense", 1.0), row("IGV", "Software", 3.0)]
    bullish = build_narrative(globals_, us, sectors_up, themes, {"sectors_positive_week": 9, "sector_count": 10})
    validate(bullish)
    assert bullish["regime"] == "risk-on"

    sectors_down = [row(f"D{i}", f"Down {i}", -2.0 - i / 10) for i in range(10)]
    bearish = build_narrative(globals_, [row("^GSPC", "S&P 500", -3.0), row("^IXIC", "Nasdaq", -4.0), row("^VIX", "VIX", 12.0)], sectors_down, themes, {"sectors_positive_week": 0, "sector_count": 10})
    validate(bearish)
    assert bearish["regime"] == "risk-off"
    assert bearish["risk_level"] == "elevated"
    print("Market Pulse narrative tests passed")


if __name__ == "__main__":
    main()
