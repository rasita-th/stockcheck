#!/usr/bin/env python3
"""v8.2.6 Fundamental Freshness Resolver.

Purpose
-------
The static UI already has a SEC/companyfacts layer, but SEC companyfacts can be
stale, sparse, or parsed into odd values for some tickers.  This resolver uses
Finnhub `financials_reported(freq="quarterly")` as a freshness/data-quality
backup and Finnhub `company_earnings(limit=5)` for EPS surprise.

Security
--------
Never hardcode the Finnhub key.  The workflow should provide:

    FINNHUB_API_KEY=${{ secrets.FINNHUB_API_KEY }}

No key is written to JSON or browser JS.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]
FUNDAMENTAL_PATHS = [d / "fundamental.json" for d in DATA_DIRS]
REPORT_PATHS = [d / "fundamental_resolver_report.json" for d in DATA_DIRS]

API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
OFFLINE = os.environ.get("STOCKCHECK_OFFLINE", "").lower() in {"1", "true", "yes"}


class ResolverError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"::warning::Could not read {path}: {exc}")
        return fallback


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    # Try ISO timestamp first, then plain date.
    for candidate in [raw, raw[:10]]:
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass
    return None


def date_key(value: Any) -> str:
    d = parse_date(value)
    return d.date().isoformat() if d else ""


def finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        n = float(value)
        if math.isfinite(n):
            return n
    except Exception:
        return None
    return None


def fmt_money(value: Any) -> str:
    n = finite(value)
    if n is None:
        return "—"
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1_000_000_000:
        return f"{sign}${n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{sign}${n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{sign}${n / 1_000:.2f}K"
    return f"{sign}${n:.2f}"


def fmt_pct(value: Any) -> str:
    n = finite(value)
    return "—" if n is None else f"{n:+.2f}%"


def fmt_num(value: Any) -> str:
    n = finite(value)
    return "—" if n is None else f"{n:.3f}"


def safe_growth(current: Any, previous: Any) -> tuple[float | None, str]:
    """Growth that does not produce horror-show percentages from negative bases."""
    c = finite(current)
    p = finite(previous)
    if c is None or p is None:
        return None, "missing"
    if abs(p) < 1e-9:
        return None, "new_base"
    if p < 0 and c > 0:
        return None, "turned_positive"
    if p > 0 and c < 0:
        return None, "turned_negative"
    if p < 0 and c < 0:
        # For losses/negative values, use absolute base and mark as unusual.
        return ((c - p) / abs(p)) * 100, "negative_base"
    return ((c - p) / abs(p)) * 100, "normal"


def tone_for_value(value: Any, kind: str = "growth", status: str = "normal") -> str:
    n = finite(value)
    if status in {"turned_positive"}:
        return "good"
    if status in {"turned_negative"}:
        return "bad"
    if status in {"new_base", "negative_base"}:
        return "warn"
    if n is None:
        return "neutral"
    if kind in {"debt_to_equity"}:
        if n <= 0.5:
            return "good"
        if n <= 1.5:
            return "warn"
        return "bad"
    if kind in {"margin", "eps_surprise", "growth", "fcf"}:
        return "good" if n > 0 else "bad" if n < 0 else "neutral"
    return "neutral"


def concept_score(item: dict[str, Any], patterns: list[str]) -> int:
    hay = " ".join(str(item.get(k, "")) for k in ("concept", "label", "name")).lower()
    score = 0
    for i, pat in enumerate(patterns):
        if re.search(pat, hay, flags=re.I):
            score += 100 - i
    return score


def extract_value(report_section: Any, patterns: list[str]) -> float | None:
    if not isinstance(report_section, list):
        return None
    best: tuple[int, float] | None = None
    for item in report_section:
        if not isinstance(item, dict):
            continue
        value = finite(item.get("value"))
        if value is None:
            continue
        score = concept_score(item, patterns)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, value)
    return best[1] if best else None


PATTERNS = {
    "revenue": [r"revenuefromcontract", r"revenues?$", r"salesrevenuenet", r"total\s+revenue", r"sales"],
    "net_income": [r"netincomeloss", r"net\s+income", r"net\s+earnings"],
    "eps": [r"earningspersharediluted", r"eps.*diluted", r"diluted.*eps"],
    "gross_profit": [r"grossprofit", r"gross\s+profit"],
    "operating_income": [r"operatingincomeloss", r"operating\s+income"],
    "operating_cash_flow": [r"netcashprovidedbyusedinoperatingactivities", r"operating\s+cash"],
    "capex": [r"paymentstoacquireproperty", r"capital\s+expenditure", r"capex", r"propertyplantandequipment"],
    "equity": [r"stockholdersequity", r"shareholders.?equity", r"total\s+equity"],
    "debt": [r"longtermdebt", r"shorttermborrowings", r"debtcurrent", r"total\s+debt"],
}


def normalize_finnhub_report(raw: dict[str, Any]) -> dict[str, Any]:
    report = raw.get("report") or {}
    ic = report.get("ic") or []
    cf = report.get("cf") or []
    bs = report.get("bs") or []

    revenue = extract_value(ic, PATTERNS["revenue"])
    net_income = extract_value(ic, PATTERNS["net_income"])
    eps = extract_value(ic, PATTERNS["eps"])
    gross_profit = extract_value(ic, PATTERNS["gross_profit"])
    operating_income = extract_value(ic, PATTERNS["operating_income"])
    ocf = extract_value(cf, PATTERNS["operating_cash_flow"])
    capex = extract_value(cf, PATTERNS["capex"])
    equity = extract_value(bs, PATTERNS["equity"])

    # Debt can be split across several concepts. Sum matching debt concepts,
    # but avoid double counting an explicit total debt if present.
    total_debt = extract_value(bs, [r"total\s+debt", r"debt"])
    if total_debt is None:
        debt_sum = 0.0
        found_debt = False
        for item in bs if isinstance(bs, list) else []:
            if not isinstance(item, dict):
                continue
            hay = " ".join(str(item.get(k, "")) for k in ("concept", "label", "name")).lower()
            if any(re.search(p, hay, flags=re.I) for p in PATTERNS["debt"]):
                value = finite(item.get("value"))
                if value is not None:
                    debt_sum += value
                    found_debt = True
        total_debt = debt_sum if found_debt else None

    fcf = None
    if ocf is not None and capex is not None:
        fcf = ocf + capex if capex < 0 else ocf - abs(capex)

    gross_margin = (gross_profit / revenue * 100) if revenue not in (None, 0) and gross_profit is not None else None
    operating_margin = (operating_income / revenue * 100) if revenue not in (None, 0) and operating_income is not None else None
    net_margin = (net_income / revenue * 100) if revenue not in (None, 0) and net_income is not None else None
    debt_to_equity = (total_debt / equity) if equity not in (None, 0) and total_debt is not None else None

    return {
        "symbol": str(raw.get("symbol") or "").upper(),
        "form": raw.get("form"),
        "year": raw.get("year"),
        "quarter": raw.get("quarter"),
        "periodEnd": raw.get("endDate") or raw.get("period") or raw.get("periodEnd"),
        "filedDate": raw.get("filedDate") or raw.get("acceptedDate"),
        "accessNumber": raw.get("accessNumber"),
        "sourceUrl": raw.get("sourceUrl"),
        "revenue": revenue,
        "netIncome": net_income,
        "eps": eps,
        "grossProfit": gross_profit,
        "operatingIncome": operating_income,
        "operatingCashFlow": ocf,
        "capex": capex,
        "freeCashFlow": fcf,
        "grossMargin": gross_margin,
        "operatingMargin": operating_margin,
        "netMargin": net_margin,
        "totalDebt": total_debt,
        "stockholdersEquity": equity,
        "debtToEquity": debt_to_equity,
    }


def period_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (date_key(row.get("periodEnd")), date_key(row.get("filedDate")))


def fetch_finnhub_financials(client: Any, ticker: str) -> list[dict[str, Any]]:
    try:
        data = client.financials_reported(symbol=ticker, freq="quarterly")
    except Exception as exc:
        print(f"::warning::{ticker}: Finnhub financials_reported failed: {exc}")
        return []
    raw_rows = data.get("data") if isinstance(data, dict) else []
    if not isinstance(raw_rows, list):
        return []
    rows = [normalize_finnhub_report(r) for r in raw_rows if isinstance(r, dict)]
    rows = [r for r in rows if r.get("periodEnd")]
    rows.sort(key=period_sort_key, reverse=True)
    return rows


def fetch_finnhub_earnings(client: Any, ticker: str) -> list[dict[str, Any]]:
    try:
        data = client.company_earnings(ticker, limit=5)
    except Exception as exc:
        print(f"::warning::{ticker}: Finnhub company_earnings failed: {exc}")
        return []
    return data if isinstance(data, list) else []


def is_placeholder(row: dict[str, Any]) -> bool:
    src = str(row.get("fundamentalSource") or "").lower()
    reasons = " ".join(str(x) for x in row.get("fundamentalReasons") or []).lower()
    company = str(row.get("company") or "").lower()
    return any(x in src + " " + reasons + " " + company for x in ["placeholder", "sample static", "sample/static", "bundled for local"])


def row_has_bad_values(row: dict[str, Any]) -> bool:
    revenue = finite(row.get("revenue"))
    margin = finite(row.get("netMargin"))
    debt = finite(row.get("debtToEquity"))
    if revenue is not None and revenue < 0:
        return True
    if margin is not None and abs(margin) > 500:
        return True
    if debt is not None and debt > 100:
        return True
    return False


def choose_source(base_row: dict[str, Any], fh_rows: list[dict[str, Any]]) -> tuple[str, str, dict[str, Any] | None]:
    latest_fh = fh_rows[0] if fh_rows else None
    if not latest_fh:
        return "sec", "Finnhub unavailable; using existing SEC/companyfacts layer", None

    sec_period = date_key(base_row.get("periodEnd"))
    sec_filed = date_key(base_row.get("filedDate") or base_row.get("filingDate"))
    fh_period = date_key(latest_fh.get("periodEnd"))
    fh_filed = date_key(latest_fh.get("filedDate"))

    if is_placeholder(base_row):
        return "finnhub", "Existing fundamental data is sample/static placeholder", latest_fh
    if row_has_bad_values(base_row):
        return "finnhub", "Existing SEC/companyfacts row has suspicious values", latest_fh
    if fh_period and sec_period and fh_period > sec_period:
        return "finnhub", f"Finnhub quarterly period {fh_period} is newer than SEC/companyfacts {sec_period}", latest_fh
    if fh_period and not sec_period:
        return "finnhub", "Finnhub has a valid period end while existing row lacks periodEnd", latest_fh
    if fh_period == sec_period and fh_filed and sec_filed and fh_filed > sec_filed:
        return "finnhub", f"Same period but Finnhub filing date {fh_filed} is newer", latest_fh
    return "sec", "SEC/companyfacts appears current enough; Finnhub retained as backup", latest_fh


def quarter_label(row: dict[str, Any]) -> str:
    q = row.get("quarter")
    y = row.get("year")
    if q and y:
        return f"Q{q} {y}"
    d = parse_date(row.get("periodEnd"))
    if d:
        qn = (d.month - 1) // 3 + 1
        return f"Q{qn} {d.year}"
    return str(row.get("latestQuarter") or "Latest")


def build_growth_fields(latest: dict[str, Any], fh_rows: list[dict[str, Any]]) -> dict[str, Any]:
    prev_q = fh_rows[1] if len(fh_rows) > 1 else {}
    latest_date = parse_date(latest.get("periodEnd"))
    prev_y = {}
    if latest_date:
        target_year = latest_date.year - 1
        target_q = (latest_date.month - 1) // 3 + 1
        for r in fh_rows[1:]:
            rd = parse_date(r.get("periodEnd"))
            if rd and rd.year == target_year and ((rd.month - 1) // 3 + 1) == target_q:
                prev_y = r
                break
    fields: dict[str, Any] = {}
    mapping = {
        "revenue": ("revenueQoQ", "revenueYoY"),
        "netIncome": ("profitQoQ", "profitYoY"),
        "eps": ("epsQoQ", "epsYoY"),
    }
    flags: dict[str, str] = {}
    for key, (qfield, yfield) in mapping.items():
        q, qs = safe_growth(latest.get(key), prev_q.get(key))
        y, ys = safe_growth(latest.get(key), prev_y.get(key))
        fields[qfield] = q
        fields[yfield] = y
        flags[qfield] = qs
        flags[yfield] = ys
    fields["growthFlags"] = flags
    fields["revenuePrevQuarter"] = prev_q.get("revenue")
    fields["netIncomePrevQuarter"] = prev_q.get("netIncome")
    fields["epsPrevQuarter"] = prev_q.get("eps")
    return fields


def latest_eps_surprise(earnings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not earnings:
        return None
    rows = sorted(earnings, key=lambda r: str(r.get("period") or r.get("date") or ""), reverse=True)
    for e in rows:
        actual = finite(e.get("actual"))
        estimate = finite(e.get("estimate"))
        if actual is None and estimate is None:
            continue
        surprise_pct = finite(e.get("surprisePercent"))
        if surprise_pct is None:
            # When estimate is negative, a simple surprisePercent can be misleading.
            # Keep it descriptive rather than forcing a fake percentage.
            _, status = safe_growth(actual, estimate)
            surprise_pct = None if status != "normal" else safe_growth(actual, estimate)[0]
        tone = tone_for_value(surprise_pct if surprise_pct is not None else (actual or 0) - (estimate or 0), "eps_surprise")
        descriptor = "beat" if tone == "good" else "miss" if tone == "bad" else "inline/mixed"
        if actual is not None and estimate is not None and actual < 0 and estimate < 0:
            descriptor = "loss narrower than expected" if actual > estimate else "loss wider than expected"
            tone = "good" if actual > estimate else "bad"
        return {
            "period": e.get("period"),
            "actual": actual,
            "estimate": estimate,
            "surprisePercent": surprise_pct,
            "descriptor": descriptor,
            "tone": tone,
            "source": "Finnhub company_earnings",
        }
    return None


def build_ai_facts(row: dict[str, Any], source_detail: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    source = row.get("fundamentalSource") or source_detail or "Fundamental resolver"
    q = row.get("latestQuarter") or quarter_label(row)

    def add(label: str, text: str, tone: str = "neutral", source_override: str | None = None) -> None:
        facts.append({"label": label, "text": text, "tone": tone, "source": source_override or source})

    surprise = row.get("epsSurprise") or {}
    if isinstance(surprise, dict) and (surprise.get("actual") is not None or surprise.get("estimate") is not None):
        pct = fmt_pct(surprise.get("surprisePercent")) if surprise.get("surprisePercent") is not None else surprise.get("descriptor", "—")
        add(
            "EPS surprise",
            f"EPS surprise {surprise.get('period') or q}: actual {fmt_num(surprise.get('actual'))} vs estimate {fmt_num(surprise.get('estimate'))}; {pct}",
            surprise.get("tone") or "neutral",
            "Finnhub company_earnings",
        )

    flags = row.get("growthFlags") or {}
    revenue_qoq = row.get("revenueQoQ")
    revenue_status = flags.get("revenueQoQ", "normal")
    if revenue_status == "turned_positive":
        add("Revenue", f"Revenue {q} turned positive to {fmt_money(row.get('revenue'))} from a negative/odd base", "good")
    else:
        add("Revenue", f"Revenue {q}: {fmt_money(row.get('revenue'))}; QoQ {fmt_pct(revenue_qoq)}, YoY {fmt_pct(row.get('revenueYoY'))}", tone_for_value(revenue_qoq, "growth", revenue_status))

    ni_status = flags.get("profitQoQ", "normal")
    ni_tone = tone_for_value(row.get("profitQoQ"), "growth", ni_status)
    add("Net income", f"Net income {q}: {fmt_money(row.get('netIncome'))}; QoQ {fmt_pct(row.get('profitQoQ'))}, YoY {fmt_pct(row.get('profitYoY'))}", ni_tone)

    eps_status = flags.get("epsQoQ", "normal")
    eps_tone = tone_for_value(row.get("epsQoQ"), "growth", eps_status)
    add("EPS", f"EPS {q}: {fmt_num(row.get('eps'))}; QoQ {fmt_pct(row.get('epsQoQ'))}, YoY {fmt_pct(row.get('epsYoY'))}", eps_tone)

    add("Free cash flow", f"Free cash flow {fmt_money(row.get('freeCashFlow'))}", tone_for_value(row.get("freeCashFlow"), "fcf"))
    margins = [row.get("grossMargin"), row.get("operatingMargin"), row.get("netMargin")]
    add("Margins", f"Margin profile: gross {fmt_pct(margins[0])}, operating {fmt_pct(margins[1])}, net {fmt_pct(margins[2])}", tone_for_value(row.get("netMargin"), "margin"))
    add("Debt/Equity", f"Debt/Equity {fmt_num(row.get('debtToEquity'))}x", tone_for_value(row.get("debtToEquity"), "debt_to_equity"))

    prior = row.get("priorCompanyGuidanceRevenue")
    nxt = row.get("nextCompanyGuidanceRevenue")
    if prior or nxt:
        add("Guidance", f"Company guidance: prior {fmt_money(prior)} ({row.get('priorCompanyGuidanceRevenuePeriod') or '—'}); next {fmt_money(nxt)} ({row.get('nextCompanyGuidanceRevenuePeriod') or '—'})", "neutral")

    return facts


def apply_finnhub_row(base_row: dict[str, Any], fh_rows: list[dict[str, Any]], earnings: list[dict[str, Any]]) -> dict[str, Any]:
    out = deepcopy(base_row)
    selected, reason, latest_fh = choose_source(base_row, fh_rows)
    latest = latest_fh or {}
    ticker = str(out.get("ticker") or out.get("symbol") or latest.get("symbol") or "").upper()

    out["selectedFundamentalSource"] = "Finnhub quarterly" if selected == "finnhub" else "SEC/companyfacts"
    out["selectedFundamentalReason"] = reason
    out["secPeriodEnd"] = out.get("periodEnd")
    out["finnhubPeriodEnd"] = latest.get("periodEnd")
    out["finnhubFiledDate"] = latest.get("filedDate")
    out["finnhubAccessNumber"] = latest.get("accessNumber")
    out["fundamentalResolverVersion"] = "8.2.6"
    out["isSamplePlaceholder"] = is_placeholder(base_row)

    if selected == "finnhub" and latest:
        for key in [
            "revenue", "netIncome", "eps", "freeCashFlow", "grossMargin", "operatingMargin",
            "netMargin", "debtToEquity", "totalDebt", "stockholdersEquity", "operatingCashFlow", "capex",
        ]:
            if latest.get(key) is not None:
                out[key] = latest.get(key)
        out["periodEnd"] = latest.get("periodEnd") or out.get("periodEnd")
        out["latestQuarter"] = quarter_label(latest)
        out["fundamentalSource"] = "Finnhub financials_reported quarterly + SEC/companyfacts backup"
        out.update(build_growth_fields(latest, fh_rows))
    else:
        out.setdefault("fundamentalSource", "SEC EDGAR companyfacts + Finnhub backup")

    surprise = latest_eps_surprise(earnings)
    if surprise:
        out["epsSurprise"] = surprise

    out["aiViewFacts"] = build_ai_facts(out, out.get("fundamentalSource"))
    out["fundamentalReasons"] = [f.get("text") for f in out["aiViewFacts"]]
    if out.get("isSamplePlaceholder"):
        out.setdefault("fundamentalWarnings", []).append("Existing SEC/companyfacts layer was sample/static placeholder; verify live data workflow output.")
    if ticker:
        out["ticker"] = ticker
        out["symbol"] = ticker
    return out


def all_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("rows")
    return rows if isinstance(rows, list) else []


def upsert_maps(data: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    data["rows"] = rows
    data["count"] = len(rows)
    fundamentals = data.get("fundamentals") if isinstance(data.get("fundamentals"), dict) else {}
    for row in rows:
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
        if not ticker:
            continue
        existing = fundamentals.get(ticker) if isinstance(fundamentals.get(ticker), dict) else {}
        existing["symbol"] = ticker
        existing["latest"] = row
        existing["fundamental"] = row
        meta = existing.get("meta") if isinstance(existing.get("meta"), dict) else {}
        meta["source"] = row.get("fundamentalSource")
        meta["selected_source"] = row.get("selectedFundamentalSource")
        meta["resolver_version"] = "8.2.6"
        existing["meta"] = meta
        fundamentals[ticker] = existing
    data["fundamentals"] = fundamentals
    data["generatedAtFundamentalResolver"] = now_iso()
    data["fundamentalResolverVersion"] = "8.2.6"


def main() -> None:
    source_path = first_existing(FUNDAMENTAL_PATHS)
    if not source_path:
        raise SystemExit("No fundamental.json found in data/site/static data paths")
    data = load_json(source_path, {})
    if not isinstance(data, dict):
        raise SystemExit("fundamental.json root must be an object")
    rows = all_rows(data)
    if not rows:
        raise SystemExit("fundamental.json rows empty; cannot resolve")

    diagnostics: dict[str, Any] = {
        "generated_at": now_iso(),
        "version": "8.2.6",
        "api_key_present": bool(API_KEY),
        "offline": OFFLINE,
        "tickers_checked": len(rows),
        "selected_finnhub": [],
        "selected_sec": [],
        "errors": {},
        "warnings": [],
    }

    client = None
    if API_KEY and not OFFLINE:
        try:
            import finnhub  # type: ignore
            client = finnhub.Client(api_key=API_KEY)
        except Exception as exc:
            diagnostics["warnings"].append(f"Finnhub client unavailable: {exc}")
            print(f"::warning::Finnhub client unavailable: {exc}")
    elif not API_KEY:
        diagnostics["warnings"].append("FINNHUB_API_KEY missing; resolver will only normalize existing data")
        print("::warning::FINNHUB_API_KEY missing; resolver will only normalize existing data")

    resolved_rows: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
        fh_reports: list[dict[str, Any]] = []
        earnings: list[dict[str, Any]] = []
        if client and ticker:
            fh_reports = fetch_finnhub_financials(client, ticker)
            earnings = fetch_finnhub_earnings(client, ticker)
        try:
            resolved = apply_finnhub_row(row, fh_reports, earnings)
            if resolved.get("selectedFundamentalSource") == "Finnhub quarterly":
                diagnostics["selected_finnhub"].append(ticker)
            else:
                diagnostics["selected_sec"].append(ticker)
            resolved_rows.append(resolved)
        except Exception as exc:
            diagnostics["errors"][ticker or "UNKNOWN"] = str(exc)
            print(f"::warning::{ticker}: resolver failed: {exc}")
            resolved_rows.append(row)

    upsert_maps(data, resolved_rows)
    data["fundamentalDiagnostics"] = diagnostics

    for path in FUNDAMENTAL_PATHS:
        save_json(path, data)
    for path in REPORT_PATHS:
        save_json(path, diagnostics)

    print(f"Fundamental resolver v8.2.6 complete: {len(resolved_rows)} rows")
    print(f"- Finnhub selected: {len(diagnostics['selected_finnhub'])}")
    print(f"- SEC/companyfacts selected: {len(diagnostics['selected_sec'])}")
    if diagnostics["errors"]:
        print(f"- Errors: {len(diagnostics['errors'])}")


if __name__ == "__main__":
    main()
