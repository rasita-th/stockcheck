#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATHS = [
    ROOT / "data/market_universe.json",
    ROOT / "site/data/market_universe.json",
    ROOT / "static/data/market_universe.json",
]
OUTPUT_DIRS = [ROOT / "data/generated", ROOT / "data", ROOT / "site/data", ROOT / "static/data"]


def universe() -> dict[str, Any]:
    for path in UNIVERSE_PATHS:
        if path.exists() and path.stat().st_size:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    raise SystemExit("market_universe.json not found")


def safe(value: Any) -> float | None:
    try:
        number = float(value)
        return round(number, 2) if math.isfinite(number) else None
    except Exception:
        return None


def change(series: pd.Series, sessions: int) -> float | None:
    series = series.dropna()
    return None if len(series) <= sessions or float(series.iloc[-sessions - 1]) == 0 else safe((float(series.iloc[-1]) / float(series.iloc[-sessions - 1]) - 1) * 100)


def ytd(series: pd.Series) -> float | None:
    series = series.dropna()
    if series.empty:
        return None
    current = series[series.index.year == series.index[-1].year]
    return None if len(current) < 2 or float(current.iloc[0]) == 0 else safe((float(current.iloc[-1]) / float(current.iloc[0]) - 1) * 100)


def get_one(symbol: str) -> pd.Series:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            history = yf.download(symbol, period="18mo", interval="1d", auto_adjust=True, progress=False, threads=False)
            if not history.empty:
                close = history["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                close = close.dropna()
                if not close.empty:
                    return close
        except Exception as exc:
            last_error = exc
        time.sleep(1 + attempt)
    raise RuntimeError(str(last_error or "no price history"))


def enrich(item: dict[str, Any], series: pd.Series) -> dict[str, Any]:
    row = dict(item)
    row.update(
        {
            "price": safe(series.iloc[-1]),
            "day_pct": change(series, 1),
            "week_pct": change(series, 5),
            "month_pct": change(series, 21),
            "ytd_pct": ytd(series),
            "year_pct": change(series, 252),
            "as_of": series.index[-1].strftime("%Y-%m-%d"),
            "status": "ok",
        }
    )
    return row


def build(items: list[dict[str, Any]], cache: dict[str, pd.Series], failed: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        symbol = str(item.get("symbol") or "").strip()
        try:
            if symbol not in cache:
                cache[symbol] = get_one(symbol)
            rows.append(enrich(item, cache[symbol]))
        except Exception as exc:
            failed.append({"symbol": symbol, "error": str(exc)})
            row = dict(item)
            row.update(
                {
                    "price": None,
                    "day_pct": None,
                    "week_pct": None,
                    "month_pct": None,
                    "ytd_pct": None,
                    "year_pct": None,
                    "as_of": None,
                    "status": "unavailable",
                }
            )
            rows.append(row)
    return rows


def pulse(sectors: list[dict[str, Any]], themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for group, rows in (("sector", sectors), ("theme", themes)):
        for row in rows:
            day, week = row.get("day_pct"), row.get("week_pct")
            if day is None and week is None:
                continue
            score = abs(day or 0) * 1.3 + abs(week or 0) * 0.7
            output.append(
                {
                    "symbol": row.get("symbol"),
                    "label": row.get("label"),
                    "group": group,
                    "direction": "leading" if (week or 0) > 0 else "lagging",
                    "day_pct": day,
                    "week_pct": week,
                    "month_pct": row.get("month_pct"),
                    "score": round(score, 2),
                }
            )
    return sorted(output, key=lambda item: item["score"], reverse=True)[:10]


def valid(rows: list[dict[str, Any]], key: str = "week_pct") -> list[dict[str, Any]]:
    return [row for row in rows if safe(row.get(key)) is not None]


def average(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if safe(row.get(key)) is not None]
    return sum(values) / len(values) if values else 0.0


def ordered(rows: list[dict[str, Any]], key: str = "week_pct") -> list[dict[str, Any]]:
    return sorted(valid(rows, key), key=lambda row: float(row[key]), reverse=True)


def label(row: dict[str, Any] | None, fallback: str) -> str:
    if not row:
        return fallback
    return str(row.get("label") or row.get("name") or row.get("symbol") or fallback)


def pct(value: Any) -> str:
    number = safe(value)
    return "—" if number is None else f"{number:+.1f}%"


def names(rows: list[dict[str, Any] | None], limit: int = 3) -> list[str]:
    result: list[str] = []
    for row in rows:
        if not row:
            continue
        value = label(row, "")
        if value and value not in result:
            result.append(value)
        if len(result) >= limit:
            break
    return result


def build_narrative(
    global_markets: list[dict[str, Any]],
    us_indices: list[dict[str, Any]],
    sectors: list[dict[str, Any]],
    themes: list[dict[str, Any]],
    breadth: dict[str, int],
) -> dict[str, Any]:
    sector_rows = valid(sectors)
    us_rows = [row for row in valid(us_indices) if row.get("symbol") != "^VIX"]
    theme_rows = valid(themes)
    global_rows = valid(global_markets)
    sector_rank = ordered(sector_rows)
    theme_rank = ordered(theme_rows)
    global_rank = ordered(global_rows)
    sector_leader = sector_rank[0] if sector_rank else None
    sector_laggard = sector_rank[-1] if sector_rank else None
    theme_leader = theme_rank[0] if theme_rank else None
    theme_laggard = theme_rank[-1] if theme_rank else None
    global_leader = global_rank[0] if global_rank else None
    global_laggard = global_rank[-1] if global_rank else None
    sector_count = max(int(breadth.get("sector_count") or len(sector_rows) or 0), 1)
    breadth_ratio = int(breadth.get("sectors_positive_week") or 0) / sector_count
    sector_avg = average(sector_rows, "week_pct")
    us_avg = average(us_rows, "week_pct")
    score = sector_avg * 0.55 + us_avg * 0.45 + (breadth_ratio - 0.5) * 4
    regime = "risk-on" if score > 1 else "risk-off" if score < -1 else "mixed"
    vix = next((row for row in us_indices if row.get("symbol") == "^VIX" or "vix" in str(row.get("label", "")).lower()), None)
    vix_week = safe(vix.get("week_pct")) if vix else None
    risk_level = "elevated" if regime == "risk-off" or breadth_ratio < 0.3 or (vix_week is not None and vix_week > 8) else "contained" if regime == "risk-on" and breadth_ratio > 0.65 else "moderate"
    regime_thai = {"risk-on": "Risk-on", "risk-off": "Risk-off", "mixed": "Mixed"}[regime]
    headline = (
        f"แรงซื้อกระจายกว้าง โดย {label(sector_leader, 'กลุ่มนำ')} เป็นผู้นำตลาด"
        if regime == "risk-on"
        else f"แรงขายกดดันตลาด ขณะที่ {label(sector_laggard, 'กลุ่มอ่อนแอ')} ถ่วง breadth"
        if regime == "risk-off"
        else "ตลาดยังเลือกเล่นเป็นรายกลุ่ม และ breadth ยังไม่ยืนยัน Risk-on เต็มตัว"
    )
    common = {
        "positive": names([sector_leader, theme_leader]),
        "watch": names([global_leader, global_laggard]),
        "risk": names([sector_laggard, theme_laggard]),
    }
    balanced = [
        f"ภาวะตลาดอยู่ในโหมด {regime_thai}; ค่าเฉลี่ย US sectors 1W อยู่ที่ {pct(sector_avg)}.",
        f"{round(breadth_ratio * 100)}% ของ US sectors เป็นบวกในรอบสัปดาห์.",
        f"{label(sector_leader, 'Sector ผู้นำ')} นำที่ {pct(sector_leader.get('week_pct') if sector_leader else None)} ขณะที่ {label(sector_laggard, 'sector ตามหลัง')} อยู่ที่ {pct(sector_laggard.get('week_pct') if sector_laggard else None)}.",
        f"{label(theme_leader, 'ธีมเด่น')} เป็นธีมที่แข็งที่สุดในชุดติดตามที่ {pct(theme_leader.get('week_pct') if theme_leader else None)}.",
        f"ตลาดโลกนำโดย {label(global_leader, '—')} {pct(global_leader.get('week_pct') if global_leader else None)} และอ่อนสุดคือ {label(global_laggard, '—')} {pct(global_laggard.get('week_pct') if global_laggard else None)}.",
        "ควรให้ความสำคัญกับ position sizing และรอ price confirmation มากกว่าการไล่ราคา." if risk_level == "elevated" else "ภาพรวมยังเปิดทางให้ถือผู้นำ แต่ควรเพิ่มน้ำหนักเฉพาะจุดที่ราคาและ breadth สนับสนุนกัน.",
    ]
    portfolio = [
        "Portfolio mode เชื่อมกับ Watchlist ที่บันทึกไว้ใน Scanner บนอุปกรณ์ของผู้ใช้.",
        f"Market backdrop ปัจจุบันคือ {regime_thai} และ breadth สัปดาห์อยู่ที่ {round(breadth_ratio * 100)}%.",
        f"{label(sector_leader, 'Sector ผู้นำ')} เป็นกลุ่มที่ช่วยหนุน relative strength ของหุ้นที่เกี่ยวข้อง.",
        f"{label(sector_laggard, 'Sector อ่อนแอ')} เป็นกลุ่มที่ควรตรวจสอบว่าหุ้นในพอร์ตหลุดแนวรับหรือไม่.",
        "Frontend จะใช้ technical.json แยก Potential Add, Hold, Watch, Avoid Chasing และ Trim Risk โดยไม่ส่ง Watchlist กลับ backend.",
    ]
    action = [
        "ลดการไล่ราคาและให้ความสำคัญกับการป้องกัน drawdown ก่อน." if regime == "risk-off" else "ถือผู้นำที่ยังมี relative strength และหลีกเลี่ยงการเพิ่มในหุ้นที่ยืดตัวเกินไป.",
        f"{label(sector_leader, 'Sector ผู้นำ')}: รอ pullback หรือ breakout ที่มี volume ยืนยัน.",
        f"{label(sector_laggard, 'Sector อ่อนแอ')}: ตรวจสอบแนวรับและ EMA สำคัญก่อนเพิ่มน้ำหนัก.",
        f"{label(theme_leader, 'ธีมเด่น')}: จัด position size ให้สอดคล้องกับ volatility ของธีม.",
        "ใช้ Portfolio tab เพื่อดู action tag จาก technical scanner ของ Watchlist ที่บันทึกไว้.",
    ]
    news = [
        f"ตลาดสหรัฐอยู่ในภาวะ {regime_thai} หลังค่าเฉลี่ยดัชนีหลัก 1W อยู่ที่ {pct(us_avg)}.",
        f"{label(sector_leader, 'Sector ผู้นำ')} ปรับตัวเด่นสุดในกลุ่ม sector ที่ {pct(sector_leader.get('week_pct') if sector_leader else None)}.",
        f"{label(sector_laggard, 'Sector ตามหลัง')} อ่อนสุดที่ {pct(sector_laggard.get('week_pct') if sector_laggard else None)}.",
        f"ธีมเด่นคือ {label(theme_leader, '—')} ที่ {pct(theme_leader.get('week_pct') if theme_leader else None)} ขณะที่ตลาดโลกมี {label(global_leader, '—')} เป็นผู้นำ.",
        f"ระดับความเสี่ยงเชิงตลาดถูกจัดเป็น {risk_level}; สรุปนี้อิงราคาและ ETF proxy ไม่ใช่ feed ข่าวเรียลไทม์.",
    ]
    risk = [
        f"Risk level: {risk_level}; breadth สัปดาห์อยู่ที่ {round(breadth_ratio * 100)}%.",
        f"{label(sector_laggard, 'Sector อ่อนแอ')} เป็นจุดเสี่ยงหลักจากผลตอบแทน 1W {pct(sector_laggard.get('week_pct') if sector_laggard else None)}.",
        f"{label(theme_laggard, 'ธีมอ่อนแอ')} เป็นธีมที่ตามหลังมากที่สุดที่ {pct(theme_laggard.get('week_pct') if theme_laggard else None)}.",
        f"VIX proxy เปลี่ยนแปลง {pct(vix_week)} ในรอบสัปดาห์." if vix_week is not None else "VIX proxy ไม่มีข้อมูลเพียงพอในรอบนี้ จึงให้น้ำหนัก breadth และดัชนีแทน.",
        "หากหุ้นใน Watchlist หลุด EMA200 หรือ scanner เปลี่ยนเป็น AVOID/WEAK ให้ถือเป็นความเสี่ยงที่ต้องตรวจสอบก่อนเพิ่มสถานะ.",
    ]
    return {
        "schema_version": "1.0",
        "default_mode": "balanced",
        "regime": regime,
        "risk_level": risk_level,
        "headline": headline,
        "refresh_window_hours": 12,
        "sources": [
            {"label": "Yahoo Finance / yfinance", "detail": "ราคา EOD ของดัชนีและ ETF proxy"},
            {"label": "Stock Timing Radar", "detail": "breadth, sector rotation, theme rotation และ technical scanner"},
        ],
        "modes": {
            "balanced": {"label": "Market", "edition": "MARKET · BALANCED", "headline": headline, "deck": "สรุปภาพตลาดจาก breadth, ดัชนี, sector และ theme ในข้อความ 5–10 บรรทัด", "summary": balanced, **common},
            "portfolio": {"label": "Portfolio", "edition": "PORTFOLIO · WATCHLIST", "headline": "เชื่อม Market Pulse กับ Watchlist ที่บันทึกใน Scanner", "deck": "ระบบจะสร้างข้อความเฉพาะพอร์ตใน browser จาก technical.json และ localStorage", "summary": portfolio, **common},
            "action": {"label": "Action", "edition": "ACTION · DECISION SUPPORT", "headline": "เน้นควบคุมความเสี่ยงก่อนเพิ่ม exposure" if regime == "risk-off" else "ถือผู้นำ รอจังหวะ และไม่ไล่ราคาที่ขยายตัวเกินไป", "deck": "เปลี่ยนข้อมูลตลาดเป็นสิ่งที่ควรตรวจสอบต่อ ไม่ใช่คำสั่งซื้อขาย", "summary": action, **common},
            "news": {"label": "News", "edition": "NEWS · MARKET TAPE", "headline": f"Market tape: {regime_thai} พร้อม sector rotation ที่แตกต่างกัน", "deck": "ข่าวสั้นเชิงตลาดจากข้อมูลราคา ไม่กล่าวอ้างเหตุการณ์ที่ไม่มีแหล่งข่าวรองรับ", "summary": news, **common},
            "risk": {"label": "Risk", "edition": "RISK · MONITOR", "headline": "ความเสี่ยงสูงกว่าปกติ ควรลดการตัดสินใจจาก momentum ระยะสั้น" if risk_level == "elevated" else "ความเสี่ยงยังควบคุมได้ แต่ breadth ต้องยืนยันต่อเนื่อง", "deck": "จัดลำดับสิ่งที่อาจทำให้ thesis หรือโครงสร้างราคาผิดทาง", "summary": risk, **common},
        },
    }


def save(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for directory in OUTPUT_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "market_pulse.json"
        path.write_text(text, encoding="utf-8")
        print("wrote", path)


def main() -> None:
    config = universe()
    cache: dict[str, pd.Series] = {}
    failed: list[dict[str, str]] = []
    global_markets = build(config.get("global_markets", []), cache, failed)
    us_indices = build(config.get("us_indices", []), cache, failed)
    sectors = build(config.get("us_sectors", []), cache, failed)
    themes = build(config.get("themes", []), cache, failed)
    all_rows = global_markets + us_indices + sectors + themes
    ok = sum(1 for row in all_rows if row.get("status") == "ok")
    breadth = {
        "sectors_positive_day": sum(1 for row in sectors if (row.get("day_pct") or 0) > 0),
        "sectors_positive_week": sum(1 for row in sectors if (row.get("week_pct") or 0) > 0),
        "sector_count": sum(1 for row in sectors if row.get("status") == "ok"),
    }
    generated_at = datetime.now(timezone.utc)
    payload = {
        "schema_version": "3.0",
        "version": "9.6.0",
        "generated_at": generated_at.isoformat(),
        "next_refresh_at": (generated_at + timedelta(hours=12)).isoformat(),
        "source": "Yahoo Finance via yfinance; indices and ETF proxies",
        "status": "ok" if not failed else ("partial" if ok else "error"),
        "successful_symbols": ok,
        "requested_rows": len(all_rows),
        "failed_symbols": failed,
        "global_markets": global_markets,
        "us_indices": us_indices,
        "us_sectors": sectors,
        "themes": themes,
        "today_pulse": pulse(sectors, themes),
        "breadth": breadth,
        "narrative": build_narrative(global_markets, us_indices, sectors, themes, breadth),
    }
    save(payload)


if __name__ == "__main__":
    main()
