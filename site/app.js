/* Stock Timing Radar — v8.0 Stability & Data Integrity
   Full v3.3 mock UI shell + original Python backend engine.
   Backend endpoints used: /api/scan, /api/quote, /api/health; analyst view links out to Yahoo Finance
*/

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
const BUILD_VERSION = "v8.0 Stability & Data Integrity";

const ETF_TICKERS = new Set(["ARKK", "ARKQ", "ARKW", "ARKG", "ARKF", "ARKX", "PRNT", "SMH", "SOXX", "QQQI", "JEPQ", "AIQ", "COPX", "UFO"]);
const BASE_WATCHLIST = ["PUMP", "SEI", "NVDA", "TSLA", "AMD", "AAPL", "AMZN", "PLTR", "SOUN"];
const STORAGE = {
  watchlist: "stockTimingRadar.watchlist.v54",
  screeners: "stockTimingRadar.screeners.v54",
  activeScreener: "stockTimingRadar.activeScreener.v54",
  settings: "stockTimingRadar.settings.v54",
  alphaKey: "stockTimingRadar.alphaKey.v1",
  priceChartMode: "stockTimingRadar.priceChartMode.v51",
  alertSeen: "stockTimingRadar.alertSeen.v61",
  alertDismissed: "stockTimingRadar.alertDismissed.v62",
};

const STATIC_DATA_URLS = {
  technical: "data/technical.json",
  fundamental: "data/fundamental.json",
};

function isStaticDeployHost() {
  const host = window.location.hostname || "";
  if (!host) return true;
  if (host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0") return false;
  return true;
}

let state = {
  selected: "PUMP",
  scannerTab: "technical",
  sortKey: "score",
  sortAsc: false,
  fundSubTab: "earnings",
  detailTab: "technical",
  mobileView: "cards",
  priceChartMode: localStorage.getItem("stockTimingRadar.priceChartMode.v51") || "line",
  chartModalOpen: false,
  activeScreener: "default",
  analystLoaded: {},
  analystPayloads: {},
  columns: {
    ticker: true, score: true, signal: true, price: true,
    ema5: true, ema20: true, ema89: true, ema200: true,
    rsi: true, macdHist: false, vol20: false, high52: false,
    fundTicker: true, fundScore: true, fundQuarter: true,
    fundRevenue: true, fundNetIncome: true, fundEps: true,
    fundFcf: true, fundMargins: true, fundGuidance: false
  },
  lastScanAt: null,
  watchlist: loadWatchlist(),
  rows: [],
  quotes: {},
  errors: [],
  lastScanSymbols: [],
  activeMarketGroup: "ALL",
  loading: false,
  fundamentalLoading: false,
  showFilteredRows: true,
  symbolLoads: new Set(),
  alertFilter: localStorage.getItem("stockTimingRadar.alertFilter.v61") || "all",
  alertCollapsed: localStorage.getItem("stockTimingRadar.alertCollapsed.v61") === "1",
  lastAlertSignature: localStorage.getItem("stockTimingRadar.alertSeen.v61") || "",
  dismissedAlerts: new Set(JSON.parse(localStorage.getItem("stockTimingRadar.alertDismissed.v62") || "[]")),
  alertSheetOpen: false,
  staticMode: isStaticDeployHost(),
  staticLoaded: false,
  staticPayloads: { technical: null, fundamental: null },
  staticLoadError: null,
  filters: {
    score: 60,
    range: "1y",
    above200: true,
    emaStack: true,
    sweetRsi: true,
    volume20: false,
    macdSignal: true,
  },
};

function loadWatchlist() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE.watchlist) || "[]");
    if (Array.isArray(saved) && saved.length) return normalizeTickers(saved);
  } catch (_) {}
  return [...BASE_WATCHLIST];
}

function saveWatchlist() {
  localStorage.setItem(STORAGE.watchlist, JSON.stringify(state.watchlist));
  persistActiveScreener();
}

function normalizeTicker(raw) {
  return String(raw || "")
    .trim()
    .replace(/^[$#]+/, "")
    .toUpperCase();
}

function normalizeTickers(items) {
  return [...new Set(items.map(normalizeTicker).filter(t => /^[A-Z0-9.\-]{1,18}$/.test(t)))];
}

function parseTickerList(rawText = "") {
  return normalizeTickers(String(rawText).split(/[\s,;|、，]+/));
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function toNum(value) {
  if (value === null || value === undefined || value === "" || value === "N/A") return null;
  const n = Number(String(value).replace(/[$,%x,]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function fmt(n, digits = 2) {
  const v = toNum(n);
  if (v === null) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtCompact(n, digits = 2) {
  const v = toNum(n);
  if (v === null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e12) return `$${fmt(v / 1e12, digits)}T`;
  if (abs >= 1e9) return `$${fmt(v / 1e9, digits)}B`;
  if (abs >= 1e6) return `$${fmt(v / 1e6, digits)}M`;
  return fmtMoney(v, digits);
}

function fmtMoney(n, digits = 2) {
  const v = toNum(n);
  if (v === null) return "—";
  if (Math.abs(v) < 1) return `$${v.toLocaleString("en-US", { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

function pctLabel(n, digits = 2) {
  const v = toNum(n);
  if (v === null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${fmt(v, digits)}%`;
}

function pctClass(n) {
  const v = toNum(n);
  if (v === null) return "neutral";
  if (v < 0) return "red";
  if (v <= 5) return "green";
  if (v <= 15) return "yellow";
  if (v <= 30) return "orange";
  return "red";
}

// Fundamental growth color logic is intentionally different from EMA distance.
// For fundamentals, higher positive growth is good; red is reserved for negative values.
function fundPctClass(n) {
  const v = toNum(n);
  if (v === null) return "neutral";
  if (v < 0) return "red";
  if (v === 0) return "neutral";
  return "green";
}

function signedTextHtml(value) {
  const raw = String(value ?? "");
  if (!raw) return "";
  // Color explicitly signed values only, without accidentally coloring date pieces like 2026-03-31.
  // Supports +20.7%, -37.0%, $-18.3M, +0.780, -0.52x.
  return esc(raw).replace(/(^|[\s(])((?:[+−-]\$?|\$[−-])\d[\d,]*(?:\.\d+)?(?:%|[KMBTx]?|x)?)/g, (full, prefix, token) => {
    const normalized = token.replace("−", "-");
    const isNeg = normalized.startsWith("-") || normalized.startsWith("$-");
    const cls = isNeg ? "signed-negative" : "signed-positive";
    return `${prefix}<span class="${cls}">${token}</span>`;
  });
}

function signedValueHtml(value, formatter = pctLabel) {
  const text = formatter(value);
  const n = toNum(value);
  const cls = n === null ? "neutral" : n < 0 ? "signed-negative" : n > 0 ? "signed-positive" : "neutral";
  return `<span class="${cls}">${esc(text)}</span>`;
}

function signalClass(signal = "") {
  const s = String(signal || "").toUpperCase();
  if (s.includes("HOT") || s.includes("อย่าไล่ราคา")) return "hot";
  if (s.includes("BUY") || s.includes("STRONG")) return "buy";
  if (s.includes("WATCH") || s.includes("SOLID") || s.includes("NEUTRAL")) return "watch";
  if (s.includes("AVOID") || s.includes("WEAK") || s.includes("INSUFFICIENT") || s.includes("ERROR")) return "avoid";
  if (s.includes("PENDING") || s.includes("LOADING")) return "watch";
  return "neutral";
}

function shortSignal(signal = "") {
  const s = String(signal || "").toUpperCase();
  if (s.includes("HOT") || s.includes("อย่าไล่ราคา")) return "HOT";
  if (s.includes("BUY") || s.includes("STRONG")) return "BUY";
  if (s.includes("WATCH")) return "WATCH";
  if (s.includes("AVOID") || s.includes("WEAK")) return "AVOID";
  if (s.includes("ERROR")) return "ERROR";
  if (s.includes("PENDING") || s.includes("LOADING")) return "PENDING";
  if (s.includes("NEUTRAL")) return "NEUTRAL";
  return signal || "—";
}

function signalText(signal = "") {
  const s = shortSignal(signal);
  if (s === "BUY") return "↗ BUY";
  if (s === "HOT") return "HOT — อย่าไล่ราคา";
  if (s === "WATCH") return "● WATCH";
  if (s === "AVOID") return "↘ AVOID";
  if (s === "ERROR") return "⚠ ERROR";
  if (s === "PENDING") return "⏳ PENDING";
  if (s === "NEUTRAL") return "○ NEUTRAL";
  return esc(s);
}

function marketGroupForTicker(ticker) {
  const t = normalizeTicker(ticker);
  if (t.endsWith(".BK")) return "TH";
  if (ETF_TICKERS.has(t)) return "ETF";
  return "US";
}

function currentQuoteFor(symbol) {
  return state.quotes[normalizeTicker(symbol)] || null;
}


function deriveTechnicalSignal(baseSignal, metrics = {}) {
  const raw = String(baseSignal || "NEUTRAL").trim();
  const upper = raw.toUpperCase();
  // Keep hard states untouched.
  if (upper.includes("AVOID") || upper.includes("WEAK") || upper.includes("ERROR") || upper.includes("PENDING") || upper.includes("LOADING")) return raw;
  const rsi = toNum(metrics.rsi);
  const ema20Pct = toNum(metrics.ema20Pct);
  const ema89Pct = toNum(metrics.ema89Pct);
  const ema200Pct = toNum(metrics.ema200Pct);
  const score = toNum(metrics.score);
  // HOT is a warning, not a bearish call: the trend may be good, but entry is chasing.
  // Previous UI used this for names with RSI too hot / distance already stretched.
  const hotByRsi = rsi !== null && rsi >= 70;
  const hotByDistance = (ema20Pct !== null && ema20Pct >= 15) || (ema89Pct !== null && ema89Pct >= 25) || (ema200Pct !== null && ema200Pct >= 45);
  if ((hotByRsi || hotByDistance) && (score === null || score >= 55)) return "HOT — อย่าไล่ราคา";
  return raw || "NEUTRAL";
}

function mapRow(row = {}) {
  const ticker = normalizeTicker(row.symbol || row.ticker);
  const quote = currentQuoteFor(ticker) || {};
  const series = Array.isArray(quote.series) ? quote.series : [];
  const latestSeries = series[series.length - 1] || {};
  const prevSeries = series[series.length - 2] || {};
  const close = toNum(row.close ?? row.regularMarketPrice ?? latestSeries.close);
  const prevClose = toNum(prevSeries.close);
  const dayPct = close !== null && prevClose ? ((close / prevClose) - 1) * 100 : null;
  const fundamental = quote.fundamental || {};
  const latest = quote.latest || row;
  const f = { ...fundamental, ...latest, ...row };
  const revenue = row.revenue ?? f.revenue ?? f.totalRevenue ?? null;
  const netIncome = row.netIncome ?? f.netIncome ?? f.netIncomeLoss ?? null;
  const eps = row.eps ?? f.eps ?? f.epsDiluted ?? null;
  const fcf = row.freeCashFlow ?? f.freeCashFlow ?? f.fcf ?? null;
  const margin = toNum(row.netMargin ?? row.operatingMargin ?? row.grossMargin ?? row.margin ?? f.netMargin ?? f.profitMargin);
  const debtEq = toNum(row.debtEquity ?? row.debtToEquity ?? row.debtEq ?? f.debtEquity ?? f.debtToEquity);
  const roe = toNum(row.roe ?? row.returnOnEquity ?? f.returnOnEquityTtm ?? f.returnOnEquity);

  return {
    raw: row,
    quote,
    ticker,
    exchange: row.exchange || row.exchangeName || row.fullExchangeName || row.instrumentType || "—",
    company: row.shortName || row.longName || row.company || row.name || row.instrumentType || ticker,
    score: toNum(row.score) ?? 0,
    signal: deriveTechnicalSignal(row.signal || "NEUTRAL", {
      rsi: row.rsi14,
      ema20Pct: row.pctVsEma20,
      ema89Pct: row.pctVsEma89,
      ema200Pct: row.pctVsEma200,
      score: row.score
    }),
    price: close,
    dayPct,
    rsi: toNum(row.rsi14),
    macd: toNum(row.macd1226),
    signal9: toNum(row.macdSignal9),
    macdHist: toNum(row.macdHist),
    vol20: toNum(row.volumeRatio20),
    ema5: toNum(row.ema5),
    ema20: toNum(row.ema20),
    ema89: toNum(row.ema89),
    ema200: toNum(row.ema200),
    ema5Pct: toNum(row.pctVsEma5),
    ema20Pct: toNum(row.pctVsEma20),
    ema89Pct: toNum(row.pctVsEma89),
    ema200Pct: toNum(row.pctVsEma200),
    high52: toNum(row.high52w),
    isPlaceholder: false,
    error: row.error || null,
    low52: toNum(row.low52w),
    pctFrom52wHigh: toNum(row.pctFrom52wHigh),
    pe: toNum(row.peRatio ?? row.pe ?? f.peRatio),
    ps: toNum(row.priceToSales ?? row.ps ?? f.priceToSalesRatio ?? f.ps),
    pb: toNum(row.priceToBook ?? row.pb ?? f.priceToBookRatio ?? f.pb),
    revYoy: toNum(row.revenueYoY ?? row.revYoy),
    epsYoy: toNum(row.epsYoY),
    margin,
    debtEq,
    roe,
    fundamentalScore: toNum(row.fundamentalScore) ?? toNum(f.fundamentalScore),
    fundamentalSignal: row.fundamentalSignal || f.fundamentalSignal || "—",
    fundamentalReasons: row.fundamentalReasons || f.fundamentalReasons || [],
    fundamentalHighlights: row.fundamentalHighlights || f.fundamentalHighlights || [],
    fundamentalSource: row.fundamentalSource || f.fundamentalSource || "SEC EDGAR companyfacts + submissions",
    latestQuarter: row.latestQuarter || f.latestQuarter || "—",
    periodEnd: row.earningsDate || row.periodEnd || f.periodEnd || "—",
    revenue,
    revenuePrevQuarter: row.revenuePrevQuarter ?? f.revenuePrevQuarter,
    revenueYearAgo: row.revenueYearAgo ?? f.revenueYearAgo,
    revenueQoQ: toNum(row.revenueQoQ ?? f.revenueQoQ),
    revenueYoY: toNum(row.revenueYoY ?? f.revenueYoY),
    netIncome,
    netIncomePrevQuarter: row.netIncomePrevQuarter ?? f.netIncomePrevQuarter,
    netIncomeYearAgo: row.netIncomeYearAgo ?? f.netIncomeYearAgo,
    profitQoQ: toNum(row.profitQoQ ?? row.netIncomeQoQ ?? f.profitQoQ),
    profitYoY: toNum(row.profitYoY ?? row.netIncomeYoY ?? f.profitYoY),
    eps,
    epsPrevQuarter: row.epsPrevQuarter ?? f.epsPrevQuarter,
    epsYearAgo: row.epsYearAgo ?? f.epsYearAgo,
    epsQoQ: toNum(row.epsQoQ ?? f.epsQoQ),
    fcf,
    guidance: {
      priorPeriod: row.priorCompanyGuidanceRevenuePeriod || f.priorCompanyGuidanceRevenuePeriod || "—",
      priorRevenue: row.priorCompanyGuidanceRevenue || f.priorCompanyGuidanceRevenue || null,
      priorConfidence: row.priorCompanyGuidanceRevenueConfidence || f.priorCompanyGuidanceRevenueConfidence || row.companyGuidanceRevenueConfidence || "—",
      actualVsPrior: row.actualVsPriorGuidanceRevenuePct || f.actualVsPriorGuidanceRevenuePct || null,
      nextPeriod: row.nextCompanyGuidanceRevenuePeriod || f.nextCompanyGuidanceRevenuePeriod || "—",
      nextRevenue: row.nextCompanyGuidanceRevenue || f.nextCompanyGuidanceRevenue || null,
    },
    reasons: row.reasons || latest.reasons || [],
    scoreParts: row.scoreParts || latest.scoreParts || {},
  };
}

function errorMapBySymbol() {
  const out = new Map();
  (state.errors || []).forEach(e => out.set(normalizeTicker(e.symbol), e.error || "Data unavailable"));
  return out;
}

function rowMapBySymbol() {
  const out = new Map();
  (state.rows || []).forEach(row => {
    const s = mapRow(row);
    if (s.ticker) out.set(s.ticker, s);
  });
  return out;
}

function allWatchlistStocks() {
  const rows = rowMapBySymbol();
  const errors = errorMapBySymbol();
  return state.watchlist.map(ticker => rows.get(ticker) || placeholderStock(ticker, errors.get(ticker)));
}

function passesFilters(s) {
  if (!s || s.isPlaceholder || s.error) return false;
  const f = state.filters;
  if (state.scannerTab === "technical") {
    if ((toNum(s.score) ?? 0) < f.score) return false;
    if (f.above200 && !((toNum(s.ema200Pct) ?? -999) > 0)) return false;
    if (f.emaStack && !(toNum(s.ema20) !== null && toNum(s.ema89) !== null && s.ema20 > s.ema89)) return false;
    if (f.sweetRsi && !(toNum(s.rsi) !== null && s.rsi >= 45 && s.rsi <= 65)) return false;
    if (f.volume20 && !((toNum(s.vol20) ?? 0) >= 1)) return false;
    if (f.macdSignal && !(toNum(s.macd) !== null && toNum(s.signal9) !== null && s.macd > s.signal9)) return false;
    return true;
  }
  return (toNum(s.fundamentalScore ?? s.score) ?? 0) >= f.score;
}

function currentStocks() {
  let stocks = allWatchlistStocks();
  if (state.activeMarketGroup !== "ALL" && state.activeMarketGroup !== "Custom") {
    stocks = stocks.filter(s => marketGroupForTicker(s.ticker) === state.activeMarketGroup);
  }
  stocks = stocks.filter(passesFilters);
  stocks.sort((a, b) => compareValues(a, b, state.sortKey, state.sortAsc));
  return stocks;
}

function scannerStocks() {
  let stocks = allWatchlistStocks();
  if (state.activeMarketGroup !== "ALL" && state.activeMarketGroup !== "Custom") {
    stocks = stocks.filter(s => marketGroupForTicker(s.ticker) === state.activeMarketGroup);
  }
  stocks = stocks.map(s => ({ ...s, _filteredOut: !passesFilters(s) }));
  stocks.sort((a, b) => {
    if (a.isPlaceholder !== b.isPlaceholder) return a.isPlaceholder ? 1 : -1;
    if (a._filteredOut !== b._filteredOut) return a._filteredOut ? 1 : -1;
    return compareValues(a, b, state.sortKey, state.sortAsc);
  });
  return stocks;
}

function compareValues(a, b, key, asc) {
  const av = sortValue(a, key);
  const bv = sortValue(b, key);
  let result;
  if (typeof av === "string" || typeof bv === "string") result = String(av || "").localeCompare(String(bv || ""));
  else result = (toNum(av) ?? -999999999) - (toNum(bv) ?? -999999999);
  return asc ? result : -result;
}

function sortValue(s, key) {
  const map = {
    ticker: s.ticker,
    score: state.scannerTab === "fundamental" ? (s.fundamentalScore ?? s.score) : s.score,
    price: s.price,
    ema5Pct: Math.abs(toNum(s.ema5Pct) ?? 999999),
    ema20Pct: Math.abs(toNum(s.ema20Pct) ?? 999999),
    ema89Pct: Math.abs(toNum(s.ema89Pct) ?? 999999),
    ema200Pct: Math.abs(toNum(s.ema200Pct) ?? 999999),
    rsi: s.rsi,
    revYoy: s.revYoy,
    revenueQoQ: s.revenueQoQ,
    profitQoQ: s.profitQoQ,
    profitYoy: s.profitYoy,
    epsQoQ: s.epsQoQ,
    epsYoy: s.epsYoy,
    fcf: s.fcf,
  };
  return key in map ? map[key] : s[key];
}

function getSelected() {
  const stocks = state.rows.map(mapRow);
  return stocks.find(s => s.ticker === state.selected) || stocks[0] || placeholderStock(state.selected || state.watchlist[0] || "NVDA");
}

function placeholderStock(ticker, error = null) {
  return {
    ticker: normalizeTicker(ticker), exchange: "—", company: error ? error : "Waiting for scan data", score: 0, signal: error ? "ERROR" : "PENDING", price: null, dayPct: null,
    rsi: null, macd: null, signal9: null, macdHist: null, vol20: null,
    ema5: null, ema20: null, ema89: null, ema200: null, ema5Pct: null, ema20Pct: null, ema89Pct: null, ema200Pct: null,
    high52: null, low52: null, revenue: null, netIncome: null, eps: null, fcf: null,
    reasons: [], fundamentalReasons: [], fundamentalHighlights: [], fundamentalSource: "—", scoreParts: {}, guidance: {}, quote: { series: [] }, raw: {}, isPlaceholder: true, error
  };
}

function maxDistance(stocks = currentStocks()) {
  const values = stocks.flatMap(s => [s.ema5Pct, s.ema20Pct, s.ema89Pct, s.ema200Pct].map(v => Math.abs(toNum(v) ?? 0)));
  return Math.max(...values, 1);
}

function barFill(value, max = maxDistance()) {
  const v = toNum(value);
  const width = v === null ? 0 : Math.max(3, Math.min(100, Math.abs(v) / max * 100));
  const cls = v !== null && v < 0 ? "red-soft" : pctClass(v);
  return `<div class="bar-track"><div class="bar-fill ${cls}" style="width:${width}%"></div></div>`;
}

function emaRows(stock, compact = false) {
  const rows = [["EMA5", stock.ema5, stock.ema5Pct], ["EMA20", stock.ema20, stock.ema20Pct], ["EMA89", stock.ema89, stock.ema89Pct], ["EMA200", stock.ema200, stock.ema200Pct]];
  const max = maxDistance(currentStocks());
  return rows.map(([label, price, pct]) => `
    <div class="${compact ? "ema-bar-row" : "distance-row"}">
      <span>${label}</span>
      <span>${fmtMoney(price)}</span>
      ${barFill(pct, max)}
      <span class="pct ${pctClass(pct)}">${pctLabel(pct)}</span>
    </div>`).join("");
}

function groupTickers() {
  return allWatchlistStocks();
}

function renderGroups() {
  const counts = { ALL: state.watchlist.length, US: 0, TH: 0, ETF: 0, Custom: 0 };
  state.watchlist.forEach(t => { counts[marketGroupForTicker(t)] += 1; });
  counts.Custom = Math.min(4, state.watchlist.length);
  const groups = [
    ["ALL", "⭐ All", counts.ALL],
    ["US", "🇺🇸 US", counts.US],
    ["TH", "🇹🇭 TH", counts.TH],
    ["ETF", "📦 ETF", counts.ETF],
    ["Custom", "⭐ Custom", counts.Custom],
  ];
  const groupButtons = groups.map(([key, label, count]) => `<button class="market-btn ${state.activeMarketGroup === key ? "active" : ""}" data-market-group="${key}">${label} <span>${count}</span></button>`).join("");
  ["marketGroups", "mobileMarketGroups"].forEach(id => { const el = $("#" + id); if (el) el.innerHTML = groupButtons; });

  const stocks = groupTickers();
  const mobileStocks = (state.activeMarketGroup === "ALL" || state.activeMarketGroup === "Custom") ? stocks : stocks.filter(s => marketGroupForTicker(s.ticker) === state.activeMarketGroup);
  const chips = mobileStocks.map(s => `<button class="chip ${signalClass(s.signal)} ${s.ticker === state.selected ? "active" : ""}" data-select="${esc(s.ticker)}">${esc(s.ticker)}</button>`).join("") + `<button class="chip neutral" data-add-symbol>+ Add</button>`;
  const mobileChipRow = $("#mobileChipRow");
  if (mobileChipRow) mobileChipRow.innerHTML = chips;

  const desktopWatchlist = $("#desktopWatchlist");
  if (desktopWatchlist) desktopWatchlist.innerHTML = stocks.map(s => `
    <button class="watch-row ${s.ticker === state.selected ? "active" : ""}" data-select="${esc(s.ticker)}">
      <span class="logo-box ${signalClass(s.signal) === "buy" ? "green" : (signalClass(s.signal) === "watch" || signalClass(s.signal) === "hot") ? "orange" : signalClass(s.signal) === "avoid" ? "red" : ""}">${esc(s.ticker[0] || "?")}</span>
      <span class="watch-name"><strong>${esc(s.ticker)}</strong><span>${esc(s.exchange || marketGroupForTicker(s.ticker))}</span></span>
      <span class="signal-dot ${signalClass(s.signal)}">● ${esc(shortSignal(s.signal))}</span>
    </button>`).join("");
}

function emaCell(price, pct) {
  return `<td><span class="ema-cell"><span>${fmtMoney(price)}</span><strong class="pct ${pctClass(pct)}">${pctLabel(pct)}</strong></span></td>`;
}

function fundStackCell(rows = []) {
  return `<td><span class="fund-stack">${rows.map(([label, value, cls = ""]) => `<span><em>${esc(label)}</em><strong class="${cls}">${value ?? "—"}</strong></span>`).join("")}</span></td>`;
}

function visibleTechnicalColumns() {
  const defs = [
    { key: "ticker", label: "Ticker", sort: "ticker", cell: s => `<td><strong class="num">${esc(s.ticker)}</strong><small>${esc(s.exchange || "")}</small></td>` },
    { key: "score", label: "Score", sort: "score", cell: s => `<td class="num">${fmt(s.score, 0)}</td>` },
    { key: "signal", label: "Signal", cell: s => `<td><span class="signal-badge ${signalClass(s.signal)}">${signalText(s.signal)}</span></td>` },
    { key: "price", label: "Price", sort: "price", cell: s => `<td class="price">${fmtMoney(s.price)}<small class="pct ${pctClass(s.dayPct)}">${pctLabel(s.dayPct)}</small></td>` },
    { key: "ema5", label: "EMA5 / %vs", sort: "ema5Pct", cell: s => emaCell(s.ema5, s.ema5Pct) },
    { key: "ema20", label: "EMA20 / %vs", sort: "ema20Pct", cell: s => emaCell(s.ema20, s.ema20Pct) },
    { key: "ema89", label: "EMA89 / %vs", sort: "ema89Pct", cell: s => emaCell(s.ema89, s.ema89Pct) },
    { key: "ema200", label: "EMA200 / %vs", sort: "ema200Pct", cell: s => emaCell(s.ema200, s.ema200Pct) },
    { key: "rsi", label: "RSI", sort: "rsi", cell: s => `<td class="num rsi-cell">${fmt(s.rsi, 1)}</td>` },
    { key: "macdHist", label: "MACD Hist", sort: "macdHist", cell: s => `<td class="num pct ${pctClass(s.macdHist)}">${fmt(s.macdHist, 3)}</td>` },
    { key: "vol20", label: "Vol/20D", sort: "vol20", cell: s => `<td class="num">${s.vol20 === null ? "—" : `${fmt(s.vol20, 2)}x`}</td>` },
    { key: "high52", label: "52W High", sort: "high52", cell: s => `<td class="price">${fmtMoney(s.high52)}</td>` },
  ];
  return defs.filter(c => state.columns[c.key] !== false);
}

function visibleFundamentalColumns() {
  const defs = [
    { key: "fundTicker", label: "Ticker", sort: "ticker", cell: s => `<td><strong class="num">${esc(s.ticker)}</strong><small>${esc(s.exchange || "")}</small></td>` },
    { key: "fundScore", label: "Fund Score / Signal", sort: "score", cell: s => fundStackCell([["Score", fmt(s.fundamentalScore ?? s.score, 0), "num"], ["Signal", `<span class="signal-badge ${signalClass(s.fundamentalSignal || s.signal)}">${esc(shortSignal(s.fundamentalSignal || s.signal))}</span>`]]) },
    { key: "fundQuarter", label: "Quarter / Period", cell: s => fundStackCell([["Latest", esc(s.latestQuarter || "—")], ["End", esc(s.periodEnd || "—")]]) },
    { key: "fundRevenue", label: "Revenue / QoQ / YoY", sort: "revYoy", cell: s => fundStackCell([["Revenue", fmtCompact(s.revenue)], ["Prev Q", fmtCompact(s.revenuePrevQuarter)], ["QoQ", `<span class="pct ${fundPctClass(s.revenueQoQ)}">${pctLabel(s.revenueQoQ)}</span>`], ["YoY", `<span class="pct ${fundPctClass(s.revenueYoY)}">${pctLabel(s.revenueYoY)}</span>`]]) },
    { key: "fundNetIncome", label: "Net Income / QoQ / YoY", cell: s => fundStackCell([["Net Inc", fmtCompact(s.netIncome)], ["Prev Q", fmtCompact(s.netIncomePrevQuarter)], ["QoQ", `<span class="pct ${fundPctClass(s.profitQoQ)}">${pctLabel(s.profitQoQ)}</span>`], ["YoY", `<span class="pct ${fundPctClass(s.profitYoY)}">${pctLabel(s.profitYoY)}</span>`]]) },
    { key: "fundEps", label: "EPS / QoQ / YoY", sort: "epsYoy", cell: s => fundStackCell([["EPS", fmt(s.eps, 3)], ["Prev Q", fmt(s.epsPrevQuarter, 3)], ["QoQ", `<span class="pct ${fundPctClass(s.epsQoQ)}">${pctLabel(s.epsQoQ)}</span>`], ["YoY", `<span class="pct ${fundPctClass(s.epsYoy)}">${pctLabel(s.epsYoy)}</span>`]]) },
    { key: "fundFcf", label: "FCF", cell: s => fundStackCell([["FCF", fmtCompact(s.fcf)], ["Rev YoY", `<span class="pct ${fundPctClass(s.revenueYoY)}">${pctLabel(s.revenueYoY)}</span>`]]) },
    { key: "fundMargins", label: "Margins / Debt", cell: s => fundStackCell([["Margin", s.margin === null ? "—" : `${fmt(s.margin, 1)}%`], ["Debt/Eq", fmt(s.debtEq, 2)], ["ROE", s.roe === null ? "—" : `${fmt(s.roe, 1)}%`]]) },
    { key: "fundGuidance", label: "Guidance", cell: s => fundStackCell([["Prior", esc(s.guidance?.priorPeriod || "—")], ["Rev Mid", fmtCompact(s.guidance?.priorRevenue)], ["Conf", esc(s.guidance?.priorConfidence || "—")]]) },
  ];
  return defs.filter(c => state.columns[c.key] !== false);
}

function renderTableHeader(tableId, columns) {
  const table = $(tableId);
  if (!table) return;
  const row = table.querySelector("thead tr");
  if (!row) return;
  row.innerHTML = columns.map(c => `<th ${c.sort ? `data-sort="${c.sort}"` : ""} class="${state.sortKey === c.sort ? "sorted" : ""}">${esc(c.label)}${state.sortKey === c.sort ? (state.sortAsc ? " ↑" : " ↓") : ""}</th>`).join("");
}

function renderTechnicalTable() {
  const body = $("#technicalTableBody");
  if (!body) return;
  const cols = visibleTechnicalColumns();
  renderTableHeader("#technicalTable", cols);
  if (state.loading) {
    body.innerHTML = Array.from({ length: 6 }).map(() => `<tr class="skeleton-row">${cols.map(() => `<td><span class="skeleton-line"></span></td>`).join("")}</tr>`).join("");
    return;
  }
  const rows = scannerStocks();
  if (!rows.length) {
    let hint = state.errors?.length
      ? `Scan failed / no market data returned. First error: ${esc(state.errors[0].symbol || "")}: ${esc(state.errors[0].error || "")}`
      : "No stocks passed filters. Try lowering score or unchecking filters.";
    if (!state.rows.length && !state.errors?.length) hint = "No scan data loaded yet. Click Scan Now. If this stays empty, make sure you opened http://localhost:8787 from python app.py, not the static HTML file.";
    body.innerHTML = `<tr><td colspan="${Math.max(cols.length, 1)}" class="muted-empty">${hint}</td></tr>`;
    return;
  }
  body.innerHTML = rows.map(s => {
    const extended = (toNum(s.ema89Pct) ?? 0) > 30 || (toNum(s.ema200Pct) ?? 0) > 30;
    const rowState = s.isPlaceholder ? "pending-row" : s._filteredOut ? "filtered-out" : "";
    return `<tr class="${s.ticker === state.selected ? "active-row" : ""} ${extended ? "extended-row" : ""} ${rowState}" data-select="${esc(s.ticker)}" title="${s.error ? esc(s.error) : s._filteredOut ? "Filtered out by current scan filters" : ""}">${cols.map(c => c.cell(s)).join("")}</tr>`;
  }).join("");
}

function renderTechnicalMobile() {
  const wrap = $("#technicalMobileCards");
  if (!wrap) return;
  const rows = scannerStocks();
  if (!rows.length) { wrap.innerHTML = `<div class="mobile-empty">No stocks passed filters.</div>`; return; }
  wrap.innerHTML = rows.map(s => `
    <article class="stock-card ${s.isPlaceholder ? "pending-card" : s._filteredOut ? "filtered-card" : ""}" data-select="${esc(s.ticker)}">
      <div class="stock-card-header">
        <div class="stock-card-title">
          <span class="logo-box ${signalClass(s.signal) === "buy" ? "green" : (signalClass(s.signal) === "watch" || signalClass(s.signal) === "hot") ? "orange" : signalClass(s.signal) === "avoid" ? "red" : ""}">${esc(s.ticker[0])}</span>
          <div class="ticker-line"><strong>${esc(s.ticker)}</strong><span>${esc(s.exchange || "—")}</span></div>
        </div>
        <div class="card-score"><strong>${fmt(s.score, 0)}</strong><span>Score</span></div>
      </div>
      <div class="card-price-row"><span>${fmtMoney(s.price)}</span><span>RSI: ${fmt(s.rsi, 1)}</span><span class="signal-badge ${signalClass(s.signal)}">${signalText(s.signal)}</span></div>
      <div class="ema-bars">${emaRows(s, true)}</div>
    </article>`).join("");
}

function renderTechnicalMobileTable() {
  const body = $("#technicalMobileTableBody");
  if (!body) return;
  const rows = scannerStocks();
  if (!rows.length) { body.innerHTML = `<tr><td class="sticky-col">No result</td><td colspan="7">Adjust filters</td></tr>`; return; }
  body.innerHTML = rows.map(s => `
    <tr class="${s.ticker === state.selected ? "active-row" : ""} ${s.isPlaceholder ? "pending-row" : s._filteredOut ? "filtered-out" : ""}" data-select="${esc(s.ticker)}">
      <td class="sticky-col"><strong class="num">${esc(s.ticker)}</strong><span>${esc(s.company || s.exchange || "")}</span></td>
      <td class="num ${s.score >= 85 ? "score-good" : s.score >= 70 ? "score-watch" : "score-weak"}">${fmt(s.score, 0)}</td>
      <td><span class="signal-badge ${signalClass(s.signal)}">${esc(shortSignal(s.signal))}</span></td>
      <td class="price">${fmtMoney(s.price)}<small class="pct ${pctClass(s.dayPct)}">${pctLabel(s.dayPct)}</small></td>
      <td><strong class="pct ${pctClass(s.ema20Pct)}">${pctLabel(s.ema20Pct)}</strong><span class="dot ${pctClass(s.ema20Pct)}"></span></td>
      <td><strong class="pct ${pctClass(s.ema89Pct)}">${pctLabel(s.ema89Pct)}</strong><span class="dot ${pctClass(s.ema89Pct)}"></span></td>
      <td><strong class="pct ${pctClass(s.ema200Pct)}">${pctLabel(s.ema200Pct)}</strong><span class="dot ${pctClass(s.ema200Pct)}"></span></td>
      <td class="num rsi-cell">${fmt(s.rsi, 1)}</td>
    </tr>`).join("");
}

function renderFundamental() {
  const rows = scannerStocks();
  const desktop = $("#fundamentalTableBody");
  const cols = visibleFundamentalColumns();
  renderTableHeader("#fundamentalTable", cols);
  if (desktop) {
    if (state.loading || state.fundamentalLoading) {
      desktop.innerHTML = Array.from({ length: 6 }).map(() => `<tr class="skeleton-row">${cols.map(() => `<td><span class="skeleton-line"></span><span class="skeleton-line"></span></td>`).join("")}</tr>`).join("");
    } else {
      desktop.innerHTML = rows.length ? rows.map(s => `
        <tr data-select="${esc(s.ticker)}" class="${s.ticker === state.selected ? "active-row" : ""} ${s.isPlaceholder ? "pending-row" : s._filteredOut ? "filtered-out" : ""}" title="${s.error ? esc(s.error) : s._filteredOut ? "Filtered out by current scan filters" : ""}">
          ${cols.map(c => c.cell(s)).join("")}
        </tr>`).join("") : `<tr><td colspan="${Math.max(cols.length, 1)}" class="muted-empty">No fundamental rows. Click Fundamental to load data, or click Scan Now.</td></tr>`;
    }
  }

  const cards = $("#fundamentalMobileCards");
  if (cards) {
    if (state.loading || state.fundamentalLoading) { cards.innerHTML = Array.from({ length: 4 }).map(() => `<article class="stock-card skeleton-card"><span class="skeleton-line wide"></span><span class="skeleton-line"></span><span class="skeleton-line"></span></article>`).join(""); }
    else cards.innerHTML = rows.map(s => `
    <article class="stock-card ${s.isPlaceholder ? "pending-card" : s._filteredOut ? "filtered-card" : ""}" data-select="${esc(s.ticker)}">
      <div class="stock-card-header">
        <div class="stock-card-title"><span class="logo-box">${esc(s.ticker[0])}</span><div class="ticker-line"><strong>${esc(s.ticker)}</strong><span>${esc(s.exchange || "—")}</span></div></div>
        <span class="signal-badge ${signalClass(s.fundamentalSignal || s.signal)}">${signalText(s.fundamentalSignal || s.signal)}</span>
      </div>
      <div class="fund-card-section"><h3>📅 Quarter</h3><div class="fund-grid">${miniMetric("Latest", esc(s.latestQuarter || "—"))}${miniMetric("Period End", esc(s.periodEnd || "—"))}${miniMetric("Score", fmt(s.fundamentalScore ?? s.score, 0))}</div></div>
      <div class="fund-card-section"><h3>💰 Earnings</h3><div class="fund-grid">${miniMetric("Revenue", fmtCompact(s.revenue))}${miniMetric("Rev QoQ", pctLabel(s.revenueQoQ))}${miniMetric("Rev YoY", pctLabel(s.revenueYoY))}${miniMetric("Net Income", fmtCompact(s.netIncome))}${miniMetric("Profit QoQ", pctLabel(s.profitQoQ))}${miniMetric("Profit YoY", pctLabel(s.profitYoY))}${miniMetric("EPS", fmt(s.eps, 3))}${miniMetric("EPS QoQ", pctLabel(s.epsQoQ))}${miniMetric("EPS YoY", pctLabel(s.epsYoy))}</div></div>
      <div class="fund-card-section"><h3>🏦 Quality</h3><div class="fund-grid">${miniMetric("FCF", fmtCompact(s.fcf))}${miniMetric("Margin", s.margin === null ? "—" : `${fmt(s.margin, 1)}%`)}${miniMetric("Debt/Eq", fmt(s.debtEq, 2))}</div></div>
    </article>`).join("");
  }
}


function cellHtmlToSticky(html) {
  return String(html || "").replace(/^<td(\s|>)/, '<td class="sticky-col"$1');
}

function yahooQuoteSymbol(ticker) {
  return encodeURIComponent(String(ticker || "").trim().toUpperCase());
}

function yahooAnalysisUrl(ticker) {
  return `https://finance.yahoo.com/quote/${yahooQuoteSymbol(ticker)}/analysis/`;
}

function yahooQuoteUrl(ticker) {
  return `https://finance.yahoo.com/quote/${yahooQuoteSymbol(ticker)}/`;
}

function updateMobileSortLabel() {
  const label = $("#mobileSortLabel");
  if (!label) return;
  const names = { score: "Score", ema20Pct: "EMA20 nearest", ema89Pct: "EMA89 nearest", ema200Pct: "EMA200 nearest", rsi: "RSI", revYoy: "Rev YoY", epsYoy: "EPS YoY", ticker: "Ticker" };
  label.textContent = `Sort: ${names[state.sortKey] || state.sortKey} ${state.sortAsc ? "↑" : "↓"}`;
}

function renderFundamentalMobileTable() {
  const table = $("#fundamentalMobileTable");
  const body = $("#fundamentalMobileTableBody");
  if (!body) return;
  if (table) table.classList.add("fundamental-mobile-table");
  const cols = visibleFundamentalColumns();
  if (table) {
    const head = table.querySelector("thead tr");
    if (head) {
      head.innerHTML = cols.map((c, i) => `<th ${i === 0 ? 'class="sticky-col"' : ''} ${c.sort ? `data-sort="${c.sort}"` : ""}>${esc(c.label)}${state.sortKey === c.sort ? (state.sortAsc ? " ↑" : " ↓") : ""}</th>`).join("");
    }
  }
  if (state.loading || state.fundamentalLoading) {
    body.innerHTML = Array.from({ length: 5 }).map(() => `<tr class="skeleton-row"><td class="sticky-col"><span class="skeleton-line"></span></td><td colspan="${Math.max(cols.length - 1, 1)}"><span class="skeleton-line wide"></span></td></tr>`).join("");
    return;
  }
  const rows = scannerStocks();
  body.innerHTML = rows.map(s => {
    const cells = cols.map((c, i) => i === 0 ? cellHtmlToSticky(c.cell(s)) : c.cell(s)).join("");
    return `<tr class="${s.ticker === state.selected ? "active-row" : ""} ${s.isPlaceholder ? "pending-row" : s._filteredOut ? "filtered-out" : ""}" data-select="${esc(s.ticker)}">${cells}</tr>`;
  }).join("");
}

function miniMetric(label, value) {
  return `<div class="fund-mini"><span>${esc(label)}</span><strong>${value ?? "—"}</strong></div>`;
}

function renderDetail() {
  const s = getSelected();
  const detailTabs = `
    <div class="detail-tabs" role="tablist" aria-label="Detail sections">
      <button class="${state.detailTab === "technical" ? "active" : ""}" data-detail-tab="technical">Technical</button>
      <button class="${state.detailTab === "setup" ? "active" : ""}" data-detail-tab="setup">Setup</button>
      <button class="${state.detailTab === "fundamental" ? "active" : ""}" data-detail-tab="fundamental">Fundamental</button>
      <button class="${state.detailTab === "playbook" ? "active" : ""}" data-detail-tab="playbook">Playbook</button>
    </div>`;
  const content = desktopDetailHtml(s);
  const detailEl = $("#detailCard");
  if (detailEl) detailEl.innerHTML = content;
  const mobileTitle = $("#mobileDetailTitle");
  if (mobileTitle) mobileTitle.textContent = `${s.ticker} Detail`;
  const mobileBody = $("#mobileDetailBody");
  if (mobileBody) mobileBody.innerHTML = `<section class="detail-card">${content}</section>`;
  const fundDash = $("#fundamentalDashboard");
  if (fundDash) fundDash.innerHTML = fundamentalDashboardHtml(s, false);
  const setup = $("#setupSummary");
  if (setup) setup.innerHTML = setupHtml(s, false);
  const playbook = $("#playbookCards");
  if (playbook) playbook.innerHTML = playbookHtml(false);
  renderChartModal();
}

function desktopDetailHtml(s) {
  return `
    <div class="detail-header">
      <div class="detail-identity">
        <span class="logo-box ${signalClass(s.signal) === "buy" ? "green" : (signalClass(s.signal) === "watch" || signalClass(s.signal) === "hot") ? "orange" : signalClass(s.signal) === "avoid" ? "red" : ""}">${esc(s.ticker[0] || "?")}</span>
        <div><h2>${esc(s.ticker)}</h2><p>${esc(s.exchange || "—")} · ${esc(s.raw.currency || "")}</p></div>
      </div>
      <span class="signal-badge ${signalClass(s.signal)}">${signalText(s.signal)} ZONE</span>
      <div class="detail-price">${fmtMoney(s.price)} <span class="pct ${pctClass(s.dayPct)}">${pctLabel(s.dayPct)}</span></div>
      <p class="detail-meta">Score ${fmt(s.score, 0)}/100 · RSI ${fmt(s.rsi, 1)} · MACD ${fmt(s.macd, 3)} · 52Wks ${fmtMoney(s.low52)} – ${fmtMoney(s.high52)}</p>
      <div class="detail-load"><input value="${esc(s.ticker)}" aria-label="Load symbol" /><button class="primary-btn" data-load-symbol>Load</button></div>
      ${detailTabs(s)}
    </div>
    <div class="detail-tab-content">${detailContentHtml(s)}</div>`;
}

function detailTabs(s = getSelected()) {
  const sig = signalClass(s.signal);
  const setupClass = sig === "buy" ? "setup-buy" : sig === "watch" ? "setup-watch" : sig === "avoid" ? "setup-avoid" : "setup-neutral";
  return `
    <div class="detail-tabs" role="tablist" aria-label="Detail sections">
      <button class="${state.detailTab === "technical" ? "active" : ""}" data-detail-tab="technical">Technical</button>
      <button class="${setupClass} ${state.detailTab === "setup" ? "active" : ""}" data-detail-tab="setup">Setup <span class="setup-tab-dot"></span></button>
      <button class="${state.detailTab === "fundamental" ? "active" : ""}" data-detail-tab="fundamental">Fundamental</button>
      <button class="${state.detailTab === "playbook" ? "active" : ""}" data-detail-tab="playbook">Playbook</button>
    </div>`;
}

function desktopSnapshotHtml(s) {
  return `
    <div class="desktop-snapshot">
      <div class="snapshot-top">
        <div><span class="snapshot-kicker">Selected Stock</span><h2>${esc(s.ticker)}</h2><p>${esc(s.company || s.exchange || "")}</p></div>
        <span class="signal-badge ${signalClass(s.signal)}">${signalText(s.signal)}</span>
      </div>
      <div class="snapshot-price-row"><div><strong>${fmtMoney(s.price)}</strong><span class="pct ${pctClass(s.dayPct)}">${pctLabel(s.dayPct)}</span></div><div class="snapshot-load"><button class="primary-btn" data-load-symbol>Refresh</button></div></div>
      <div class="snapshot-metrics"><div><span>Score</span><strong>${fmt(s.score, 0)}/100</strong></div><div><span>RSI</span><strong>${fmt(s.rsi, 1)}</strong></div><div><span>52W Range</span><strong>${fmtMoney(s.low52)} – ${fmtMoney(s.high52)}</strong></div></div>
      <div class="snapshot-section"><h3>Distance from EMA</h3>${emaRows(s)}</div>
      <div class="snapshot-section"><h3>Fundamental Snapshot</h3><div class="snapshot-fund-grid">${miniMetric("Revenue", fmtCompact(s.revenue))}${miniMetric("Net Income", fmtCompact(s.netIncome))}${miniMetric("EPS", fmt(s.eps, 3))}${miniMetric("Rev YoY", pctLabel(s.revYoy, 0))}${miniMetric("EPS YoY", pctLabel(s.epsYoy, 0))}${miniMetric("ROE", s.roe === null ? "—" : `${fmt(s.roe, 1)}%`)}</div></div>
      <div class="snapshot-section"><h3>Playbook Highlights</h3><button class="snapshot-rule" data-detail-tab="setup">↗ Trend <span>Price/EMA stack</span></button><button class="snapshot-rule" data-detail-tab="technical">⚡ Momentum <span>RSI/MACD/Volume</span></button><button class="snapshot-rule" data-detail-tab="fundamental">📊 Fundamental <span>SEC dashboard</span></button></div>
    </div>`;
}

function detailContentHtml(s) {
  if (state.detailTab === "setup") return `<div class="padded-detail-section">${setupHtml(s, false)}</div>`;
  if (state.detailTab === "fundamental") return `<div class="padded-detail-section">${fundamentalDashboardHtml(s, false)}</div>`;
  if (state.detailTab === "playbook") return `<div class="padded-detail-section">${playbookHtml(false)}</div>`;
  return `
    <div class="chart-stack">
      ${priceChartPanel(s)}
      ${chartPanel("RSI(14)", `RSI14: ${fmt(s.rsi, 1)}`, rsiChartSvg(s))}
      ${chartPanel("MACD(12,26,9)", `MACD: ${fmt(s.macd,3)} · Signal: ${fmt(s.signal9,3)}`, macdChartSvg(s))}
      ${chartPanel("VOL(5,10)", `Vol/20D: ${s.vol20 === null ? "—" : `${fmt(s.vol20, 2)}x`}`, volumeChartSvg(s))}
    </div>`;
}

function priceChartPanel(s) {
  const mode = state.priceChartMode === "candles" ? "candles" : "line";
  return `<section class="chart-panel price-chart-panel" data-open-chart-modal title="Click chart to expand">
    <div class="chart-title price-chart-title">
      <div><h3>Price / EMA</h3><span>${mode === "candles" ? "Candles" : "Close line"}, EMA5, EMA20, EMA89, EMA200</span></div>
      <div class="chart-actions" data-chart-controls>
        <div class="chart-mode-toggle" role="group" aria-label="Price chart mode">
          <button type="button" class="${mode === "line" ? "active" : ""}" data-chart-mode="line">Line</button>
          <button type="button" class="${mode === "candles" ? "active" : ""}" data-chart-mode="candles">Candles</button>
        </div>
        <button type="button" class="chart-expand-btn" data-open-chart-modal aria-label="Expand chart">⛶</button>
      </div>
    </div>
    ${priceChartSvg(s)}
  </section>`;
}

function chartPanel(title, subtitle, svg) {
  return `<section class="chart-panel"><div class="chart-title"><h3>${title}</h3><span>${subtitle}</span></div>${svg}</section>`;
}

function svgLine(points, color, width = 2, dash = "") {
  if (!points.length) return "";
  const d = points.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ");
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="${width}" ${dash ? `stroke-dasharray="${dash}"` : ""} stroke-linecap="round" stroke-linejoin="round"/>`;
}

function scaleSeries(values, width = 300, height = 120, pad = 8, minForced = null, maxForced = null) {
  const clean = values.map(toNum).filter(v => v !== null);
  if (!clean.length) return [];
  const min = minForced !== null ? minForced : Math.min(...clean);
  const max = maxForced !== null ? maxForced : Math.max(...clean);
  const span = max === min ? 1 : max - min;
  const step = values.length <= 1 ? 0 : (width - pad * 2) / (values.length - 1);
  return values.map((v, i) => {
    const n = toNum(v);
    if (n === null) return null;
    return [pad + i * step, height - pad - ((n - min) / span) * (height - pad * 2)];
  }).filter(Boolean);
}

function recentSeries(s, n = 60) {
  const arr = s.quote?.series || [];
  return arr.slice(Math.max(0, arr.length - n));
}

function fmtDateLabel(value) {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value).slice(5, 10);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function chartAxisLabels(series) {
  if (!series.length) return "";
  const first = series[0]?.date;
  const mid = series[Math.floor(series.length / 2)]?.date;
  const last = series[series.length - 1]?.date;
  return `<div class="chart-axis"><span>${esc(fmtDateLabel(first))}</span><span>${esc(fmtDateLabel(mid))}</span><span>${esc(fmtDateLabel(last))}</span></div>`;
}

function candleSvg(series, min, max, width = 320, height = 140, pad = 10) {
  const span = max === min ? 1 : max - min;
  const y = (v) => height - pad - ((toNum(v) - min) / span) * (height - pad * 2);
  const step = series.length <= 1 ? width - pad * 2 : (width - pad * 2) / series.length;
  const candleW = Math.max(2, Math.min(7, step * 0.52));
  return series.map((x, i) => {
    const o = toNum(x.open), h = toNum(x.high), l = toNum(x.low), c = toNum(x.close);
    if ([o,h,l,c].some(v => v === null)) return "";
    const cx = pad + i * step + step / 2;
    const up = c >= o;
    const color = up ? "#3fb950" : "#f85149";
    const top = Math.min(y(o), y(c));
    const bodyH = Math.max(1.6, Math.abs(y(o) - y(c)));
    return `<g class="candle ${up ? "up" : "down"}"><line x1="${cx.toFixed(2)}" y1="${y(h).toFixed(2)}" x2="${cx.toFixed(2)}" y2="${y(l).toFixed(2)}" stroke="${color}" stroke-width="1.1"/><rect x="${(cx - candleW/2).toFixed(2)}" y="${top.toFixed(2)}" width="${candleW.toFixed(2)}" height="${bodyH.toFixed(2)}" rx="0.8" fill="${color}" opacity="0.9"/></g>`;
  }).join("");
}

function priceChartSvg(s) {
  const series = recentSeries(s, 60);
  if (!series.length) return `<div class="chart-empty">ยังไม่มี series จริง — กด Scan Now หรือ Load ticker เพื่อดึงข้อมูลจาก backend</div>`;
  const closes = series.map(x => x.close);
  const ema5 = series.map(x => x.ema5);
  const ema20 = series.map(x => x.ema20);
  const ema89 = series.map(x => x.ema89);
  const ema200 = series.map(x => x.ema200);
  const all = [...closes, ...ema5, ...ema20, ...ema89, ...ema200].map(toNum).filter(v => v !== null);
  const min = all.length ? Math.min(...all) : 0;
  const max = all.length ? Math.max(...all) : 1;
  const pad = (max - min) * 0.06 || 1;
  const minBound = min - pad;
  const maxBound = max + pad;
  const closeLayer = state.priceChartMode === "candles"
    ? candleSvg(series, minBound, maxBound)
    : svgLine(scaleSeries(closes,320,140,10,minBound,maxBound), "#e6edf3", 2.4);
  const closeLabel = state.priceChartMode === "candles" ? "Candles" : "Close";
  return `<svg class="fake-chart" viewBox="0 0 320 140" preserveAspectRatio="none"><g class="grid-lines"><line x1="10" y1="35" x2="310" y2="35"/><line x1="10" y1="75" x2="310" y2="75"/><line x1="10" y1="115" x2="310" y2="115"/></g>${closeLayer}${svgLine(scaleSeries(ema5,320,140,10,minBound,maxBound), "#3fb950", 1.8)}${svgLine(scaleSeries(ema20,320,140,10,minBound,maxBound), "#58a6ff", 1.8)}${svgLine(scaleSeries(ema89,320,140,10,minBound,maxBound), "#e3822a", 1.8)}${svgLine(scaleSeries(ema200,320,140,10,minBound,maxBound), "#f85149", 1.8, "4 4")}</svg>${chartAxisLabels(series)}<div class="chart-legend"><span class="close">● ${closeLabel}</span><span class="green">● EMA5</span><span class="blue">● EMA20</span><span class="orange">● EMA89</span><span class="red">● EMA200</span></div>`;
}

function rsiChartSvg(s) {
  const rawSeries = recentSeries(s, 60);
  if (!rawSeries.length) return `<div class="chart-empty">ยังไม่มี RSI series</div>`;
  const series = rawSeries.map(x => x.rsi14);
  return `<svg class="fake-chart" viewBox="0 0 320 140" preserveAspectRatio="none"><g class="grid-lines"><line x1="10" y1="30" x2="310" y2="30"/><line x1="10" y1="70" x2="310" y2="70"/><line x1="10" y1="110" x2="310" y2="110"/></g><line x1="10" y1="42" x2="310" y2="42" stroke="#f85149" stroke-dasharray="4 5"/><line x1="10" y1="70" x2="310" y2="70" stroke="#8b949e" stroke-dasharray="4 5"/><line x1="10" y1="98" x2="310" y2="98" stroke="#3fb950" stroke-dasharray="4 5"/>${svgLine(scaleSeries(series,320,140,10,0,100), "#c084fc", 2.2)}</svg>${chartAxisLabels(rawSeries)}`;
}

function macdChartSvg(s) {
  const series = recentSeries(s, 60);
  if (!series.length) return `<div class="chart-empty">ยังไม่มี MACD series</div>`;
  const macd = series.map(x => x.macd1226);
  const sig = series.map(x => x.macdSignal9);
  const hist = series.map(x => x.macdHist);
  const vals = [...macd, ...sig, ...hist].map(toNum).filter(v => v !== null);
  const maxAbs = Math.max(...vals.map(v => Math.abs(v)), 1);
  const bars = hist.map(toNum).map((v, i) => {
    if (v === null) return "";
    const x = 10 + i * (300 / Math.max(hist.length, 1));
    const h = Math.abs(v) / maxAbs * 45;
    const y = v >= 0 ? 70 - h : 70;
    return `<rect x="${x}" y="${y}" width="3" height="${h}" fill="${v >= 0 ? "#3fb950" : "#f85149"}" opacity="0.85"/>`;
  }).join("");
  return `<svg class="fake-chart" viewBox="0 0 320 140" preserveAspectRatio="none"><line x1="10" y1="70" x2="310" y2="70" stroke="#30363d"/>${bars}${svgLine(scaleSeries(macd,320,140,10,-maxAbs,maxAbs), "#58a6ff", 2)}${svgLine(scaleSeries(sig,320,140,10,-maxAbs,maxAbs), "#e3822a", 2)}</svg>${chartAxisLabels(series)}`;
}

function volumeChartSvg(s) {
  const series = recentSeries(s, 60);
  if (!series.length) return `<div class="chart-empty">ยังไม่มี Volume series</div>`;
  const vols = series.map(x => toNum(x.volume) ?? 0);
  const max = Math.max(...vols, 1);
  const bars = vols.map((v, i) => {
    const x = 10 + i * (300 / Math.max(vols.length, 1));
    const h = (v / max) * 90;
    return `<rect x="${x}" y="${120 - h}" width="3" height="${h}" fill="${i % 3 === 0 ? "#f85149" : "#58a6ff"}" opacity="0.75"/>`;
  }).join("");
  return `<svg class="fake-chart" viewBox="0 0 320 140" preserveAspectRatio="none"><g class="grid-lines"><line x1="10" y1="35" x2="310" y2="35"/><line x1="10" y1="75" x2="310" y2="75"/><line x1="10" y1="115" x2="310" y2="115"/></g>${bars}</svg>${chartAxisLabels(series)}`;
}

function setupHtml(s, wrapped = true) {
  const parts = s.scoreParts || {};
  const trend = toNum(parts.trend ?? parts.Trend) ?? Math.min(40, Math.round((toNum(s.score) ?? 0) * 0.40));
  const momentum = toNum(parts.momentum ?? parts.Momentum) ?? Math.min(30, Math.round((toNum(s.score) ?? 0) * 0.30));
  const rsi = toNum(parts.rsi ?? parts.RSI) ?? (s.rsi >= 45 && s.rsi <= 65 ? 20 : 10);
  const volume = toNum(parts.volume ?? parts.Volume) ?? (s.vol20 >= 1 ? 10 : 5);
  const reasons = (Array.isArray(s.reasons) && s.reasons.length ? s.reasons : [
    s.ema200Pct > 0 ? "✅ Price above EMA200 = major trend still constructive" : "⚠️ Price below EMA200 = structure still weak",
    s.ema20 > s.ema89 ? "✅ EMA20 > EMA89 = medium trend supports setup" : "⚠️ EMA20 below EMA89 = wait for trend repair",
    s.rsi >= 45 && s.rsi <= 65 ? "✅ RSI 45–65 = sweet spot" : "⚠️ RSI outside sweet spot",
    s.macd > s.signal9 ? "✅ MACD > Signal = momentum supports" : "⚠️ MACD still below signal",
  ]).slice(0, 8);
  const setupTone = signalClass(s.signal);
  const html = `
    <div class="setup-title-row"><h2>Setup อ่านยังไง</h2><span class="setup-chip ${setupTone}">${signalText(s.signal)} setup</span></div>
    <span class="signal-badge ${signalClass(s.signal)}">${signalText(s.signal)} / Trend Confirmed</span>
    <div class="score-progress">${progress("Trend", trend, 40)}${progress("Momentum", momentum, 30)}${progress("RSI", rsi, 20)}${progress("Volume", volume, 10)}</div>
    <ul class="signal-list">${reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul>`;
  return wrapped ? `<article class="panel-card setup-card setup-${setupTone}">${html}</article>` : `<div class="setup-card setup-${setupTone}">${html}</div>`;
}

function progress(label, value, total) {
  const pct = Math.max(0, Math.min(100, (toNum(value) ?? 0) / total * 100));
  const tone = pct >= 80 ? "good" : pct >= 55 ? "watch" : "weak";
  return `<div class="progress-row progress-${tone}"><span>${label}</span><span class="progress-track"><span class="progress-fill ${tone}" style="width:${pct}%"></span></span><strong>${fmt(value, 0)}/${total}</strong></div>`;
}

function growthBadge(value) {
  const n = toNum(value);
  const cls = n === null ? "badge-flat" : n < 0 ? "badge-down" : "badge-up";
  return `<b class="${cls}">${esc(value || "—")}</b>`;
}

function metric(title, value, prev, qoq, yoy) {
  return `<div class="metric-card"><h3>${esc(title)}</h3><strong class="metric-value">${value || "—"}</strong><div class="mini-stats"><span>Prev Q <b>${prev || "—"}</b></span><span>Estimate <b>—</b></span><span>QoQ ${growthBadge(qoq)}</span><span>YoY ${growthBadge(yoy)}</span></div></div>`;
}

function formatAiReason(item) {
  const raw = String(item || "").trim();
  if (!raw) return "";
  const patterns = [" — ที่มา:", " – ที่มา:", " - ที่มา:", " — Source:", " – Source:", " - Source:"];
  let cut = -1;
  let token = "";
  for (const p of patterns) {
    const idx = raw.indexOf(p);
    if (idx >= 0 && (cut < 0 || idx < cut)) { cut = idx; token = p; }
  }
  if (cut < 0) return `<span class="ai-main-text">${signedTextHtml(raw)}</span>`;
  const main = raw.slice(0, cut).trim();
  const source = raw.slice(cut + token.length).trim();
  return `<span class="ai-main-text">${signedTextHtml(main)}</span><details class="source-detail"><summary>ที่มา</summary><small>${esc(source || "SEC EDGAR companyfacts")}</small></details>`;
}

function aiViewHtml(s) {
  const reasons = Array.isArray(s.fundamentalReasons) ? s.fundamentalReasons : [];
  const highlights = Array.isArray(s.fundamentalHighlights) ? s.fundamentalHighlights : [];
  const fallback = [
    `Revenue YoY: ${pctLabel(s.revenueYoY)} — ${s.revenueYoY === null ? "SEC companyfacts ยังไม่มีค่าปัจจุบันหรือค่าเทียบช่วงก่อนหน้าที่ match ได้" : "คำนวณจาก SEC companyfacts"}`,
    `Revenue QoQ: ${pctLabel(s.revenueQoQ)} — ${s.revenueQoQ === null ? "SEC companyfacts ยังไม่มีค่าปัจจุบันหรือค่าเทียบช่วงก่อนหน้าที่ match ได้" : "คำนวณจาก SEC companyfacts"}`,
    `EPS YoY: ${pctLabel(s.epsYoy)}${s.epsYearAgo ? ` จาก ${fmt(s.epsYearAgo, 3)} เป็น ${fmt(s.eps, 3)}` : ""}`,
    `Net income QoQ: ${pctLabel(s.profitQoQ)}`,
    `Free cash flow: ${fmtCompact(s.fcf)}`,
    `Debt/Equity: ${fmt(s.debtEq, 2)}x`,
  ];
  const items = (reasons.length ? reasons : highlights.length ? highlights : fallback).filter(Boolean).slice(0, 10);
  return `<div class="ai-view-card"><div class="ai-view-head"><strong>AI view</strong><span>${esc(s.fundamentalSource || "SEC EDGAR")}</span></div><ul>${items.map(x => `<li>${formatAiReason(x)}</li>`).join("")}</ul></div>`;
}

function fundamentalDashboardHtml(s, wrapped = true) {
  const analyst = state.analystPayloads[s.ticker];
  const earnings = `
    <div class="metric-grid">
      ${metric("Revenue", fmtCompact(s.revenue), fmtCompact(s.revenuePrevQuarter), pctLabel(s.revenueQoQ), pctLabel(s.revenueYoY))}
      ${metric("Net Income", fmtCompact(s.netIncome), fmtCompact(s.netIncomePrevQuarter), pctLabel(s.profitQoQ), pctLabel(s.profitYoY))}
      ${metric("EPS (Diluted)", fmt(s.eps, 3), fmt(s.epsPrevQuarter, 3), pctLabel(s.epsQoQ), pctLabel(s.epsYoy))}
      ${metric("Free Cash Flow", fmtCompact(s.fcf), "—", "—", "—")}
    </div>
    <div class="standout-card"><strong>What stood out</strong><ul><li>Latest quarter: ${esc(s.latestQuarter || "—")}</li><li>Period end: ${esc(s.periodEnd || "—")}</li><li>Revenue YoY: ${signedValueHtml(s.revenueYoY)}</li><li>EPS YoY: ${signedValueHtml(s.epsYoy)}</li><li>Net income QoQ: ${signedValueHtml(s.profitQoQ)}</li><li>Free cash flow: ${signedTextHtml(fmtCompact(s.fcf))}</li></ul></div>
    ${aiViewHtml(s)}`;
  const guidance = `
    <div class="standout-card"><strong>🟢 Guidance View</strong><ul><li>Prior Guide Period: ${esc(s.guidance.priorPeriod || "—")}</li><li>Prior Rev Guide Mid: ${fmtCompact(s.guidance.priorRevenue)}</li><li>Confidence: ${esc(s.guidance.priorConfidence || "—")}</li><li>Actual vs Prior Guide: ${signedValueHtml(s.guidance.actualVsPrior)}</li><li>Next Guide Period: ${esc(s.guidance.nextPeriod || "—")}</li><li>Next Rev Guide Mid: ${fmtCompact(s.guidance.nextRevenue)}</li></ul></div>
    ${aiViewHtml(s)}`;
  const analystHtml = analystLinksHtml(s);
  const content = state.fundSubTab === "guidance" ? guidance : state.fundSubTab === "analyst" ? analystHtml : earnings;
  const html = `
    <h2>FUNDAMENTAL DASHBOARD</h2>
    <p class="note">${esc(s.ticker)} dashboard · ${esc(s.fundamentalSignal || "Fundamental")}${s.fundamentalScore !== null ? ` · Score ${fmt(s.fundamentalScore, 0)}/100` : ""} · Source: SEC EDGAR companyfacts + submissions</p>
    <div class="fund-tabs"><button class="${state.fundSubTab === "earnings" ? "active" : ""}" data-fund-tab="earnings">Earnings Snapshot</button><button class="${state.fundSubTab === "guidance" ? "active" : ""}" data-fund-tab="guidance">Company Guidance View</button><button class="${state.fundSubTab === "analyst" ? "active" : ""}" data-fund-tab="analyst">Analyst Consensus</button></div>
    ${content}`;
  return wrapped ? `<article class="panel-card fundamental-dashboard">${html}</article>` : html;
}

function analystLinksHtml(s) {
  const analysisUrl = yahooAnalysisUrl(s.ticker);
  const quoteUrl = yahooQuoteUrl(s.ticker);
  return `<div class="standout-card yahoo-analysis-card"><strong>Yahoo Finance Analysis</strong><p class="note">ไม่ใช้ Alpha Vantage API แล้ว — กดปุ่มเพื่อเปิดหน้า Analyst Estimates / Earnings Estimates ของ Yahoo Finance โดยตรง</p>
    <ul><li>Current Price: ${fmtMoney(s.price)}</li><li>Ticker: ${esc(s.ticker)}</li><li>Source: Yahoo Finance Analysis</li></ul>
    <div class="link-row"><a class="external-link" href="${analysisUrl}" target="_blank" rel="noopener noreferrer">Open Yahoo Analysis ↗</a><a class="external-link secondary" href="${quoteUrl}" target="_blank" rel="noopener noreferrer">Open Yahoo Quote ↗</a></div>
  </div>`;
}

function analystConsensusLoadedHtml(s, payload = {}) {
  return analystLinksHtml(s);
}

function playbookHtml(wrapped = true) {
  const html = `
    <h2>PLAYBOOK</h2>
    <div class="play-card buy"><h3>🟢 BUY ZONE</h3><p>Price &gt; EMA200, EMA20 &gt; EMA89, EMA5 &gt; EMA20, RSI 45–65, Volume ปกติขึ้นไป</p></div>
    <div class="play-card watch"><h3>🟡 WATCH</h3><p>Trend ดี แต่ RSI ร้อน หรือ momentum ยังไม่ confirm → รอจังหวะ อย่ารีบ</p></div>
    <div class="play-card avoid"><h3>🔴 AVOID</h3><p>ต่ำกว่า EMA200 และ score ต่ำ → สนามของ turnaround ไม่ใช่ compounding</p></div>`;
  return wrapped ? `<article class="panel-card playbook-card">${html}</article>` : html;
}

function setLoading(on, text = "") {
  state.loading = on;
  const subtitle = $("#scannerSubtitle");
  if (subtitle) subtitle.textContent = text || (on ? "Scanning with original Python engine…" : "Default sort: Score ↓ · click EMA headers to find nearest line");
  ["#scanNowDesktop", "#mobileScanNow"].forEach(sel => { const b = $(sel); if (b) { b.disabled = on; b.textContent = on ? "Scanning…" : "◎ Scan Now"; } });
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, { cache: "no-store", ...options });
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 160)}`);
  if (text.trim().startsWith("<")) throw new Error("Backend returned HTML instead of JSON. Run python app.py and open localhost:8787.");
  return JSON.parse(text);
}

async function fetchStaticLayer(layer) {
  const base = STATIC_DATA_URLS[layer];
  if (!base) throw new Error(`Unknown static layer: ${layer}`);
  const url = `${base}?v=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  const text = await res.text();
  if (!res.ok) throw new Error(`Static ${layer} HTTP ${res.status}: ${text.slice(0, 120)}`);
  if (text.trim().startsWith("<")) throw new Error(`Static ${layer} returned HTML. Check GitHub Pages data files under site/data/.`);
  return JSON.parse(text);
}

function mergeStaticPayloads(technical = {}, fundamental = {}) {
  const techRows = Array.isArray(technical.rows) ? technical.rows : [];
  const fundRows = Array.isArray(fundamental.rows) ? fundamental.rows : [];
  const fundBySymbol = new Map();
  fundRows.forEach(row => {
    const sym = normalizeTicker(row.symbol || row.ticker);
    if (sym) fundBySymbol.set(sym, row);
  });

  const rows = [];
  const seen = new Set();
  techRows.forEach(row => {
    const sym = normalizeTicker(row.symbol || row.ticker);
    if (!sym) return;
    const fund = fundBySymbol.get(sym) || {};
    rows.push({
      ...fund,
      ...row,
      fundamentalScore: fund.fundamentalScore ?? row.fundamentalScore,
      fundamentalSignal: fund.fundamentalSignal ?? row.fundamentalSignal,
      fundamentalReasons: fund.fundamentalReasons ?? row.fundamentalReasons,
      fundamentalHighlights: fund.fundamentalHighlights ?? row.fundamentalHighlights,
      fundamentalSource: fund.fundamentalSource ?? row.fundamentalSource,
      latestQuarter: fund.latestQuarter ?? row.latestQuarter,
      earningsDate: fund.earningsDate ?? row.earningsDate,
      revenue: fund.revenue ?? row.revenue,
      revenuePrevQuarter: fund.revenuePrevQuarter ?? row.revenuePrevQuarter,
      revenueQoQ: fund.revenueQoQ ?? row.revenueQoQ,
      revenueYoY: fund.revenueYoY ?? row.revenueYoY,
      netIncome: fund.netIncome ?? row.netIncome,
      netIncomePrevQuarter: fund.netIncomePrevQuarter ?? row.netIncomePrevQuarter,
      profitQoQ: fund.profitQoQ ?? row.profitQoQ,
      profitYoY: fund.profitYoY ?? row.profitYoY,
      eps: fund.eps ?? row.eps,
      epsPrevQuarter: fund.epsPrevQuarter ?? row.epsPrevQuarter,
      epsQoQ: fund.epsQoQ ?? row.epsQoQ,
      epsYoY: fund.epsYoY ?? row.epsYoY,
      freeCashFlow: fund.freeCashFlow ?? row.freeCashFlow,
      grossMargin: fund.grossMargin ?? row.grossMargin,
      operatingMargin: fund.operatingMargin ?? row.operatingMargin,
      netMargin: fund.netMargin ?? row.netMargin,
      debtToEquity: fund.debtToEquity ?? row.debtToEquity,
      roe: fund.roe ?? row.roe,
      priorCompanyGuidanceRevenuePeriod: fund.priorCompanyGuidanceRevenuePeriod ?? row.priorCompanyGuidanceRevenuePeriod,
      priorCompanyGuidanceRevenue: fund.priorCompanyGuidanceRevenue ?? row.priorCompanyGuidanceRevenue,
      actualVsPriorGuidanceRevenuePct: fund.actualVsPriorGuidanceRevenuePct ?? row.actualVsPriorGuidanceRevenuePct,
      nextCompanyGuidanceRevenuePeriod: fund.nextCompanyGuidanceRevenuePeriod ?? row.nextCompanyGuidanceRevenuePeriod,
      nextCompanyGuidanceRevenue: fund.nextCompanyGuidanceRevenue ?? row.nextCompanyGuidanceRevenue,
    });
    seen.add(sym);
  });
  fundRows.forEach(row => {
    const sym = normalizeTicker(row.symbol || row.ticker);
    if (sym && !seen.has(sym)) rows.push(row);
  });

  state.rows = rows;
  state.quotes = technical.quotes || {};
  const fundamentals = fundamental.fundamentals || {};
  Object.entries(fundamentals).forEach(([symRaw, detail]) => {
    const sym = normalizeTicker(symRaw);
    const existing = state.quotes[sym] || {};
    state.quotes[sym] = {
      ...existing,
      latest: { ...(existing.latest || {}), ...(detail.latest || detail.fundamental || {}) },
      fundamental: { ...(existing.fundamental || {}), ...(detail.fundamental || detail.latest || {}) },
    };
  });

  const generatedAt = technical.generatedAtTechnical || technical.generatedAt || fundamental.generatedAtFundamental || fundamental.generatedAt || null;
  state.lastScanAt = generatedAt ? String(generatedAt).replace(" UTC", "") : new Date().toLocaleString();
  state.lastScanSymbols = normalizeTickers(technical.watchlist || fundamental.watchlist || rows.map(r => r.symbol || r.ticker));
  if ((!state.watchlist || !state.watchlist.length || state.watchlist.every(t => BASE_WATCHLIST.includes(t))) && state.lastScanSymbols.length) {
    state.watchlist = [...state.lastScanSymbols];
  }
  const errs = [];
  if (Array.isArray(technical.errors)) errs.push(...technical.errors);
  if (Array.isArray(fundamental.errors)) errs.push(...fundamental.errors);
  state.errors = errs;
}

async function loadStaticData(options = {}) {
  state.staticMode = true;
  state.staticLoadError = null;
  setLoading(true, options.message || "Loading GitHub Pages static data…");
  try {
    const technical = await fetchStaticLayer("technical");
    let fundamental = state.staticPayloads.fundamental || {};
    try {
      fundamental = await fetchStaticLayer("fundamental");
    } catch (fundErr) {
      console.warn("Fundamental static layer not available yet", fundErr);
      fundamental = { rows: [], fundamentals: {}, errors: [{ symbol: "FUNDAMENTAL", error: "fundamental.json not generated yet" }] };
    }
    state.staticPayloads = { technical, fundamental };
    mergeStaticPayloads(technical, fundamental);
    state.staticLoaded = true;
    state.staticLoadError = null;
    if (!state.selected || !state.rows.some(r => normalizeTicker(r.symbol || r.ticker) === state.selected)) {
      state.selected = normalizeTicker(state.rows[0]?.symbol || state.watchlist[0] || "NVDA");
    }
    setLoading(false, `Loaded static data · Technical ${technical.generatedAtTechnical || technical.generatedAt || "—"} · Fundamental ${fundamental.generatedAtFundamental || fundamental.generatedAt || "—"}`);
    renderAll();
  } catch (err) {
    console.error(err);
    state.staticLoadError = err.message || String(err);
    state.rows = [];
    state.errors = [{ symbol: "STATIC", error: state.staticLoadError }];
    setLoading(false, `Static data load failed: ${state.staticLoadError}`);
    renderAll();
  }
}
async function scan(force = false, options = {}) {
  if (state.staticMode || isStaticDeployHost()) {
    await loadStaticData({ message: options.message || "Reloading GitHub Pages static data…" });
    return;
  }
  const scanSymbols = normalizeTickers(options.symbols || state.watchlist);
  if (!scanSymbols.length) {
    openSheet("bulkAddSheet");
    const summary = $("#bulkImportSummary");
    if (summary) summary.textContent = "วาง ticker ที่ต้องการสแกนก่อน";
    return;
  }
  syncFiltersFromUi();
  state.lastScanSymbols = scanSymbols;
  setLoading(true, options.message || `Scanning ${scanSymbols.length} tickers · ${state.filters.range}`);
  try {
    const params = new URLSearchParams({
      symbols: scanSymbols.join(","),
      range: state.filters.range,
      interval: "1d",
      includeFundamentals: (options.includeFundamentals ?? (state.scannerTab === "fundamental")) ? "1" : "0",
      v: String(Date.now())
    });
    const data = await fetchJson(`/api/scan?${params}`);
    state.rows = Array.isArray(data.rows) ? data.rows : [];
    state.quotes = data.quotes || {};
    state.errors = data.errors || [];
    if (!state.rows.length && state.errors.length) {
      state.rows = [];
    }
    state.lastScanAt = new Date().toLocaleString();
    if (!state.selected || !state.rows.some(r => normalizeTicker(r.symbol) === state.selected)) {
      state.selected = normalizeTicker(state.rows[0]?.symbol || state.watchlist[0]);
    }
    renderAll();
    updateResultCount();
    showAlertToastIfNeeded(force);
    if (state.errors.length) console.warn("Scan errors", state.errors);
    setLoading(false, `Showing ${currentStocks().length} pass filters / ${state.rows.length} loaded · ${data.generatedAt || "latest"}`);
    renderStatus();
  } catch (err) {
    console.error(err);
    state.rows = [];
    state.errors = [{ symbol: "API", error: err.message || String(err) }];
    setLoading(false, `Scan failed: ${err.message || err}`);
    renderAll();
  }
}

async function loadSymbolFromBackend(symbol, options = {}) {
  const ticker = normalizeTicker(symbol);
  if (!ticker) return;
  if (state.staticMode || isStaticDeployHost()) {
    if (!state.watchlist.includes(ticker)) {
      state.watchlist.unshift(ticker);
      saveWatchlist();
    }
    state.selected = ticker;
    if (!state.rows.some(r => normalizeTicker(r.symbol || r.ticker) === ticker)) {
      state.errors = [...(state.errors || []), { symbol: ticker, error: "Static deploy has no generated data for this ticker. Add it to watchlist.txt and rerun GitHub Actions." }];
    }
    renderAll();
    return;
  }
  syncFiltersFromUi();
  if (!options.silent) setLoading(true, `Loading ${ticker}…`);
  try {
    const params = new URLSearchParams({ symbol: ticker, range: state.filters.range, interval: "1d", includeFundamentals: "1", v: String(Date.now()) });
    const data = await fetchJson(`/api/quote?${params}`);
    const latest = data.latest || {};
    state.quotes[ticker] = data;
    const idx = state.rows.findIndex(r => normalizeTicker(r.symbol) === ticker);
    if (idx >= 0) state.rows[idx] = latest;
    else state.rows.push(latest);
    if (!state.watchlist.includes(ticker)) {
      state.watchlist.unshift(ticker);
      saveWatchlist();
    }
    state.selected = ticker;
    renderAll();
    updateResultCount();
    if (!options.silent) setLoading(false, `Loaded ${ticker}`);
  } catch (err) {
    console.error(err);
    if (!options.silent) setLoading(false, `Load failed for ${ticker}: ${err.message || err}`);
    else { state.errors = [...(state.errors || []), { symbol: ticker, error: err.message || String(err) }]; renderAll(); }
  }
}

function hasFundamentalData(s) {
  return [s.pe, s.ps, s.revYoy, s.epsYoy, s.margin, s.debtEq, s.roe, s.revenue, s.netIncome, s.eps].some(v => toNum(v) !== null);
}

async function ensureFundamentalData() {
  if (state.staticMode || isStaticDeployHost()) {
    if (!state.staticLoaded) await loadStaticData({ message: "Loading static fundamental layer…" });
    return;
  }
  if (state.fundamentalLoading || state.loading) return;
  const loaded = allWatchlistStocks().filter(s => !s.isPlaceholder);
  const needs = !loaded.length || loaded.some(s => !hasFundamentalData(s));
  if (!needs) return;
  state.fundamentalLoading = true;
  renderAll();
  try { await scan(true, { includeFundamentals: true, message: "Loading fundamentals from backend…" }); }
  finally { state.fundamentalLoading = false; renderAll(); }
}

async function ensureSymbolDetail(symbol, needFundamental = false) {
  const ticker = normalizeTicker(symbol);
  if (!ticker || state.symbolLoads.has(ticker)) return;
  const q = state.quotes[ticker];
  const s = (allWatchlistStocks().find(x => x.ticker === ticker) || placeholderStock(ticker));
  const hasSeries = Array.isArray(q?.series) && q.series.length;
  if (hasSeries && (!needFundamental || hasFundamentalData(s))) return;
  state.symbolLoads.add(ticker);
  try { await loadSymbolFromBackend(ticker, { silent: true }); }
  finally { state.symbolLoads.delete(ticker); }
}

function getActiveAlphaKeyInput() {
  const active = document.activeElement;
  if (active && active.matches && active.matches("[data-alpha-key-input]")) return active;
  const inputs = Array.from(document.querySelectorAll("[data-alpha-key-input]"));
  return inputs.find(el => el.offsetParent !== null) || inputs[0] || null;
}

function setAlphaKeyStatus(message = "", tone = "neutral") {
  $$('[data-alpha-key-status]').forEach(el => {
    el.textContent = message;
    el.className = `alpha-key-status ${tone}`;
  });
}

function maskAlphaKey(key = "") {
  const v = String(key || "").trim();
  if (!v) return "";
  if (v.length <= 8) return "••••";
  return `${v.slice(0, 4)}…${v.slice(-4)}`;
}

async function saveAlphaVantageKey(showAlert = true) {
  const input = getActiveAlphaKeyInput();
  const key = (input?.value || localStorage.getItem(STORAGE.alphaKey) || "").trim();
  if (!key) {
    setAlphaKeyStatus("ใส่ Alpha Vantage API key ก่อน", "error");
    if (input) input.focus();
    return "";
  }
  localStorage.setItem(STORAGE.alphaKey, key);
  $$('[data-alpha-key-input]').forEach(el => { if (el !== input) el.value = key; });
  setAlphaKeyStatus(`Saved locally: ${maskAlphaKey(key)}`, "ok");
  try {
    await fetchJson(`/api/alpha-vantage/key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apiKey: key }),
    });
  } catch (err) {
    console.warn("Alpha Vantage key is saved in browser localStorage; server persistence is optional", err);
  }
  if (showAlert) setAlphaKeyStatus(`Saved locally: ${maskAlphaKey(key)}`, "ok");
  return key;
}

async function loadAnalystConsensus() {
  const s = getSelected();
  const activeInput = getActiveAlphaKeyInput();
  const typedKey = (activeInput?.value || "").trim();
  if (typedKey) localStorage.setItem(STORAGE.alphaKey, typedKey);
  state.fundSubTab = "analyst";
  state.analystPayloads[s.ticker] = { loading: true };
  renderDetail();
  const apiKey = typedKey || localStorage.getItem(STORAGE.alphaKey) || "";
  if (!apiKey) {
    state.analystPayloads[s.ticker] = { ok: false, error: "กรุณาใส่ Alpha Vantage API Key ก่อนโหลด Analyst Consensus" };
    renderDetail();
    setAlphaKeyStatus("กรุณาใส่ Alpha Vantage API Key ก่อนโหลด", "error");
    return;
  }
  setAlphaKeyStatus("Loading Analyst Consensus…", "loading");
  try {
    const payload = await fetchJson(`/api/analyst-consensus`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: s.ticker, currentPrice: s.price, apiKey }),
    });
    state.analystPayloads[s.ticker] = payload;
    setAlphaKeyStatus(payload && payload.ok === false ? (payload.error || "Load failed") : "Analyst Consensus loaded", payload && payload.ok === false ? "error" : "ok");
  } catch (err) {
    try {
      const params = new URLSearchParams({ symbol: s.ticker, currentPrice: String(s.price || ""), apiKey });
      state.analystPayloads[s.ticker] = await fetchJson(`/api/analyst-consensus?${params}`);
    } catch (err2) {
      state.analystPayloads[s.ticker] = { ok: false, error: err2.message || err.message || String(err2) };
      setAlphaKeyStatus(err2.message || err.message || String(err2), "error");
    }
  }
  renderDetail();
}

function tradingViewSymbol(ticker = state.selected) {
  const t = normalizeTicker(ticker);
  const s = getSelected();
  const exchange = String(s.exchange || "").toUpperCase();
  const prefix = exchange.includes("NY") ? "NYSE" : exchange.includes("NAS") || exchange.includes("NMS") ? "NASDAQ" : "";
  return prefix ? `${prefix}:${t.replace(/\.BK$/, "")}` : t.replace(/\.BK$/, "SET:$&");
}

function financeLinksHtml(s = getSelected()) {
  const ticker = encodeURIComponent(normalizeTicker(s.ticker));
  const tv = encodeURIComponent(tradingViewSymbol(s.ticker));
  return `<div class="chart-external-links"><a href="https://www.tradingview.com/chart/?symbol=${tv}" target="_blank" rel="noopener">TradingView ↗</a><a href="https://finance.yahoo.com/quote/${ticker}" target="_blank" rel="noopener">Yahoo Finance ↗</a></div>`;
}

function renderChartModal() {
  const modal = $("#chartModal");
  if (!modal) return;
  if (!state.chartModalOpen) {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    modal.innerHTML = "";
    return;
  }
  const s = getSelected();
  modal.hidden = false;
  modal.setAttribute("aria-hidden", "false");
  modal.innerHTML = `<div class="chart-modal-backdrop" data-close-chart-modal></div><div class="chart-modal-card" role="dialog" aria-modal="true" aria-label="${esc(s.ticker)} expanded chart"><header class="chart-modal-header"><div><strong>${esc(s.ticker)} Price / EMA</strong><span>${fmtMoney(s.price)} · RSI ${fmt(s.rsi, 1)}</span></div>${financeLinksHtml(s)}<button class="icon-btn" data-close-chart-modal aria-label="Close chart">×</button></header><div class="chart-modal-body">${priceChartPanel(s)}</div></div>`;
}

function openChartModal() {
  state.chartModalOpen = true;
  renderChartModal();
}

function closeChartModal() {
  state.chartModalOpen = false;
  renderChartModal();
}

function addSymbolsBulk(rawText = "", mode = "append") {
  const tickers = parseTickerList(rawText);
  if (!tickers.length) return { total: 0, added: [], existing: [] };
  const before = new Set(state.watchlist);
  if (mode === "replace") state.watchlist = [];
  tickers.forEach(t => {
    if (!state.watchlist.includes(t)) state.watchlist.push(t);
    if (!state.rows.some(r => normalizeTicker(r.symbol) === t)) state.rows.push({ symbol: t, signal: "NEUTRAL", score: 0 });
  });
  const added = tickers.filter(t => !before.has(t));
  const existing = tickers.filter(t => before.has(t));
  state.selected = tickers[0];
  saveWatchlist();
  renderAll();
  return { total: tickers.length, added, existing };
}

function importBulkSymbols() {
  const input = $("#bulkSymbolInput");
  const summary = $("#bulkImportSummary");
  const raw = input?.value || "";
  const mode = raw.trim().startsWith("=") ? "replace" : "append";
  const clean = mode === "replace" ? raw.trim().slice(1) : raw;
  const result = addSymbolsBulk(clean, mode);
  if (!summary) return;
  if (!result.total) {
    summary.textContent = "ยังไม่พบ ticker ที่อ่านได้ — ลองวาง เช่น NVDA TSLA AAPL หรือแยกบรรทัดละตัว";
    summary.classList.add("warn");
    return;
  }
  summary.classList.remove("warn");
  summary.textContent = `${mode === "replace" ? "แทนที่ list แล้ว" : "เพิ่มเข้า list แล้ว"}: เพิ่มใหม่ ${result.added.length} ตัว · มีอยู่แล้ว ${result.existing.length} ตัว · รวม ${state.watchlist.length} ตัว`;
  if (input) input.value = "";
  setTimeout(() => { closeSheets(); scan(); }, 350);
}

function updateResultCount() {
  const count = currentStocks().length;
  const total = state.lastScanSymbols.length || state.rows.length || state.watchlist.length;
  const pill = $("#filterResultPill");
  if (pill) pill.textContent = `✓ ${count}/${total} pass`;
  $$(".mini-badge").forEach(el => { el.textContent = String(count); });
}

function syncFiltersFromUi(source = "desktop") {
  const scoreEl = source === "sheet" ? $("#sheetScoreRange") : $("#scoreRange");
  const score = Number(scoreEl?.value ?? state.filters.score);
  state.filters.score = score;
  state.filters.above200 = Boolean((source === "sheet" ? $("#sheetFilterAbove200") : $("#filterAbove200"))?.checked ?? state.filters.above200);
  state.filters.emaStack = Boolean((source === "sheet" ? $("#sheetFilterEmaStack") : $("#filterEmaStack"))?.checked ?? state.filters.emaStack);
  state.filters.sweetRsi = Boolean((source === "sheet" ? $("#sheetFilterSweetRsi") : $("#filterSweetRsi"))?.checked ?? state.filters.sweetRsi);
  state.filters.volume20 = Boolean((source === "sheet" ? $("#sheetFilterVolume20") : $("#filterVolume20"))?.checked ?? state.filters.volume20);
  state.filters.macdSignal = Boolean((source === "sheet" ? $("#sheetFilterMacdSignal") : $("#filterMacdSignal"))?.checked ?? state.filters.macdSignal);
  applyFilterUi();
  saveSettings();
}

function resetFilters() {
  state.filters = { score: 60, range: "1y", above200: true, emaStack: true, sweetRsi: true, volume20: false, macdSignal: true };
  applyFilterUi();
  saveSettings();
  renderAll();
}

function applyFilterUi() {
  ["#scoreRange", "#sheetScoreRange"].forEach(sel => { const el = $(sel); if (el) el.value = String(state.filters.score); });
  ["#scoreOutput", "#sheetScoreOutput"].forEach(sel => { const el = $(sel); if (el) el.value = String(state.filters.score); });
  const map = [
    ["#filterAbove200", "#sheetFilterAbove200", state.filters.above200],
    ["#filterEmaStack", "#sheetFilterEmaStack", state.filters.emaStack],
    ["#filterSweetRsi", "#sheetFilterSweetRsi", state.filters.sweetRsi],
    ["#filterVolume20", "#sheetFilterVolume20", state.filters.volume20],
    ["#filterMacdSignal", "#sheetFilterMacdSignal", state.filters.macdSignal],
  ];
  map.forEach(([a, b, val]) => { [a, b].forEach(sel => { const el = $(sel); if (el) el.checked = Boolean(val); }); });
  ["#rangeButtons", "#sheetRangeButtons"].forEach(sel => {
    const root = $(sel); if (!root) return;
    $$('button[data-range]', root).forEach(btn => btn.classList.toggle("active", btn.dataset.range === state.filters.range));
  });
}

function saveSettings() {
  localStorage.setItem(STORAGE.settings, JSON.stringify({ filters: state.filters, scannerTab: state.scannerTab, mobileView: state.mobileView, sortKey: state.sortKey, sortAsc: state.sortAsc, columns: state.columns, activeScreener: state.activeScreener, detailTab: state.detailTab, fundSubTab: state.fundSubTab, priceChartMode: state.priceChartMode, alertFilter: state.alertFilter, alertCollapsed: state.alertCollapsed }));
}

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE.settings) || "{}");
    if (saved.filters) state.filters = { ...state.filters, ...saved.filters };
    if (saved.priceChartMode) state.priceChartMode = saved.priceChartMode;
    if (saved.scannerTab) state.scannerTab = saved.scannerTab;
    if (saved.mobileView) state.mobileView = saved.mobileView;
    if (saved.sortKey) state.sortKey = saved.sortKey;
    if (typeof saved.sortAsc === "boolean") state.sortAsc = saved.sortAsc;
    if (saved.columns) state.columns = { ...state.columns, ...saved.columns };
    if (saved.activeScreener) state.activeScreener = saved.activeScreener;
    if (saved.detailTab) state.detailTab = saved.detailTab;
    if (saved.fundSubTab) state.fundSubTab = saved.fundSubTab;
    if (saved.alertFilter) state.alertFilter = saved.alertFilter;
    if (typeof saved.alertCollapsed === "boolean") state.alertCollapsed = saved.alertCollapsed;
  } catch (_) {}
}

function getScreeners() {
  try { return JSON.parse(localStorage.getItem(STORAGE.screeners) || "{}"); } catch (_) { return {}; }
}
function setScreeners(x) { localStorage.setItem(STORAGE.screeners, JSON.stringify(x)); }
function persistActiveScreener() {
  const screeners = getScreeners();
  screeners[state.activeScreener] = { watchlist: state.watchlist, filters: state.filters, columns: state.columns, scannerTab: state.scannerTab, mobileView: state.mobileView, sortKey: state.sortKey, sortAsc: state.sortAsc };
  setScreeners(screeners);
}
function loadScreener(key) {
  const defaults = {
    default: BASE_WATCHLIST,
    momentum: ["NVDA", "AMD", "AVGO", "TSLA", "PLTR", "APP", "CRWD", "DDOG", "HOOD", "COIN"],
    thai: ["PTT.BK", "CPALL.BK", "AOT.BK", "ADVANC.BK", "KBANK.BK", "BDMS.BK", "DELTA.BK", "GULF.BK", "TRUE.BK", "PTTEP.BK"],
    dividend: ["JEPQ", "QQQI", "KO", "PEP", "CVX", "ABBV", "WMT", "COST", "BAC", "AXP"],
    quality: ["MSFT", "COST", "ASML", "LIN", "ISRG", "BKNG", "ADP", "ORLY", "INTU", "VRSK"],
  };
  const saved = getScreeners()[key];
  state.activeScreener = key;
  state.watchlist = normalizeTickers(saved?.watchlist || defaults[key] || state.watchlist);
  if (saved?.filters) state.filters = { ...state.filters, ...saved.filters };
  if (saved?.columns) state.columns = { ...state.columns, ...saved.columns };
  if (saved?.scannerTab) state.scannerTab = saved.scannerTab;
  if (saved?.mobileView) state.mobileView = saved.mobileView;
  if (saved?.sortKey) state.sortKey = saved.sortKey;
  if (typeof saved?.sortAsc === "boolean") state.sortAsc = saved.sortAsc;
  state.selected = state.watchlist[0] || "NVDA";
  saveWatchlist();
  applyFilterUi();
  renderAll();
  scan();
}

function newScreener() {
  const name = prompt("ตั้งชื่อ screener ใหม่", "My Screener");
  if (!name) return;
  const key = name.toLowerCase().replace(/[^a-z0-9ก-๙]+/gi, "-").replace(/^-|-$/g, "") || `screener-${Date.now()}`;
  state.activeScreener = key;
  persistActiveScreener();
  renderPortfolioTabs(name, key);
}

function renderPortfolioTabs(newName = null, newKey = null) {
  const nav = $(".portfolio-tabs");
  if (!nav) return;
  const builtIns = [
    ["default", "⭐ Default"], ["momentum", "🚀 Momentum"], ["thai", "🇹🇭 Thai"], ["dividend", "🏦 Dividend"], ["quality", "🧱 High Quality"],
  ];
  const saved = getScreeners();
  const custom = Object.keys(saved).filter(k => !builtIns.some(([key]) => key === k)).slice(0, 4).map(k => [k, `⭐ ${k}`]);
  const tabs = [...builtIns.slice(0, 5), ...custom];
  nav.innerHTML = tabs.map(([key, label]) => `<button class="portfolio-tab ${key === state.activeScreener ? "active" : ""}" data-screener="${esc(key)}" title="Double click to rename / long press to delete">${esc(label)}</button>`).join("") + `
    <button class="portfolio-tab more-tab" data-export-screeners>⇅</button>
    <button class="portfolio-tab add-tab" id="newScreenerBtn">+ New</button>`;
}



function setColumnPreset(name) {
  const presets = {
    compact: { ticker:true, score:true, signal:true, price:true, ema5:false, ema20:true, ema89:false, ema200:false, rsi:true, macdHist:false, vol20:false, high52:false,
      fundTicker:true, fundScore:true, fundQuarter:false, fundRevenue:true, fundNetIncome:false, fundEps:true, fundFcf:false, fundMargins:true, fundGuidance:false },
    ema: { ticker:true, score:true, signal:true, price:true, ema5:true, ema20:true, ema89:true, ema200:true, rsi:true, macdHist:false, vol20:false, high52:false,
      fundTicker:true, fundScore:true, fundQuarter:true, fundRevenue:true, fundNetIncome:true, fundEps:true, fundFcf:true, fundMargins:true, fundGuidance:false },
    all: { ticker:true, score:true, signal:true, price:true, ema5:true, ema20:true, ema89:true, ema200:true, rsi:true, macdHist:true, vol20:true, high52:true,
      fundTicker:true, fundScore:true, fundQuarter:true, fundRevenue:true, fundNetIncome:true, fundEps:true, fundFcf:true, fundMargins:true, fundGuidance:true },
  };
  state.columns = { ...state.columns, ...(presets[name] || presets.ema) };
  renderColumnManager();
  saveSettings();
  renderAll();
}

function renderColumnManager() {
  const technicalLabels = {
    ticker:"Ticker", score:"Score", signal:"Signal", price:"Last Price", ema5:"EMA5 / %vs", ema20:"EMA20 / %vs", ema89:"EMA89 / %vs", ema200:"EMA200 / %vs", rsi:"RSI", macdHist:"MACD Hist", vol20:"Vol/20D", high52:"52Wk High"
  };
  const fundamentalLabels = {
    fundTicker:"Ticker", fundScore:"Fund Score / Signal", fundQuarter:"Latest Quarter / Period", fundRevenue:"Revenue / QoQ / YoY", fundNetIncome:"Net Income / QoQ / YoY", fundEps:"EPS / QoQ / YoY", fundFcf:"Free Cash Flow", fundMargins:"Margin / Debt / ROE", fundGuidance:"Guidance"
  };
  const section = (title, labels) => `<div class="column-section"><h3>${title}</h3>${Object.entries(labels).map(([key,label]) => `<label><span>☰ ${label}</span><input type="checkbox" data-column-key="${key}" ${state.columns[key] !== false ? "checked" : ""}></label>`).join("")}</div>`;
  const grid = $("#columnsGrid");
  if (grid) grid.innerHTML = section("Technical", technicalLabels) + section("Fundamental", fundamentalLabels);
}

function syncColumnsFromSheet() {
  $$('[data-column-key]').forEach(cb => { state.columns[cb.dataset.columnKey] = cb.checked; });
  if (!state.columns.ticker) state.columns.ticker = true;
  saveSettings();
  renderAll();
}

function clearWatchlist() {
  if (!confirm("Clear current watchlist?")) return;
  state.watchlist = [];
  state.rows = [];
  state.quotes = {};
  saveWatchlist();
  renderAll();
}

function renameActiveScreener() {
  const current = state.activeScreener;
  const name = prompt("Rename screener", current);
  if (!name) return;
  const newKey = name.toLowerCase().replace(/[^a-z0-9ก-๙]+/gi, "-").replace(/^-|-$/g, "") || `screener-${Date.now()}`;
  const screeners = getScreeners();
  screeners[newKey] = screeners[current] || { watchlist: state.watchlist, filters: state.filters, columns: state.columns, scannerTab: state.scannerTab, mobileView: state.mobileView };
  if (newKey !== current) delete screeners[current];
  setScreeners(screeners);
  state.activeScreener = newKey;
  saveSettings();
  renderPortfolioTabs();
}

function deleteActiveScreener() {
  if (["default", "momentum", "thai", "dividend", "quality"].includes(state.activeScreener)) {
    alert("Default screeners cannot be deleted. Create a custom screener first.");
    return;
  }
  if (!confirm(`Delete screener ${state.activeScreener}?`)) return;
  const screeners = getScreeners();
  delete screeners[state.activeScreener];
  setScreeners(screeners);
  state.activeScreener = "default";
  loadScreener("default");
}

function exportScreeners() {
  const payload = JSON.stringify(getScreeners(), null, 2);
  navigator.clipboard?.writeText(payload);
  alert("Screener JSON copied to clipboard.");
}

function importScreeners() {
  const raw = prompt("Paste screener JSON");
  if (!raw) return;
  try { setScreeners(JSON.parse(raw)); renderPortfolioTabs(); alert("Imported screeners."); }
  catch (err) { alert("Invalid JSON"); }
}


function persistDismissedAlerts() {
  localStorage.setItem(STORAGE.alertDismissed, JSON.stringify(Array.from(state.dismissedAlerts || [])));
}

function markAlertDismissed(id) {
  if (!id) return;
  const key = String(id);
  // Memo alerts represent saved user records. Do not auto-dismiss them just
  // because the alert was opened; they should remain until the memo itself is
  // deleted, marked Done, or ignored by the user.
  if (key.startsWith("memo-")) return;
  state.dismissedAlerts.add(key);
  persistDismissedAlerts();
}

function visibleAlertItems(items) {
  const dismissed = state.dismissedAlerts || new Set();
  return items.filter(a => String(a.id || "").startsWith("memo-") || !dismissed.has(String(a.id)));
}

function closeAlertSheet() {
  state.alertSheetOpen = false;
  const sheet = $("#alertMobileSheet");
  if (sheet) sheet.hidden = true;
}

function openAlertSheet() {
  state.alertSheetOpen = true;
  renderAlertCenter();
  const sheet = $("#alertMobileSheet");
  if (sheet) sheet.hidden = false;
}

function alertLevelRank(level) {
  return ({ action: 0, hot: 1, risk: 2, near: 3, memo: 4, info: 5 }[level] ?? 9);
}

function alertPctHtml(value, mode = "technical") {
  const n = toNum(value);
  if (n === null) return `<span class="alert-value neutral">—</span>`;
  const cls = mode === "fundamental" ? fundPctClass(n) : pctClass(n);
  return `<span class="alert-value ${cls}">${pctLabel(n)}</span>`;
}

function latestMemoAlerts() {
  let memos = [];
  try { memos = JSON.parse(localStorage.getItem("stockTimingRadar.memos.v55") || "[]"); } catch (_) { memos = []; }
  if (!Array.isArray(memos) || !memos.length) return [];
  return memos.map(m => {
    const ticker = normalizeTicker(m.ticker);
    const current = toNum(m.currentPrice);
    const target = toNum(m.targetPrice);
    const terminal = ["Done", "Ignored", "Deleted"].includes(String(m.status || ""));
    if (terminal) return null;
    const hit = current !== null && target !== null && (m.targetDirection === "lte" ? current <= target : current >= target);
    if (m.status === "Alert" || hit) {
      return {
        id: `memo-${m.id || ticker}`,
        type: "memo",
        level: "memo",
        ticker,
        title: "Memo alert triggered",
        message: `${m.actionPlan || "Action"} · Target ${fmtMoney(target)} · Current ${fmtMoney(current)}`,
        detail: m.reason || "Saved memo reached alert state",
        sortScore: 92,
        icon: "📝",
        persistent: true,
      };
    }
    return null;
  }).filter(Boolean);
}

function buildAlertItems() {
  const alerts = [];
  const stocks = allWatchlistStocks();
  stocks.forEach(s => {
    if (!s || !s.ticker) return;
    if (s.error) {
      alerts.push({ id:`err-${s.ticker}`, type:"risk", level:"risk", ticker:s.ticker, icon:"⚠️", title:"Data error", message:String(s.error), detail:"Scan returned an error for this ticker", sortScore:80 });
      return;
    }
    if (s.isPlaceholder) {
      alerts.push({ id:`pending-${s.ticker}`, type:"info", level:"info", ticker:s.ticker, icon:"⏳", title:"Waiting for scan data", message:"Ticker is in watchlist but not loaded yet", detail:"Press Scan Now to fetch technical data", sortScore:10 });
      return;
    }
    const score = toNum(s.score) ?? 0;
    const rsi = toNum(s.rsi);
    const ema20 = toNum(s.ema20Pct);
    const ema89 = toNum(s.ema89Pct);
    const ema200 = toNum(s.ema200Pct);
    const macd = toNum(s.macd);
    const sig = toNum(s.signal9);
    const vol = toNum(s.vol20);
    const near20 = ema20 !== null && Math.abs(ema20) <= 5;
    const near89 = ema89 !== null && Math.abs(ema89) <= 6;
    const hot = (rsi !== null && rsi >= 70) || (ema20 !== null && ema20 >= 15) || (ema89 !== null && ema89 >= 25) || (ema200 !== null && ema200 >= 45) || signalClass(s.signal) === "hot";
    const risk = (ema200 !== null && ema200 < 0) || (rsi !== null && rsi < 38) || (macd !== null && sig !== null && macd < sig && score < 65);
    const actionable = score >= 75 && near20 && !hot && !risk;
    if (actionable) {
      alerts.push({ id:`action-${s.ticker}`, type:"action", level:"action", ticker:s.ticker, icon:"🟢", title:"Buy-zone candidate", message:`Score ${fmt(score,0)} · EMA20 ${pctLabel(ema20)} · RSI ${fmt(rsi,1)}`, detail:"High score while price is still close to EMA20", sortScore:100 + score - Math.abs(ema20 || 0) });
    }
    if (near20 && !actionable) {
      alerts.push({ id:`near20-${s.ticker}`, type:"near", level:"near", ticker:s.ticker, icon:"📏", title:"Near EMA20", message:`EMA20 distance ${pctLabel(ema20)} · Price ${fmtMoney(s.price)}`, detail:"Potential entry is closer to the short/medium trend line", sortScore:75 - Math.abs(ema20 || 0) });
    }
    if (near89) {
      alerts.push({ id:`near89-${s.ticker}`, type:"near", level:"near", ticker:s.ticker, icon:"📐", title:"Near EMA89", message:`EMA89 distance ${pctLabel(ema89)} · Score ${fmt(score,0)}`, detail:"Watch for deeper pullback / base support area", sortScore:68 - Math.abs(ema89 || 0) });
    }
    if (hot) {
      const reason = rsi !== null && rsi >= 70 ? `RSI ${fmt(rsi,1)}` : `EMA stretch ${pctLabel(Math.max(ema20 || -999, ema89 || -999, ema200 || -999))}`;
      alerts.push({ id:`hot-${s.ticker}`, type:"hot", level:"hot", ticker:s.ticker, icon:"🔥", title:"HOT — อย่าไล่ราคา", message:`${reason} · wait for pullback`, detail:"Trend may still be strong, but entry risk/reward is stretched", sortScore:90 });
    }
    if (risk) {
      const parts = [];
      if (ema200 !== null && ema200 < 0) parts.push(`below EMA200 ${pctLabel(ema200)}`);
      if (rsi !== null && rsi < 38) parts.push(`RSI ${fmt(rsi,1)}`);
      if (macd !== null && sig !== null && macd < sig) parts.push("MACD < Signal");
      alerts.push({ id:`risk-${s.ticker}`, type:"risk", level:"risk", ticker:s.ticker, icon:"🔴", title:"Risk check", message:parts.join(" · ") || "Technical risk rising", detail:"Setup is weakening; review before adding", sortScore:85 });
    }
    if (vol !== null && vol >= 1.5 && score >= 65) {
      alerts.push({ id:`vol-${s.ticker}`, type:"action", level:"action", ticker:s.ticker, icon:"📡", title:"Volume expansion", message:`Vol/20D ${fmt(vol,2)}x · Score ${fmt(score,0)}`, detail:"Volume is above recent average; confirm price action", sortScore:78 + vol });
    }
  });
  alerts.push(...latestMemoAlerts());
  const seen = new Set();
  return alerts.filter(a => {
    const key = `${a.id}-${a.ticker}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).sort((a,b) => alertLevelRank(a.level) - alertLevelRank(b.level) || (b.sortScore || 0) - (a.sortScore || 0) || String(a.ticker).localeCompare(String(b.ticker)));
}

function filteredAlerts() {
  const all = visibleAlertItems(buildAlertItems());
  const f = state.alertFilter || "all";
  if (f === "all") return all;
  return all.filter(a => a.type === f || a.level === f);
}

function alertFilterLabel(f) {
  return ({ all:"All", action:"Actionable", near:"Near EMA", hot:"HOT", risk:"Risk", memo:"Memo" }[f] || "All");
}

function renderAlertCenter() {
  const panel = $("#alertCenter");
  if (!panel) return;
  const all = visibleAlertItems(buildAlertItems());
  const items = filteredAlerts();
  panel.classList.toggle("collapsed", state.alertCollapsed);
  $$("[data-alert-filter]", panel).forEach(btn => btn.classList.toggle("active", btn.dataset.alertFilter === (state.alertFilter || "all")));
  const counts = all.reduce((acc, a) => { acc[a.level] = (acc[a.level] || 0) + 1; acc.total += 1; return acc; }, { total:0 });
  const pill = $("#alertCountPill");
  if (pill) pill.textContent = `${counts.total} alerts`;
  const subtitle = $("#alertSubtitle");
  if (subtitle) subtitle.textContent = state.lastScanAt ? `Last checked ${state.lastScanAt} · ${alertFilterLabel(state.alertFilter)} view` : "Run Scan Now to generate technical alerts";
  const toggle = panel.querySelector("[data-toggle-alerts]");
  if (toggle) toggle.textContent = state.alertCollapsed ? "Show" : "Hide";
  const summary = $("#alertSummaryGrid");
  if (summary) {
    summary.innerHTML = [
      ["Actionable", counts.action || 0, "action", "🟢"],
      ["Near EMA", counts.near || 0, "near", "📏"],
      ["HOT", counts.hot || 0, "hot", "🔥"],
      ["Risk", counts.risk || 0, "risk", "🔴"],
      ["Memo", counts.memo || 0, "memo", "📝"],
    ].map(([label, count, cls, icon]) => `<button class="alert-stat ${cls}" data-alert-filter="${cls}"><span>${icon} ${label}</span><strong>${count}</strong></button>`).join("");
  }
  const list = $("#alertList");
  if (!list) return;
  if (!items.length) {
    list.innerHTML = `<div class="alert-empty">ไม่มี alert ในหมวดนี้ตอนนี้ · ลอง Scan Now หรือเปลี่ยน filter</div>`;
    renderMobileAlertControls(all, items);
    return;
  }
  list.innerHTML = items.slice(0, 12).map(a => `<button class="alert-item ${a.level}" data-alert-id="${esc(a.id)}" data-alert-ticker="${esc(a.ticker)}" title="Open ${esc(a.ticker)} detail">
    <span class="alert-icon">${a.icon}</span>
    <span class="alert-main"><strong>${esc(a.ticker)} · ${esc(a.title)}</strong><small>${esc(a.message)}</small><em>${esc(a.detail)}</em></span>
    <span class="alert-arrow">↗</span>
  </button>`).join("");

  renderMobileAlertControls(all, items);
}

function renderMobileAlertControls(all, items) {
  const fab = $("#alertFab");
  const badge = $("#alertFabBadge");
  const sheet = $("#alertMobileSheet");
  const mobileList = $("#alertMobileList");
  const mobileSub = $("#alertMobileSubtitle");
  const mobileFilters = $("#alertMobileFilters");
  if (!fab || !badge || !sheet || !mobileList) return;
  const unreadAll = (all || []).filter(a => !state.dismissedAlerts?.has(a.id));
  const unreadItems = (items || []).filter(a => !state.dismissedAlerts?.has(a.id));
  const count = unreadAll.length;
  fab.hidden = count === 0;
  badge.textContent = count > 99 ? "99+" : String(count);
  fab.classList.toggle("pulse", count > 0 && !state.alertSheetOpen);
  if (mobileSub) mobileSub.textContent = count ? `${count} unread · tap an alert to open and clear it` : "No unread alerts";
  if (mobileFilters) $$('[data-alert-filter]', mobileFilters).forEach(btn => btn.classList.toggle("active", btn.dataset.alertFilter === (state.alertFilter || "all")));
  if (!count) {
    mobileList.innerHTML = `<div class="alert-empty">ไม่มี unread alert ตอนนี้</div>`;
    sheet.hidden = !state.alertSheetOpen;
    return;
  }
  if (!unreadItems.length) {
    mobileList.innerHTML = `<div class="alert-empty">ไม่มี unread alert ในหมวดนี้ · ลองเลือก All</div>`;
  } else {
    mobileList.innerHTML = unreadItems.slice(0, 20).map(a => `<button class="alert-item ${a.level}" data-alert-id="${esc(a.id)}" data-alert-ticker="${esc(a.ticker)}" title="Open ${esc(a.ticker)} detail">
      <span class="alert-icon">${a.icon}</span>
      <span class="alert-main"><strong>${esc(a.ticker)} · ${esc(a.title)}</strong><small>${esc(a.message)}</small><em>${esc(a.detail)}</em></span>
      <span class="alert-arrow">↗</span>
    </button>`).join("");
  }
  sheet.hidden = !state.alertSheetOpen;
}

function alertSignature(alerts) {
  return alerts.filter(a => ["action","hot","risk","memo"].includes(a.level)).slice(0, 8).map(a => `${a.level}:${a.ticker}:${a.title}`).join("|");
}

function showAlertToastIfNeeded(force = false) {
  const alerts = visibleAlertItems(buildAlertItems()).filter(a => ["action","hot","risk","memo"].includes(a.level));
  renderAlertCenter();
  if (!alerts.length) return;
  const sig = alertSignature(alerts);
  if (!force && sig && sig === state.lastAlertSignature) return;
  state.lastAlertSignature = sig;
  localStorage.setItem(STORAGE.alertSeen, sig);
  const top = alerts[0];
  const toast = $("#alertToast");
  if (!toast) return;
  if (window.matchMedia("(max-width: 767px)").matches) {
    toast.hidden = true;
    const fab = $("#alertFab");
    if (fab) {
      fab.classList.remove("pulse");
      void fab.offsetWidth;
      fab.classList.add("pulse");
    }
    return;
  }
  toast.innerHTML = `<strong>🔔 ${alerts.length} technical alert${alerts.length > 1 ? "s" : ""}</strong><span>${esc(top.ticker)} · ${esc(top.title)} — ${esc(top.message)}</span><button data-open-alerts>Open</button>`;
  toast.hidden = false;
  clearTimeout(showAlertToastIfNeeded._timer);
  showAlertToastIfNeeded._timer = setTimeout(() => { toast.hidden = true; }, 6500);
}

function renderStatus() {
  const subtitle = $("#scannerSubtitle");
  if (!subtitle || state.loading) return;
  const err = state.errors?.length ? ` · ${state.errors.length} errors` : "";
  const when = state.lastScanAt ? ` · Last scan ${state.lastScanAt}` : "";
  subtitle.textContent = `Showing ${currentStocks().length} pass / ${state.lastScanSymbols.length || state.rows.length || state.watchlist.length} watchlist · table keeps filtered rows dimmed · sort ${state.sortKey}${state.sortAsc ? " ↑" : " ↓"}${when}${err}`;
  updateMobileSortLabel();
}

function renderAll() {
  const shell = $(".app-shell");
  if (shell) {
    shell.dataset.view = state.scannerTab;
    shell.dataset.mobileView = state.mobileView;
  }
  applyFilterUi();
  renderGroups();
  renderColumnManager();
  renderPortfolioTabs();
  renderTechnicalTable();
  renderTechnicalMobile();
  renderTechnicalMobileTable();
  renderFundamental();
  renderFundamentalMobileTable();
  renderDetail();
  updateTabs();
  updateResultCount();
  renderAlertCenter();
  renderStatus();
  updateMobileSortLabel();
}

function updateTabs() {
  $$('[data-tab]').forEach(btn => btn.classList.toggle("active", btn.dataset.tab === state.scannerTab));
  $("#technicalScanner")?.classList.toggle("active", state.scannerTab === "technical");
  $("#fundamentalScanner")?.classList.toggle("active", state.scannerTab === "fundamental");
  $$('[data-mobile-view]').forEach(btn => btn.classList.toggle("active", btn.dataset.mobileView === state.mobileView));
  $$(".portfolio-tab").forEach(btn => btn.classList.toggle("active", btn.dataset.screener === state.activeScreener));
}

function openSheet(id) {
  const sheet = $("#" + id);
  if (!sheet) {
    console.warn("Missing sheet", id);
    return;
  }
  $$(".bottom-sheet").forEach(s => {
    if (s !== sheet) {
      s.classList.remove("open");
      s.setAttribute("aria-hidden", "true");
    }
  });
  const backdrop = $("#sheetBackdrop");
  if (backdrop) backdrop.hidden = false;
  document.body.classList.add("sheet-open");
  sheet.classList.add("open");
  sheet.setAttribute("aria-hidden", "false");
  const first = sheet.querySelector("textarea, input, button:not([data-close-sheet])");
  if (id === "bulkAddSheet" || id === "quickScanSheet") setTimeout(() => first?.focus(), 90);
}
function closeSheets() {
  const backdrop = $("#sheetBackdrop");
  if (backdrop) backdrop.hidden = true;
  document.body.classList.remove("sheet-open");
  $$(".bottom-sheet").forEach(s => { s.classList.remove("open"); s.setAttribute("aria-hidden", "true"); });
}
function openQuickScanSheet() {
  const input = $("#quickScanInput");
  if (input) input.value = state.watchlist.join(" ");
  const summary = $("#quickScanSummary");
  if (summary) summary.textContent = `${state.watchlist.length} symbols in current watchlist`;
  openSheet("quickScanSheet");
}
function openMobileDetail() {
  const modal = $("#mobileDetailModal");
  if (modal) { modal.classList.add("open"); modal.setAttribute("aria-hidden", "false"); }
}


function setScannerTab(tabName) {
  const next = tabName === "fundamental" ? "fundamental" : "technical";
  if (state.scannerTab === next) {
    updateTabs();
    return;
  }
  state.scannerTab = next;
  state.sortKey = "score";
  state.sortAsc = false;
  saveSettings();
  renderAll();
  if (next === "fundamental") {
    ensureFundamentalData();
  }
}

function setDetailTab(tabName) {
  const allowed = new Set(["technical", "setup", "fundamental", "playbook"]);
  state.detailTab = allowed.has(tabName) ? tabName : "technical";
  saveSettings();
  renderDetail();
  ensureSymbolDetail(state.selected, state.detailTab === "fundamental");
}

function setFundSubTab(tabName) {
  const allowed = new Set(["earnings", "guidance", "analyst"]);
  state.fundSubTab = allowed.has(tabName) ? tabName : "earnings";
  saveSettings();
  renderDetail();
  if (state.fundSubTab === "analyst") {
    // Keep API on-demand: UI switches immediately; the user decides when to press Load.
    return;
  }
  ensureSymbolDetail(state.selected, true);
}

function bindHardWiredTabs() {
  // Capture phase fallback: guarantees UI tabs switch even if a parent panel is re-rendered
  // or a table overlay catches the normal delegated click. API/data loading remains lazy.
  ["pointerdown", "mousedown", "click"].forEach(type => {
    document.addEventListener(type, (e) => {
      const input = e.target.closest && e.target.closest("[data-alpha-key-input]");
      if (!input) return;
      // Desktop has nested clickable dashboard panels; keep API key typing isolated
      // from delegated tab/table handlers without blocking the browser's native focus.
      e.stopPropagation();
      if (type === "click") input.focus();
    }, true);
  });
  document.addEventListener("click", (e) => {
    const alertFilter = e.target.closest("[data-alert-filter]");
    if (alertFilter) {
      e.preventDefault();
      e.stopPropagation();
      state.alertFilter = alertFilter.dataset.alertFilter || "all";
      localStorage.setItem("stockTimingRadar.alertFilter.v61", state.alertFilter);
      saveSettings();
      renderAlertCenter();
      return;
    }
    const alertTicker = e.target.closest("[data-alert-ticker]");
    if (alertTicker) {
      e.preventDefault();
      e.stopPropagation();
      markAlertDismissed(alertTicker.dataset.alertId);
      state.selected = normalizeTicker(alertTicker.dataset.alertTicker);
      closeAlertSheet();
      renderAll();
      ensureSymbolDetail(state.selected, false);
      if (window.matchMedia("(max-width: 767px)").matches) openMobileDetail();
      return;
    }
    if (e.target.closest("[data-toggle-alerts]")) {
      e.preventDefault();
      e.stopPropagation();
      state.alertCollapsed = !state.alertCollapsed;
      localStorage.setItem("stockTimingRadar.alertCollapsed.v61", state.alertCollapsed ? "1" : "0");
      saveSettings();
      renderAlertCenter();
      return;
    }
    if (e.target.closest("[data-open-alerts]") || e.target.closest("#alertFab")) {
      e.preventDefault();
      e.stopPropagation();
      $("#alertToast")?.setAttribute("hidden", "");
      if (window.matchMedia("(max-width: 767px)").matches) {
        openAlertSheet();
      } else {
        state.alertCollapsed = false;
        localStorage.setItem("stockTimingRadar.alertCollapsed.v61", "0");
        renderAlertCenter();
        $("#alertCenter")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      return;
    }
    if (e.target.closest("[data-close-alert-sheet]")) {
      e.preventDefault();
      e.stopPropagation();
      closeAlertSheet();
      return;
    }
    if (e.target.closest("[data-dismiss-all-alerts]")) {
      e.preventDefault();
      e.stopPropagation();
      visibleAlertItems(buildAlertItems()).forEach(a => markAlertDismissed(a.id));
      closeAlertSheet();
      renderAll();
      return;
    }
    if (e.target.closest("[data-close-chart-modal]")) {
      e.preventDefault();
      e.stopPropagation();
      closeChartModal();
      return;
    }
    const chartOpen = e.target.closest("[data-open-chart-modal]");
    if (chartOpen && (!e.target.closest("[data-chart-controls]") || e.target.closest(".chart-expand-btn"))) {
      e.preventDefault();
      e.stopPropagation();
      openChartModal();
      return;
    }
    const chartMode = e.target.closest("[data-chart-mode]");
    if (chartMode) {
      e.preventDefault();
      e.stopPropagation();
      state.priceChartMode = chartMode.dataset.chartMode === "candles" ? "candles" : "line";
      localStorage.setItem(STORAGE.priceChartMode, state.priceChartMode);
      saveSettings();
      renderDetail();
      return;
    }
    const th = e.target.closest("th[data-sort]");
    if (th) {
      e.preventDefault();
      e.stopPropagation();
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortAsc = !state.sortAsc;
      else { state.sortKey = key; state.sortAsc = key.includes("Pct") || key.includes("Yoy") || key.includes("QoQ"); }
      saveSettings();
      renderAll();
      return;
    }
    const sortPick = e.target.closest("[data-sort-pick]");
    if (sortPick) {
      e.preventDefault();
      e.stopPropagation();
      state.sortKey = sortPick.dataset.sortPick;
      state.sortAsc = sortPick.dataset.sortDir !== "desc";
      saveSettings();
      closeSheets();
      renderAll();
      return;
    }
    const resetBtn = e.target.closest("#filtersSheet .sheet-actions .secondary-btn");
    if (resetBtn && resetBtn.textContent.trim().toLowerCase().includes("reset")) {
      e.preventDefault();
      e.stopPropagation();
      resetFilters();
      return;
    }
    const openPanel = e.target.closest("[data-open-panel]");
    if (openPanel) {
      e.preventDefault();
      e.stopPropagation();
      const target = openPanel.dataset.openPanel === "columns" ? "columnsSheet" : openPanel.dataset.openPanel === "filters" ? "filtersSheet" : openPanel.dataset.openPanel === "sort" ? "sortSheet" : "bulkAddSheet";
      openSheet(target);
      return;
    }
    const scannerTab = e.target.closest("[data-tab]");
    if (scannerTab) {
      e.preventDefault();
      e.stopPropagation();
      setScannerTab(scannerTab.dataset.tab);
      return;
    }
    const detailTab = e.target.closest("[data-detail-tab]");
    if (detailTab) {
      e.preventDefault();
      e.stopPropagation();
      setDetailTab(detailTab.dataset.detailTab);
      return;
    }
    const fundTab = e.target.closest("[data-fund-tab]");
    if (fundTab) {
      e.preventDefault();
      e.stopPropagation();
      setFundSubTab(fundTab.dataset.fundTab);
      return;
    }
  }, true);

  document.addEventListener("input", (e) => {
    const el = e.target;
    if (!el || !(el instanceof HTMLInputElement)) return;
    if (el.id === "scoreRange" || el.id === "sheetScoreRange") {
      state.filters.score = Number(el.value || 0);
      applyFilterUi();
      saveSettings();
      renderAll();
    }
  }, true);

  document.addEventListener("change", (e) => {
    const el = e.target;
    if (!el || !(el instanceof HTMLInputElement)) return;
    const ids = new Set(["filterAbove200","filterEmaStack","filterSweetRsi","filterVolume20","filterMacdSignal","sheetFilterAbove200","sheetFilterEmaStack","sheetFilterSweetRsi","sheetFilterVolume20","sheetFilterMacdSignal"]);
    if (ids.has(el.id)) {
      syncFiltersFromUi(el.id.startsWith("sheet") ? "sheet" : "desktop");
      saveSettings();
      renderAll();
    }
  }, true);
}

function bindEvents() {
  document.body.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest("[data-alpha-key-input]")) return;
    const select = e.target.closest("[data-select]");
    if (select) {
      state.selected = normalizeTicker(select.dataset.select);
      renderAll();
      ensureSymbolDetail(state.selected, state.detailTab === "fundamental");
      if (window.matchMedia("(max-width: 767px)").matches && select.closest(".stock-card")) openMobileDetail();
      return;
    }
    const add = e.target.closest("[data-add-symbol]");
    if (add) { openSheet("bulkAddSheet"); setTimeout(() => $("#bulkSymbolInput")?.focus(), 60); return; }
    const group = e.target.closest("[data-market-group]");
    if (group) { state.activeMarketGroup = group.dataset.marketGroup; renderAll(); return; }
    const portfolio = e.target.closest(".portfolio-tab");
    if (portfolio && !portfolio.classList.contains("add-tab") && !portfolio.classList.contains("more-tab")) { loadScreener(portfolio.dataset.screener || "default"); return; }
    if (e.target.closest(".add-tab")) { newScreener(); return; }
    const mobileView = e.target.closest("[data-mobile-view]");
    if (mobileView) { state.mobileView = mobileView.dataset.mobileView; saveSettings(); renderAll(); return; }
    const detailTab = e.target.closest("[data-detail-tab]");
    if (detailTab) { setDetailTab(detailTab.dataset.detailTab); return; }
    const tab = e.target.closest("[data-tab]");
    if (tab) { setScannerTab(tab.dataset.tab); return; }
    const fundTab = e.target.closest("[data-fund-tab]");
    if (fundTab) { setFundSubTab(fundTab.dataset.fundTab); return; }
    const open = e.target.closest("[data-open-panel]");
    if (open) { openSheet(open.dataset.openPanel === "columns" ? "columnsSheet" : open.dataset.openPanel === "filters" ? "filtersSheet" : open.dataset.openPanel === "sort" ? "sortSheet" : "bulkAddSheet"); return; }
    if (e.target.closest("[data-close-sheet]")) { closeSheets(); return; }
    if (e.target.closest("[data-import-symbols]")) { importBulkSymbols(); return; }
    if (e.target.closest("[data-replace-symbols]")) { const input = $("#bulkSymbolInput"); const result = addSymbolsBulk(input?.value || "", "replace"); const s = $("#bulkImportSummary"); if (s) s.textContent = `แทนที่ watchlist แล้ว: ${result.total} symbols`; if (input) input.value = ""; setTimeout(() => { closeSheets(); scan(true); }, 300); return; }
    if (e.target.closest("[data-clear-watchlist]")) { clearWatchlist(); closeSheets(); return; }
    if (e.target.closest("[data-column-preset]")) { setColumnPreset(e.target.closest("[data-column-preset]").dataset.columnPreset); return; }
    if (e.target.closest("#columnsSheet .sheet-actions .primary-btn")) { syncColumnsFromSheet(); closeSheets(); return; }
    if (e.target.closest("[data-rename-screener]")) { renameActiveScreener(); return; }
    if (e.target.closest("[data-delete-screener]")) { deleteActiveScreener(); return; }
    if (e.target.closest("[data-export-screeners]")) { exportScreeners(); return; }
    if (e.target.closest("[data-import-screeners]")) { importScreeners(); return; }
    if (e.target.closest("[data-clear-symbols]")) { const input = $("#bulkSymbolInput"); if (input) input.value = ""; const s = $("#bulkImportSummary"); if (s) s.textContent = ""; return; }
    const sortPick = e.target.closest("[data-sort-pick]");
    if (sortPick) { state.sortKey = sortPick.dataset.sortPick; state.sortAsc = sortPick.dataset.sortDir !== "desc"; saveSettings(); closeSheets(); renderAll(); return; }

    if (e.target.closest("#mobileScanNow")) { openQuickScanSheet(); return; }
    if (e.target.closest("#scanNowDesktop, #filtersSheet .sheet-actions .primary-btn")) { syncFiltersFromUi(e.target.closest("#filtersSheet") ? "sheet" : "desktop"); closeSheets(); scan(true); return; }
    if (e.target.closest("[data-scan-current]")) { closeSheets(); scan(true); return; }
    if (e.target.closest("[data-scan-temp]")) { const raw = $("#quickScanInput")?.value || ""; const symbols = parseTickerList(raw); if (!symbols.length) { const s=$("#quickScanSummary"); if (s) s.textContent="ใส่ ticker อย่างน้อย 1 ตัว"; return; } closeSheets(); scan(true, { symbols, message: `Scanning temporary list · ${symbols.length} symbols` }); return; }
    if (e.target.closest("[data-replace-scan]")) { const raw = $("#quickScanInput")?.value || ""; const result = addSymbolsBulk(raw, "replace"); if (!result.total) { const s=$("#quickScanSummary"); if (s) s.textContent="ใส่ ticker อย่างน้อย 1 ตัว"; return; } closeSheets(); scan(true); return; }
    if (e.target.closest("[data-append-scan]")) { const raw = $("#quickScanInput")?.value || ""; const result = addSymbolsBulk(raw, "append"); if (!result.total) { const s=$("#quickScanSummary"); if (s) s.textContent="ใส่ ticker อย่างน้อย 1 ตัว"; return; } closeSheets(); scan(true); return; }
    const rangeBtn = e.target.closest("button[data-range]");
    if (rangeBtn) { state.filters.range = rangeBtn.dataset.range; applyFilterUi(); saveSettings(); return; }
    const th = e.target.closest("th[data-sort]");
    if (th) { const key = th.dataset.sort; if (state.sortKey === key) state.sortAsc = !state.sortAsc; else { state.sortKey = key; state.sortAsc = key.includes("Pct"); } saveSettings(); renderAll(); return; }
    const loadSymbolBtn = e.target.closest("[data-load-symbol]");
    if (loadSymbolBtn) { const input = loadSymbolBtn.closest(".detail-header")?.querySelector("input"); loadSymbolFromBackend(input?.value || state.selected); return; }
    // Analyst tab now links to Yahoo Finance; no API key interaction required.
  });



  document.body.addEventListener("input", (e) => {
    if (e.target && e.target.matches("[data-alpha-key-input]")) {
      localStorage.setItem(STORAGE.alphaKey, e.target.value.trim());
    }
  }, true);

  document.body.addEventListener("keydown", (e) => {
    if (e.target && e.target.matches("[data-alpha-key-input]")) {
      e.stopPropagation();
      return;
    }
  }, true);

  document.body.addEventListener("dblclick", (e) => { if (e.target.closest(".portfolio-tab:not(.add-tab):not(.more-tab)")) renameActiveScreener(); });
  let longPressTimer = null;
  document.body.addEventListener("pointerdown", (e) => { const tab = e.target.closest(".portfolio-tab:not(.add-tab):not(.more-tab)"); if (tab) longPressTimer = setTimeout(deleteActiveScreener, 750); });
  document.body.addEventListener("pointerup", () => { if (longPressTimer) clearTimeout(longPressTimer); longPressTimer = null; });
  document.addEventListener("keydown", (event) => {
    if (event.target && ["INPUT", "TEXTAREA"].includes(event.target.tagName)) return;
    if (event.key === "Escape" && state.chartModalOpen) { event.preventDefault(); closeChartModal(); return; }
    if (event.key === "/") { event.preventDefault(); $("#symbolSearch")?.focus(); }
    if (event.key.toLowerCase() === "s") { event.preventDefault(); scan(true); }
  });
  $("#sheetBackdrop")?.addEventListener("click", closeSheets);
  $("#closeDetail")?.addEventListener("click", () => $("#mobileDetailModal")?.classList.remove("open"));

  ["#scoreRange", "#sheetScoreRange"].forEach(id => {
    const el = $(id); if (!el) return;
    el.addEventListener("input", () => {
      state.filters.score = Number(el.value);
      applyFilterUi();
      renderAll();
    });
  });

  ["#filterAbove200", "#filterEmaStack", "#filterSweetRsi", "#filterVolume20", "#filterMacdSignal", "#sheetFilterAbove200", "#sheetFilterEmaStack", "#sheetFilterSweetRsi", "#sheetFilterVolume20", "#sheetFilterMacdSignal"].forEach(sel => {
    const el = $(sel); if (!el) return;
    el.addEventListener("change", () => { syncFiltersFromUi(sel.startsWith("#sheet") ? "sheet" : "desktop"); renderAll(); });
  });

  document.body.addEventListener("change", (event) => {
    const cb = event.target.closest("[data-column-key]");
    if (!cb) return;
    state.columns[cb.dataset.columnKey] = cb.checked;
    if (!state.columns.ticker) state.columns.ticker = true;
    if (!state.columns.fundTicker) state.columns.fundTicker = true;
    saveSettings();
    renderTechnicalTable();
    renderFundamental();
    renderFundamentalMobileTable();
    renderStatus();
  });

  $("#bulkSymbolInput")?.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); importBulkSymbols(); }
  });
  $("#quickScanInput")?.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      const symbols = parseTickerList(event.currentTarget.value || "");
      if (symbols.length) { closeSheets(); scan(true, { symbols, message: `Scanning temporary list · ${symbols.length} symbols` }); }
    }
  });

  $("#symbolSearch")?.addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); loadSymbolFromBackend(event.currentTarget.value); event.currentTarget.value = ""; }
  });
}

function bootstrapFromStaticIfAny() {
  // Give the UI a useful shape before the first backend scan finishes.
  state.rows = state.watchlist.map(t => ({ symbol: t, signal: "NEUTRAL", score: 0 }));
}

loadSettings();
bootstrapFromStaticIfAny();
bindHardWiredTabs();
bindEvents();
renderAll();
if (state.staticMode || isStaticDeployHost()) {
  loadStaticData({ message: "Loading GitHub Pages static data…" });
} else {
  scan(false);
}


/* v5.5 Memo page: localStorage investment memo dashboard */
(function initMemoFeature(){
  const MEMO_STORAGE = {
    memos: "stockTimingRadar.memos.v55",
    filters: "stockTimingRadar.memoFilters.v55",
    notified: "stockTimingRadar.memoNotified.v55",
    view: "stockTimingRadar.appView.v55",
    mobileView: "stockTimingRadar.memoMobileView.v72"
  };
  const STATUS = ["Watchlist", "Alert", "Done", "Ignored"];
  const TREND = ["Uptrend", "Downtrend", "Sideways", "Unknown"];
  const CONVICTION = ["Low", "Medium", "High"];
  const ACTIONS = ["Buy on pullback", "Wait for uptrend", "Buy breakout", "Avoid chasing", "Watch earnings", "Recheck valuation", "Hold off", "Custom"];
  const CATEGORIES = ["News", "Earnings", "Valuation", "Technical setup", "Pullback", "Breakout", "Thematic", "Other"];
  const MEMO_PHASES = [
    { value:"Early Uptrend", th:"เริ่มฟื้นตัว", cls:"early-uptrend", tone:"blue" },
    { value:"Uptrend Confirmed", th:"ขาขึ้นยืนยันแล้ว", cls:"uptrend-confirmed", tone:"green" },
    { value:"Healthy Pullback", th:"ย่อสุขภาพดี", cls:"healthy-pullback", tone:"teal" },
    { value:"Actionable", th:"น่าลงมือ", cls:"actionable", tone:"green" },
    { value:"HOT / Wait Pullback", th:"ร้อนแรง / รอย่อ", cls:"hot-wait-pullback", tone:"orange" },
    { value:"Squeeze Setup", th:"บีบตัวรอเบรก", cls:"squeeze-setup", tone:"purple" },
    { value:"Rotation Watch", th:"เงินเริ่มหมุนเข้า", cls:"rotation-watch", tone:"blue" },
    { value:"Distribution Risk", th:"เสี่ยงถูกขายออก", cls:"distribution-risk", tone:"red" },
    { value:"Oversold Watch", th:"ขายมากเกิน / รอฟื้น", cls:"oversold-watch", tone:"yellow" },
    { value:"Downtrend", th:"ขาลง", cls:"downtrend-phase", tone:"red" },
    { value:"Invalidated", th:"แผนเสียแล้ว", cls:"invalidated", tone:"red" },
    { value:"Done", th:"ปิดงานแล้ว", cls:"done-phase", tone:"gray" },
    { value:"Ignored", th:"พักไว้ก่อน", cls:"ignored-phase", tone:"gray" },
  ];
  const memoState = {
    memos: loadMemos(),
    filters: loadMemoFilters(),
    editingId: null,
    loading: false
  };

  function memoEsc(v){ return (typeof esc === "function" ? esc(v) : String(v ?? "").replace(/[&<>"']/g, s => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[s]))); }
  function memoToNum(v){ return typeof toNum === "function" ? toNum(v) : (Number.isFinite(Number(v)) ? Number(v) : null); }
  function memoFmtMoney(v){ return typeof fmtMoney === "function" ? fmtMoney(v) : (memoToNum(v) == null ? "—" : `$${memoToNum(v).toFixed(2)}`); }
  function memoPctLabel(v){ return typeof pctLabel === "function" ? pctLabel(v) : (memoToNum(v) == null ? "—" : `${memoToNum(v) > 0 ? "+" : ""}${memoToNum(v).toFixed(2)}%`); }
  function memoPctClass(v){ const n=memoToNum(v); return n==null ? "neutral" : n < 0 ? "red" : "green"; }
  function memoTicker(raw){ return typeof normalizeTicker === "function" ? normalizeTicker(raw) : String(raw||"").trim().toUpperCase().replace(/^[$#]+/, ""); }
  function memoNow(){ return new Date().toISOString(); }
  function memoLocalTime(iso){ try { return new Date(iso).toLocaleString(); } catch { return "—"; } }
  function uid(){ return `m_${Date.now()}_${Math.random().toString(16).slice(2)}`; }

  function loadMemos(){
    try { const parsed = JSON.parse(localStorage.getItem(MEMO_STORAGE.memos) || "[]"); if (Array.isArray(parsed)) return parsed; } catch(_) {}
    return [];
  }
  function saveMemos(){ localStorage.setItem(MEMO_STORAGE.memos, JSON.stringify(memoState.memos)); }
  function loadMemoFilters(){
    const base = { search:"", status:"All", trend:"All", conviction:"All", category:"All", actionPlan:"All", sort:"Alert first" };
    try { return { ...base, ...(JSON.parse(localStorage.getItem(MEMO_STORAGE.filters) || "{}") || {}) }; } catch { return base; }
  }
  function saveMemoFilters(){ localStorage.setItem(MEMO_STORAGE.filters, JSON.stringify(memoState.filters)); }
  function notifiedMap(){ try { return JSON.parse(localStorage.getItem(MEMO_STORAGE.notified) || "{}"); } catch { return {}; } }
  function setNotified(id){ const map = notifiedMap(); map[id] = true; localStorage.setItem(MEMO_STORAGE.notified, JSON.stringify(map)); }

  function buildAppNav(){
    if (document.querySelector(".app-mode-nav")) return;
    const brand = document.querySelector(".topbar .brand");
    if (!brand) return;
    const nav = document.createElement("nav");
    nav.className = "app-mode-nav";
    nav.innerHTML = `<button class="app-mode-btn active" data-app-view="scanner">Scanner</button><button class="app-mode-btn" data-app-view="memo">📝 Memo</button>`;
    brand.insertAdjacentElement("afterend", nav);
  }

  function buildMemoPage(){
    if (document.getElementById("memoPage")) return;
    const shell = document.querySelector(".app-shell");
    if (!shell) return;
    const page = document.createElement("section");
    page.id = "memoPage";
    page.className = "memo-page";
    page.innerHTML = `
      <div class="memo-shell">
        <section class="panel-card memo-top">
          <div class="memo-title"><h2>Stock Memo</h2><p>Track stock ideas, targets, alerts, trends, and action plans</p></div>
          <div class="memo-actions"><button class="primary-btn" data-memo-add>+ Add Memo</button><button class="secondary-btn" data-memo-add-from-screener>Add From Screener</button><button class="secondary-btn" data-memo-import-current>Import Current Stock</button><button class="secondary-btn" data-memo-refresh>Refresh Prices</button></div>
        </section>
        <section class="memo-stats" id="memoStats"></section>
        <section class="panel-card memo-filters" id="memoFilters">
          ${fieldHtml("Search", `<input data-memo-filter="search" type="search" placeholder="Search ticker or memo reason…" />`)}
          ${selectField("Status", "status", ["All", ...STATUS])}
          ${selectField("Trend", "trend", ["All", ...TREND])}
          ${selectField("Conviction", "conviction", ["All", ...CONVICTION])}
          ${selectField("Category", "category", ["All", ...CATEGORIES])}
          ${selectField("Action plan", "actionPlan", ["All", ...ACTIONS])}
          ${selectField("Sort", "sort", ["Alert first", "High conviction first", "Most actionable first", "Newest first", "% from target", "% change", "Trend", "Ticker"])}
        </section>
        <div class="memo-view-toggle" role="tablist" aria-label="Memo view">
          <button type="button" class="memo-view-btn active" data-memo-view="cards">Card View</button>
          <button type="button" class="memo-view-btn" data-memo-view="table">Table View</button>
        </div>
        <section class="panel-card memo-table-card"><div class="memo-table-wrap"><table class="memo-table"><thead><tr>
          <th>Memo Status</th><th>Note date/time</th><th>Stock ticker</th><th>Memo reason</th><th>Source link</th><th>Price at note</th><th>Current price</th><th>% change</th><th>Target price</th><th>% from target</th><th>Tags</th><th>Alert Ladder</th><th>Conviction</th><th>Action plan</th><th>Actions</th>
        </tr></thead><tbody id="memoTableBody"></tbody></table></div></section>
        <section class="memo-mobile-list" id="memoMobileList"></section>
      </div>
      <button class="memo-fab" data-memo-fab aria-label="Create memo">+</button>
    `;
    shell.appendChild(page);
    const modal = document.createElement("section");
    modal.id = "memoModal";
    modal.className = "memo-modal";
    modal.hidden = true;
    modal.innerHTML = memoModalHtml();
    document.body.appendChild(modal);
    const toast = document.createElement("div");
    toast.id = "memoToast";
    toast.className = "memo-toast";
    toast.hidden = true;
    document.body.appendChild(toast);
    const actionSheet = document.createElement("section");
    actionSheet.id = "memoActionSheet";
    actionSheet.className = "memo-action-sheet";
    actionSheet.hidden = true;
    actionSheet.innerHTML = `
      <div class="memo-sheet-backdrop" data-memo-action-close></div>
      <div class="memo-sheet-card" role="dialog" aria-modal="true" aria-label="Create memo action sheet">
        <div class="memo-sheet-handle"></div>
        <div class="memo-sheet-head"><h3>Create</h3><button class="icon-btn" type="button" data-memo-action-close>×</button></div>
        <button class="memo-sheet-action primary" type="button" data-memo-action-add><span>＋</span><strong>Add Memo</strong><small>Start with a blank memo form</small></button>
        <button class="memo-sheet-action" type="button" data-memo-action-picker><span>⌕</span><strong>Add From Screener</strong><small>Search existing scanner results and prefill price / trend / EMA status</small></button>
        <button class="memo-sheet-action" type="button" data-memo-action-current><span>↳</span><strong>Import Current Stock</strong><small>Use the stock currently selected in the scanner</small></button>
      </div>`;
    document.body.appendChild(actionSheet);
    const picker = document.createElement("section");
    picker.id = "memoScreenerPicker";
    picker.className = "memo-picker-modal";
    picker.hidden = true;
    picker.innerHTML = `
      <div class="memo-modal-backdrop" data-memo-picker-cancel></div>
      <div class="memo-picker-card" role="dialog" aria-modal="true" aria-label="Pick stock from screener">
        <div class="memo-modal-header"><div><h2>Add From Screener</h2><p class="memo-picker-subtitle">Search ticker or select a stock from current scanner results.</p></div><button class="icon-btn" type="button" data-memo-picker-cancel>×</button></div>
        <div class="memo-picker-search"><input id="memoPickerSearch" type="search" placeholder="Search ticker, signal, or company…" autocomplete="off" data-memo-picker-search /></div>
        <div id="memoPickerList" class="memo-picker-list"></div>
      </div>`;
    document.body.appendChild(picker);
    const globalFab = document.createElement("button");
    globalFab.id = "memoGlobalFab";
    globalFab.className = "memo-global-fab";
    globalFab.type = "button";
    globalFab.setAttribute("aria-label", "Create memo or import stock");
    globalFab.setAttribute("data-memo-fab", "");
    globalFab.textContent = "+";
    document.body.appendChild(globalFab);
  }
  function fieldHtml(label, control){ return `<div class="memo-field"><label>${label}</label>${control}</div>`; }
  function selectField(label, key, options){ return fieldHtml(label, `<select data-memo-filter="${key}">${options.map(o => `<option value="${memoEsc(o)}">${memoEsc(o)}</option>`).join("")}</select>`); }
  function memoModalHtml(){
    return `<div class="memo-modal-backdrop" data-memo-cancel></div><div class="memo-modal-card" role="dialog" aria-modal="true" aria-labelledby="memoModalTitle">
      <div class="memo-modal-header"><div><h2 id="memoModalTitle">Add Memo</h2><p class="memo-modal-subtitle">Create or import an idea. Screener imports prefill stock data first; you finish the thesis.</p></div><button class="icon-btn" type="button" data-memo-cancel>×</button></div>
      <form class="memo-form" id="memoForm">
        <input type="hidden" name="prefillNotePrice" />
        <input type="hidden" name="prefillCurrentPrice" />
        <input type="hidden" name="prefillTrend" />
        <input type="hidden" name="prefillEmaStatus" />
        <input type="hidden" name="prefillEmaDistance" />
        <div id="memoPrefillPreview" class="memo-prefill-preview wide" hidden></div>
        ${fieldHtml("Ticker", `<input name="ticker" required placeholder="NVDA" autocomplete="off" />`)}
        ${fieldHtml("Memo status", `<select name="memoPhase">${MEMO_PHASES.map(x=>`<option value="${memoEsc(x.value)}">${memoEsc(x.th)} · ${memoEsc(x.value)}</option>`).join("")}</select>`)}
        ${fieldHtml("Target price", `<input name="targetPrice" required inputmode="decimal" type="number" step="0.0001" placeholder="120.00" />`)}
        ${fieldHtml("Target direction", `<select name="targetDirection"><option value="lte">Alert when price <= target</option><option value="gte">Alert when price >= target</option></select>`)}
        ${fieldHtml("Alert condition", `<select name="alertType"><option value="priceTarget">Price reaches target</option><option value="priceNearEma">Price near EMA line</option><option value="ema5GtEma89">EMA5 > EMA89</option><option value="ema89GtEma200">EMA89 > EMA200</option><option value="uptrendConfirm">EMA5 > EMA20 and EMA89 > EMA200</option></select>`)}
        ${fieldHtml("EMA alert line", `<select name="alertEmaLine"><option value="EMA20">EMA20</option><option value="EMA5">EMA5</option><option value="EMA89">EMA89</option><option value="EMA200">EMA200</option></select>`)}
        ${fieldHtml("EMA distance tolerance %", `<input name="alertDistancePct" inputmode="decimal" type="number" step="0.1" value="2" placeholder="2.0" />`)}
        ${fieldHtml("Conviction", `<select name="conviction">${CONVICTION.map(x=>`<option>${x}</option>`).join("")}</select>`)}
        ${fieldHtml("Action plan", `<select name="actionPlan">${ACTIONS.map(x=>`<option>${x}</option>`).join("")}</select>`)}
        ${fieldHtml("Category", `<select name="category">${CATEGORIES.map(x=>`<option>${x}</option>`).join("")}</select>`)}
        ${fieldHtml("Custom action plan", `<input name="customActionPlan" placeholder="Optional when Custom is selected" />`)}
        ${fieldHtml("Source link", `<input name="sourceLink" type="url" inputmode="url" placeholder="https://…" />`)}
        ${fieldHtml("Memo reason", `<textarea name="reason" required placeholder="Why is this stock interesting? What price matters? What action should be taken?"></textarea>`).replace('class="memo-field"','class="memo-field wide"')}
        <div class="memo-form-actions"><button type="button" class="secondary-btn" data-memo-cancel>Cancel</button><button type="submit" class="primary-btn">Save Memo</button></div>
      </form>
    </div>`;
  }

  function setAppView(view){
    const memo = view === "memo";
    document.body.classList.toggle("memo-active", memo);
    document.querySelectorAll("[data-app-view]").forEach(b => b.classList.toggle("active", b.dataset.appView === view));
    localStorage.setItem(MEMO_STORAGE.view, view);
    if (memo) renderMemo();
  }

  function memoSlug(value){ return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "unknown"; }
  function memoPhaseMeta(value){
    const raw = String(value || "").trim();
    return MEMO_PHASES.find(x => x.value === raw || x.th === raw || memoSlug(x.value) === memoSlug(raw)) || MEMO_PHASES[0];
  }
  function suggestedMemoPhase(m){
    const stock = stockForMemoTicker(m?.ticker);
    const rsi = memoToNum(stock?.rsi);
    const e20 = memoToNum(stock?.ema20Pct), e89 = memoToNum(stock?.ema89Pct), e200 = memoToNum(stock?.ema200Pct);
    const vol = memoToNum(stock?.volumeRatio ?? stock?.volRatio);
    if (m?.status === "Done") return "Done";
    if (m?.status === "Ignored") return "Ignored";
    if (rsi != null && rsi < 30) return "Oversold Watch";
    if (rsi != null && rsi > 70) return "HOT / Wait Pullback";
    if (e20 != null && e89 != null && e200 != null && e20 > 0 && e89 > 0 && e200 > 0) {
      if ((Math.abs(e20) <= 5 || Math.abs(e89) <= 8) && rsi != null && rsi >= 45 && rsi <= 65) return "Healthy Pullback";
      return "Uptrend Confirmed";
    }
    if (e20 != null && e89 != null && e20 > 0 && e89 > -3) return "Early Uptrend";
    if (e20 != null && e89 != null && e200 != null && e20 < 0 && e89 < 0 && e200 < 0) return "Downtrend";
    if (vol != null && vol > 1.8 && e20 != null && e20 < 0) return "Distribution Risk";
    return "Early Uptrend";
  }
  function memoPhaseFor(m){ return m?.memoPhase || suggestedMemoPhase(m); }
  function memoPhaseBadge(m, opts={}){
    const meta = memoPhaseMeta(memoPhaseFor(m));
    const compact = opts.compact;
    return `<span class="memo-phase-badge ${memoEsc(meta.cls)}"><span class="memo-phase-th">${memoEsc(meta.th)}</span>${compact ? "" : `<span class="memo-phase-en">${memoEsc(meta.value)}</span>`}</span>`;
  }
  function memoTriggeredTags(m){
    const tags = [];
    const stock = stockForMemoTicker(m?.ticker) || {};
    const phase = memoPhaseMeta(memoPhaseFor(m)).value;
    const e20 = memoToNum(stock.ema20Pct), e89 = memoToNum(stock.ema89Pct), e200 = memoToNum(stock.ema200Pct);
    const rsi = memoToNum(stock.rsi), macd = memoToNum(stock.macdHist ?? stock.macdHistogram), vol = memoToNum(stock.volumeRatio ?? stock.volRatio);
    if (m?.emaDistance && m.emaDistance !== "—") tags.push(m.emaDistance);
    else if (e20 != null) tags.push(`EMA20 ${memoPctLabel(e20)}`);
    if (rsi != null) tags.push(`RSI ${rsi.toFixed(0)}${rsi >= 70 ? " Hot" : rsi >= 50 && rsi <= 65 ? " Healthy" : rsi < 45 ? " Weak" : ""}`);
    if (macd != null) tags.push(macd >= 0 ? "MACD Bullish" : "MACD Weakening");
    if (vol != null && vol > 1.5) tags.push(`Volume ${vol.toFixed(1)}x`);
    if (phase === "HOT / Wait Pullback" && e89 != null) tags.unshift(`EMA89 ${memoPctLabel(e89)}`);
    if (phase === "Distribution Risk") tags.unshift("Volume Spike Down");
    if (!tags.length && m?.emaStatus) tags.push(...String(m.emaStatus).split(" · ").slice(0,3));
    return [...new Set(tags.filter(Boolean))].slice(0,3);
  }
  function memoTagsHtml(m){
    const tags = memoTriggeredTags(m);
    if (!tags.length) return `<span class="memo-tag neutral">No technical tags yet</span>`;
    return tags.map(t => {
      const neg = /below|weak|down|-\d|risk/i.test(t);
      const hot = /hot|\+([2-9]\d|1[5-9])|volume/i.test(t);
      return `<span class="memo-tag ${neg ? "risk" : hot ? "warm" : "good"}">${memoEsc(t)}</span>`;
    }).join("");
  }
  function memoAlertLadderHtml(m){
    const phase = memoPhaseMeta(memoPhaseFor(m)).value;
    const positive = ["Early Uptrend","Uptrend Confirmed","Healthy Pullback","Actionable"];
    const done = label => {
      if (label === "Early Uptrend") return positive.includes(phase) || phase === "HOT / Wait Pullback";
      if (label === "Uptrend Confirmed") return ["Uptrend Confirmed","Healthy Pullback","Actionable","HOT / Wait Pullback"].includes(phase);
      if (label === "Healthy Pullback") return ["Healthy Pullback","Actionable"].includes(phase);
      if (label === "HOT / Wait Pullback") return phase === "HOT / Wait Pullback";
      if (label === "Distribution Risk") return ["Distribution Risk","Downtrend","Invalidated"].includes(phase);
      return false;
    };
    const steps = [
      ["Early Uptrend","เริ่มฟื้นตัว"],
      ["Uptrend Confirmed","ขาขึ้นยืนยันแล้ว"],
      ["Healthy Pullback","ย่อสุขภาพดี"],
      phase === "Distribution Risk" || phase === "Downtrend" || phase === "Invalidated" ? ["Distribution Risk","เสี่ยงถูกขายออก"] : ["HOT / Wait Pullback","ร้อนแรง / รอย่อ"],
    ];
    return `<div class="memo-ladder">${steps.map(([en,th]) => `<span class="memo-ladder-step ${done(en) ? "done" : "todo"}"><b>${done(en) ? "✓" : "☐"}</b>${memoEsc(th)}</span>`).join("")}</div>`;
  }

  function statusClass(status){ return String(status||"Watchlist").toLowerCase(); }
  function statusLabel(status){ return status === "Alert" ? "🚨 Alert" : status === "Done" ? "✅ Done" : status === "Ignored" ? "❌ Ignored" : "👀 Watchlist"; }
  function trendClass(trend){ return String(trend||"Unknown").toLowerCase(); }
  function convictionClass(conviction){ return String(conviction||"Low").toLowerCase(); }
  function trendBadge(trend){ return `<span class="memo-badge ${trendClass(trend)}">${memoEsc(trend || "Unknown")}</span>`; }
  function statusBadge(status){ return `<span class="memo-badge ${statusClass(status)}">${memoEsc(statusLabel(status))}</span>`; }
  function convictionBadge(c){ return `<span class="memo-badge ${convictionClass(c)}">${memoEsc(c || "Low")}</span>`; }
  function signedPct(v){
    const n = memoToNum(v);
    const cls = n == null ? "neutral" : n > 0 ? "memo-pct-up green" : n < 0 ? "memo-pct-down red" : "memo-pct-flat neutral";
    return `<span class="memo-pct ${cls}">${memoPctLabel(v)}</span>`;
  }
  function calcPctChange(current, note){ const c=memoToNum(current), n=memoToNum(note); return c==null || !n ? null : ((c-n)/n)*100; }
  function calcFromTarget(current, target){ const c=memoToNum(current), t=memoToNum(target); return c==null || !t ? null : ((c-t)/t)*100; }
  function isTargetReached(memo){
    const p=memoToNum(memo.currentPrice), t=memoToNum(memo.targetPrice); if(p==null || t==null) return false;
    return memo.targetDirection === "lte" ? p <= t : p >= t;
  }
  function stockForMemoTicker(ticker){
    const t = memoTicker(ticker);
    let stocks = [];
    try { stocks = typeof allWatchlistStocks === "function" ? allWatchlistStocks() : []; } catch (_) { stocks = []; }
    if (!Array.isArray(stocks) || !stocks.length) { try { stocks = typeof scannerStocks === "function" ? scannerStocks() : []; } catch (_) {} }
    return (stocks || []).find(s => memoTicker(s?.ticker || s?.symbol) === t) || null;
  }
  function pctToEmaPrice(current, pct){
    const c = memoToNum(current), p = memoToNum(pct);
    if (c == null || p == null || (1 + p/100) === 0) return null;
    return c / (1 + p/100);
  }
  function emaPriceFromStock(stock, line){
    if (!stock) return null;
    const key = String(line || "").toLowerCase();
    const direct = memoToNum(stock[key] ?? stock[`${key}Price`]);
    if (direct != null) return direct;
    const pct = memoToNum(stock[`${key}Pct`]);
    return pctToEmaPrice(stock.price, pct);
  }
  function emaPctFromStock(stock, line){
    if (!stock) return null;
    const key = String(line || "").toLowerCase();
    const direct = memoToNum(stock[`${key}Pct`]);
    if (direct != null) return direct;
    const price = memoToNum(stock.price), emaP = emaPriceFromStock(stock, line);
    return price == null || !emaP ? null : ((price / emaP) - 1) * 100;
  }
  function memoAlertLabel(memo){
    const type = memo.alertType || "priceTarget";
    if (type === "priceNearEma") return `Near ${memo.alertEmaLine || "EMA20"} ≤ ${memo.alertDistancePct || 2}%`;
    if (type === "ema5GtEma89") return "EMA5 > EMA89";
    if (type === "ema89GtEma200") return "EMA89 > EMA200";
    if (type === "uptrendConfirm") return "EMA5 > EMA20 + EMA89 > EMA200";
    return `Target ${memo.targetDirection === "gte" ? "≥" : "≤"} ${memoFmtMoney(memo.targetPrice)}`;
  }
  function isMemoAlertReached(memo){
    const type = memo.alertType || "priceTarget";
    if (type === "priceTarget") return isTargetReached(memo);
    const stock = stockForMemoTicker(memo.ticker);
    if (!stock) return false;
    const current = memoToNum(stock.price ?? memo.currentPrice);
    if (type === "priceNearEma") {
      const line = memo.alertEmaLine || "EMA20";
      const pct = emaPctFromStock(stock, line);
      const tol = memoToNum(memo.alertDistancePct) ?? 2;
      return pct != null && Math.abs(pct) <= Math.abs(tol);
    }
    const e5 = emaPriceFromStock(stock, "EMA5"), e20 = emaPriceFromStock(stock, "EMA20"), e89 = emaPriceFromStock(stock, "EMA89"), e200 = emaPriceFromStock(stock, "EMA200");
    if (type === "ema5GtEma89") return e5 != null && e89 != null && e5 > e89;
    if (type === "ema89GtEma200") return e89 != null && e200 != null && e89 > e200;
    if (type === "uptrendConfirm") return e5 != null && e20 != null && e89 != null && e200 != null && e5 > e20 && e89 > e200 && (current == null || current > e200);
    return false;
  }
  function shortReason(reason){ const r=String(reason||""); return r.length <= 120 ? memoEsc(r) : `${memoEsc(r.slice(0,120))}…<details><summary>More</summary>${memoEsc(r)}</details>`; }
  function sourceLinkHtml(url){ return url ? `<a class="memo-source-btn" href="${memoEsc(url)}" target="_blank" rel="noopener noreferrer">Source ↗</a>` : `<span class="neutral">—</span>`; }

  function ema(values, period){
    const nums = values.map(memoToNum); let k = 2/(period+1), out = [], prev = null;
    nums.forEach(v => { if(v==null){ out.push(prev); return; } prev = prev==null ? v : (v*k + prev*(1-k)); out.push(prev); });
    return out;
  }
  function trendFromQuote(latest, quote){
    const series = Array.isArray(quote?.series) ? quote.series : [];
    const current = memoToNum(latest?.close ?? latest?.regularMarketPrice ?? latest?.price);
    if (!series.length || current == null) return "Unknown";
    const closes = series.map(x => memoToNum(x.close)).filter(v => v != null);
    if (closes.length < 60) return "Unknown";
    const ema20 = ema(closes,20), ema50 = ema(closes,50);
    const e20 = ema20[ema20.length-1], e50 = ema50[ema50.length-1], e50Prev = ema50[Math.max(0, ema50.length-6)];
    if ([e20,e50,e50Prev].some(v => v == null)) return "Unknown";
    if (current > e50 && e20 > e50 && e50 > e50Prev) return "Uptrend";
    if (current < e50 && e20 < e50 && e50 < e50Prev) return "Downtrend";
    return "Sideways";
  }

  function enrichMemo(m){
    const current = memoToNum(m.currentPrice);
    const out = { ...m };
    out.changePct = calcPctChange(current, m.notePrice);
    out.fromTargetPct = calcFromTarget(current, m.targetPrice);
    if (out.status !== "Done" && out.status !== "Ignored" && isMemoAlertReached(out)) out.status = "Alert";
    return out;
  }
  function maybeNotify(memo){
    if (memo.status !== "Alert") return;
    const notified = notifiedMap();
    if (notified[memo.id]) return;
    // Only suppress repeated browser/toast notifications; this does not hide the saved memo.
    setNotified(memo.id);
    showMemoToast("🚨 Target reached", `${memo.ticker}: ${memoFmtMoney(memo.currentPrice)} reached target ${memoFmtMoney(memo.targetPrice)}`);
    if ("Notification" in window && Notification.permission === "granted") {
      try { new Notification(`Stock alert: ${memo.ticker}`, { body: `${memoFmtMoney(memo.currentPrice)} reached target ${memoFmtMoney(memo.targetPrice)}` }); } catch(_) {}
    } else if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().catch(()=>{});
    }
  }
  function showMemoToast(title, text){
    const el = document.getElementById("memoToast"); if(!el) return;
    el.innerHTML = `<strong>${memoEsc(title)}</strong><span>${memoEsc(text)}</span>`;
    el.hidden = false; clearTimeout(showMemoToast._timer); showMemoToast._timer = setTimeout(()=>{ el.hidden = true; }, 5200);
  }

  async function fetchMemoPrice(ticker){
    const t = memoTicker(ticker);
    const existing = (typeof allWatchlistStocks === "function" ? allWatchlistStocks() : []).find(s => s.ticker === t);
    let best = existing && memoToNum(existing.price) != null ? { price:memoToNum(existing.price), trend: existing.ema20 && existing.price ? "Unknown" : "Unknown", quote: existing.quote, latest: existing.raw || {} } : null;
    try {
      const params = new URLSearchParams({ symbol:t, range:"1y", interval:"1d", includeFundamentals:"0", v:String(Date.now()) });
      const data = await fetchJson(`/api/quote?${params}`);
      const latest = data.latest || {};
      const row = typeof mapRow === "function" ? mapRow(latest) : latest;
      const price = memoToNum(row.price ?? latest.close ?? latest.regularMarketPrice);
      const trend = trendFromQuote(latest, data);
      if (price != null) return { price, trend, raw:data, latest };
    } catch(err) { console.warn("memo price fetch failed", t, err); }
    return best || { price:null, trend:"Unknown", raw:null, latest:{} };
  }

  async function refreshMemo(memo, {silent=false}={}){
    if(!silent) showMemoToast("Refreshing price", memo.ticker);
    const price = await fetchMemoPrice(memo.ticker);
    const next = enrichMemo({ ...memo, currentPrice: price.price ?? memo.currentPrice, trend: price.trend || memo.trend || "Unknown", updatedAt:memoNow() });
    const idx = memoState.memos.findIndex(x => x.id === memo.id);
    if (idx >= 0) memoState.memos[idx] = next;
    saveMemos(); maybeNotify(next); renderMemo();
  }
  async function refreshAllMemos(){
    if (!memoState.memos.length) return;
    memoState.loading = true; renderMemo();
    for (const m of memoState.memos) await refreshMemo(m, {silent:true});
    memoState.loading = false; saveMemos(); renderMemo(); showMemoToast("Prices refreshed", `${memoState.memos.length} memos checked`);
  }

  function getFilteredMemos(){
    const f = memoState.filters;
    let arr = memoState.memos.map(enrichMemo);
    const q = String(f.search||"").trim().toLowerCase();
    if(q) arr = arr.filter(m => `${m.ticker} ${m.reason}`.toLowerCase().includes(q));
    if(f.status !== "All") arr = arr.filter(m => m.status === f.status);
    if(f.trend !== "All") arr = arr.filter(m => (m.trend || "Unknown") === f.trend);
    if(f.conviction !== "All") arr = arr.filter(m => m.conviction === f.conviction);
    if(f.category !== "All") arr = arr.filter(m => m.category === f.category);
    if(f.actionPlan !== "All") arr = arr.filter(m => (m.actionPlan === f.actionPlan || m.customActionPlan === f.actionPlan));
    const rankStatus = { Alert:0, Watchlist:1, Done:2, Ignored:3 };
    const rankConv = { High:0, Medium:1, Low:2 };
    const rankTrend = { Uptrend:0, Sideways:1, Unknown:2, Downtrend:3 };
    const actionable = m => (m.status === "Alert" ? 1000 : 0) + (m.conviction === "High" ? 100 : m.conviction === "Medium" ? 50 : 10) + (m.trend === "Uptrend" ? 25 : m.trend === "Sideways" ? 5 : 0) - Math.abs(memoToNum(m.fromTargetPct) ?? 999);
    arr.sort((a,b)=>{
      switch(f.sort){
        case "High conviction first": return (rankConv[a.conviction]??9) - (rankConv[b.conviction]??9) || (rankStatus[a.status]??9)-(rankStatus[b.status]??9);
        case "Most actionable first": return actionable(b) - actionable(a);
        case "Newest first": return new Date(b.createdAt||0) - new Date(a.createdAt||0);
        case "% from target": return Math.abs(memoToNum(a.fromTargetPct)??999) - Math.abs(memoToNum(b.fromTargetPct)??999);
        case "% change": return (memoToNum(b.changePct)??-999) - (memoToNum(a.changePct)??-999);
        case "Trend": return (rankTrend[a.trend]??9) - (rankTrend[b.trend]??9);
        case "Ticker": return String(a.ticker).localeCompare(String(b.ticker));
        default: return (rankStatus[a.status]??9) - (rankStatus[b.status]??9) || (rankConv[a.conviction]??9) - (rankConv[b.conviction]??9) || new Date(b.createdAt||0) - new Date(a.createdAt||0);
      }
    });
    return arr;
  }

  function renderMemo(){
    if(!document.body.classList.contains("memo-active") && localStorage.getItem(MEMO_STORAGE.view) !== "memo") return;
    memoState.memos = loadMemos().map(enrichMemo);
    saveMemos();
    const mv = localStorage.getItem(MEMO_STORAGE.mobileView) || "cards";
    document.body.classList.toggle("memo-mobile-table-view", mv === "table");
    document.querySelectorAll("[data-memo-view]").forEach(btn => btn.classList.toggle("active", btn.dataset.memoView === mv));
    renderMemoStats(); renderMemoFilters(); renderMemoTable(); renderMemoCards();
  }
  function renderMemoStats(){
    const el = document.getElementById("memoStats"); if(!el) return;
    const counts = { Watchlist:0, Alert:0, Done:0, Ignored:0 };
    memoState.memos.forEach(m => { counts[enrichMemo(m).status] = (counts[enrichMemo(m).status]||0)+1; });
    el.innerHTML = [["Watchlist",counts.Watchlist,"👀"],["Alert",counts.Alert,"🚨"],["Done",counts.Done,"✅"],["Ignored",counts.Ignored,"❌"]].map(([k,v,icon])=>`<div class="memo-stat"><span>${icon} ${k}</span><b>${v}</b></div>`).join("");
  }
  function renderMemoFilters(){
    document.querySelectorAll("[data-memo-filter]").forEach(el => { const k=el.dataset.memoFilter; if (document.activeElement !== el) el.value = memoState.filters[k] ?? ""; });
  }
  function renderMemoTable(){
    const body = document.getElementById("memoTableBody"); if(!body) return;
    const memos = getFilteredMemos();
    if(!memos.length){ body.innerHTML = `<tr><td colspan="15" class="memo-empty">No memos yet. Add one to start tracking an idea.</td></tr>`; return; }
    body.innerHTML = memos.map(m => `<tr class="${statusClass(m.status)}-row">
      <td>${memoPhaseBadge(m)}<div class="memo-table-substatus">${statusBadge(m.status)}${m.status === "Alert" ? `<span class="memo-target-hit">Triggered</span>` : ""}</div></td>
      <td class="memo-date">${memoEsc(memoLocalTime(m.createdAt))}</td>
      <td><button class="memo-ticker-link" type="button" data-memo-open-ticker="${memoEsc(m.ticker)}"><span class="memo-ticker">${memoEsc(m.ticker)}</span></button><br><small>${memoEsc(m.category||"Other")}</small></td>
      <td><div class="memo-reason">${shortReason(m.reason)}</div></td>
      <td>${sourceLinkHtml(m.sourceLink)}</td>
      <td>${memoFmtMoney(m.notePrice)}</td><td>${memoFmtMoney(m.currentPrice)}</td><td>${signedPct(m.changePct)}</td><td>${memoFmtMoney(m.targetPrice)}</td><td>${signedPct(m.fromTargetPct)}</td>
      <td><div class="memo-tags compact">${memoTagsHtml(m)}</div></td><td>${memoAlertLadderHtml(m)}</td><td>${convictionBadge(m.conviction)}</td><td>${memoEsc(m.actionPlan === "Custom" ? (m.customActionPlan || "Custom") : m.actionPlan)}</td>
      <td>${memoActionsHtml(m)}</td>
    </tr>`).join("");
  }
  function renderMemoCards(){
    const list = document.getElementById("memoMobileList"); if(!list) return;
    const memos = getFilteredMemos();
    if(!memos.length){ list.innerHTML = `<div class="panel-card memo-empty">No memos yet. Tap + Add Memo.</div>`; return; }
    list.innerHTML = memos.map(m => `<article class="memo-card ${statusClass(m.status)}-card memo-phase-card ${memoEsc(memoPhaseMeta(memoPhaseFor(m)).cls)}">
      <div class="memo-card-top"><div><button class="memo-ticker-link card" type="button" data-memo-open-ticker="${memoEsc(m.ticker)}"><span class="memo-ticker">${memoEsc(m.ticker)}</span></button><br><small>${memoEsc(m.category||"Other")} · ${memoEsc(memoLocalTime(m.createdAt))}</small></div><div class="memo-card-conviction">${memoEsc(m.conviction || "Low")} ${convictionBadge(m.conviction)}</div></div>
      <div class="memo-primary-status">${memoPhaseBadge(m)}</div>
      <div class="memo-card-kpis compact"><div class="memo-kpi"><span>Current</span><b>${memoFmtMoney(m.currentPrice)}</b></div><div class="memo-kpi"><span>Note</span><b>${memoFmtMoney(m.notePrice)} <small>${signedPct(m.changePct)} from note</small></b></div><div class="memo-kpi"><span>Target</span><b>${memoFmtMoney(m.targetPrice)} <small>${signedPct(m.fromTargetPct)} to target</small></b></div></div>
      <div class="memo-section-label">Status Tags</div><div class="memo-tags">${memoTagsHtml(m)}</div>
      <div class="memo-section-label">Alert Ladder</div>${memoAlertLadderHtml(m)}
      <div class="memo-section-label">Action Plan</div><div class="memo-card-reason"><b>${memoEsc(m.actionPlan === "Custom" ? (m.customActionPlan || "Custom") : m.actionPlan)}</b><br>${shortReason(m.reason)}</div>
      <div class="memo-card-footer">${sourceLinkHtml(m.sourceLink)}<div class="memo-card-actions">${memoActionsHtml(m)}</div></div>
    </article>`).join("");
  }

  function memoStockList(){
    let stocks = [];
    try { stocks = typeof scannerStocks === "function" ? scannerStocks() : []; } catch (_) { stocks = []; }
    if (!Array.isArray(stocks) || !stocks.length) {
      try { stocks = typeof allWatchlistStocks === "function" ? allWatchlistStocks() : []; } catch (_) { stocks = []; }
    }
    const seen = new Set();
    return (stocks || []).filter(s => {
      const t = memoTicker(s?.ticker || s?.symbol);
      if (!t || seen.has(t)) return false;
      seen.add(t);
      return true;
    });
  }
  function trendFromStock(s){
    const e20 = memoToNum(s?.ema20Pct), e89 = memoToNum(s?.ema89Pct), e200 = memoToNum(s?.ema200Pct);
    const rsi = memoToNum(s?.rsi);
    if ([e20,e89,e200].every(v => v != null && v > 0)) return rsi != null && rsi > 70 ? "Uptrend - hot" : "Uptrend";
    if ([e20,e89,e200].every(v => v != null && v < 0)) return "Downtrend";
    if (e20 != null || e89 != null || e200 != null) return "Sideways";
    return s?.trend || "Unknown";
  }
  function emaStatusFromStock(s){
    if (!s || s.isPlaceholder) return "—";
    const parts = [];
    [["EMA5",s.ema5Pct],["EMA20",s.ema20Pct],["EMA89",s.ema89Pct],["EMA200",s.ema200Pct]].forEach(([k,v]) => {
      if (memoToNum(v) != null) parts.push(`${k} ${memoPctLabel(v)}`);
    });
    return parts.length ? parts.join(" · ") : "—";
  }
  function nearestEmaDistanceFromStock(s){
    if (!s || s.isPlaceholder) return "—";
    const pairs = [["EMA5",s.ema5Pct],["EMA20",s.ema20Pct],["EMA89",s.ema89Pct],["EMA200",s.ema200Pct]]
      .map(([k,v]) => [k, memoToNum(v)]).filter(([,v]) => v != null).sort((a,b)=>Math.abs(a[1])-Math.abs(b[1]));
    return pairs.length ? `${pairs[0][0]} ${memoPctLabel(pairs[0][1])}` : "—";
  }
  function stockToMemoPrefill(stock){
    const s = stock || (typeof getSelected === "function" ? getSelected() : null) || {};
    const ticker = memoTicker(s.ticker || s.symbol || state?.selected || "");
    const price = memoToNum(s.price ?? s.close ?? s.regularMarketPrice);
    const trend = trendFromStock(s);
    const emaStatus = emaStatusFromStock(s);
    const emaDistance = nearestEmaDistanceFromStock(s);
    return { ticker, currentPrice: price, notePrice: price, trend, emaStatus, emaDistance, signal: s.signal || "", score: s.score ?? null };
  }
  function currentSelectedPrefill(){
    let s = null;
    try { s = typeof getSelected === "function" ? getSelected() : null; } catch (_) {}
    if (!s || s.isPlaceholder) {
      try { s = memoStockList().find(x => memoTicker(x.ticker) === memoTicker(state?.selected)) || s; } catch (_) {}
    }
    return stockToMemoPrefill(s);
  }
  function applyMemoPrefill(form, prefill){
    if (!form) return;
    const p = prefill || {};
    if (p.ticker && form.elements.ticker) form.elements.ticker.value = memoTicker(p.ticker);
    if (form.elements.prefillNotePrice) form.elements.prefillNotePrice.value = p.notePrice ?? p.currentPrice ?? "";
    if (form.elements.prefillCurrentPrice) form.elements.prefillCurrentPrice.value = p.currentPrice ?? p.notePrice ?? "";
    if (form.elements.prefillTrend) form.elements.prefillTrend.value = p.trend || "";
    if (form.elements.prefillEmaStatus) form.elements.prefillEmaStatus.value = p.emaStatus || "";
    if (form.elements.prefillEmaDistance) form.elements.prefillEmaDistance.value = p.emaDistance || "";
    const preview = document.getElementById("memoPrefillPreview");
    if (preview && p.ticker) {
      preview.hidden = false;
      preview.innerHTML = `<div class="memo-prefill-title"><span>${memoEsc(memoTicker(p.ticker))}</span><b>${memoFmtMoney(p.currentPrice ?? p.notePrice)}</b></div>
        <div class="memo-prefill-grid"><span>Trend <b>${memoEsc(p.trend || "Unknown")}</b></span><span>Nearest EMA <b>${memoEsc(p.emaDistance || "—")}</b></span><span>EMA status <b>${memoEsc(p.emaStatus || "—")}</b></span>${p.score != null ? `<span>Score <b>${memoEsc(p.score)}</b></span>` : ""}</div>`;
    } else if (preview) {
      preview.hidden = true;
      preview.innerHTML = "";
    }
  }
  function openMemoActionSheet(){ const el=document.getElementById("memoActionSheet"); if(el){ el.hidden=false; document.body.classList.add("memo-create-sheet-open"); } }
  function closeMemoActionSheet(){ const el=document.getElementById("memoActionSheet"); if(el){ el.hidden=true; document.body.classList.remove("memo-create-sheet-open"); } }
  function openMemoPicker(){
    closeMemoActionSheet();
    const picker = document.getElementById("memoScreenerPicker");
    if(!picker) return;
    picker.hidden = false;
    renderMemoPicker("");
    setTimeout(()=>document.getElementById("memoPickerSearch")?.focus(), 60);
  }
  function closeMemoPicker(){ const picker=document.getElementById("memoScreenerPicker"); if(picker) picker.hidden=true; }
  function renderMemoPicker(query=""){
    const list = document.getElementById("memoPickerList");
    if(!list) return;
    const q = String(query||"").trim().toLowerCase();
    const stocks = memoStockList().filter(s => {
      const hay = `${s.ticker||s.symbol||""} ${s.company||""} ${s.signal||""}`.toLowerCase();
      return !q || hay.includes(q);
    }).slice(0, 80);
    const exact = memoTicker(query);
    const useManual = exact && !stocks.some(s => memoTicker(s.ticker || s.symbol) === exact);
    const manual = useManual ? `<button type="button" class="memo-picker-row manual" data-memo-pick-manual="${memoEsc(exact)}"><strong>Use ${memoEsc(exact)}</strong><span>Not in current scanner results. Create memo with ticker only.</span></button>` : "";
    list.innerHTML = manual + (stocks.length ? stocks.map(s => {
      const p = stockToMemoPrefill(s);
      return `<button type="button" class="memo-picker-row" data-memo-pick-stock="${memoEsc(p.ticker)}">
        <span class="memo-picker-ticker">${memoEsc(p.ticker)}</span>
        <span>${memoFmtMoney(p.currentPrice)}</span>
        <span>${memoEsc(p.trend || "Unknown")}</span>
        <span class="${memoPctClass(s.ema20Pct)}">EMA20 ${memoPctLabel(s.ema20Pct)}</span>
      </button>`;
    }).join("") : `<div class="memo-picker-empty">No scanner results found. Search a ticker and choose “Use TICKER”.</div>`);
  }
  function memoActionsHtml(m){ return `<div class="memo-actions-cell">
    <button class="memo-mini-btn" data-memo-status="Done" data-memo-id="${m.id}">✅ Done</button><button class="memo-mini-btn" data-memo-status="Ignored" data-memo-id="${m.id}">❌ Ignore</button><button class="memo-mini-btn" data-memo-status="Watchlist" data-memo-id="${m.id}">👀 Watch</button><button class="memo-mini-btn" data-memo-edit="${m.id}">Edit</button><button class="memo-mini-btn" data-memo-refresh-one="${m.id}">Refresh</button><button class="memo-mini-btn" data-memo-delete="${m.id}">Delete</button>
  </div>`; }

  function openMemoModal(id=null, prefill=null){
    memoState.editingId = id;
    closeMemoActionSheet();
    closeMemoPicker();
    const modal = document.getElementById("memoModal"), form = document.getElementById("memoForm"), title = document.getElementById("memoModalTitle");
    if(!modal || !form) return;
    form.reset();
    const preview = document.getElementById("memoPrefillPreview");
    if (preview) { preview.hidden = true; preview.innerHTML = ""; }
    if(title) title.textContent = id ? "Edit Memo" : (prefill?.ticker ? `Add Memo · ${memoTicker(prefill.ticker)}` : "Add Memo");
    const m = memoState.memos.find(x => x.id === id);
    if(m){
      Object.keys(m).forEach(k => { if(form.elements[k]) form.elements[k].value = m[k] ?? ""; });
      applyMemoPrefill(form, { ticker:m.ticker, currentPrice:m.currentPrice, notePrice:m.notePrice, trend:m.trend, emaStatus:m.emaStatus, emaDistance:m.emaDistance });
    } else if (prefill) {
      applyMemoPrefill(form, prefill);
    }
    modal.hidden = false;
    setTimeout(()=>{
      const first = prefill?.ticker ? (form.elements.reason || form.elements.targetPrice) : form.elements.ticker;
      first?.focus();
    }, 80);
  }
  function closeMemoModal(){ const modal=document.getElementById("memoModal"); if(modal) modal.hidden = true; memoState.editingId = null; }
  async function saveMemoFromForm(){
    const form = document.getElementById("memoForm"); if(!form) return;
    const fd = new FormData(form);
    const ticker = memoTicker(fd.get("ticker"));
    if(!ticker){ form.elements.ticker?.focus(); return; }
    const prefillPrice = memoToNum(fd.get("prefillCurrentPrice")) ?? memoToNum(fd.get("prefillNotePrice"));
    const prefillNotePrice = memoToNum(fd.get("prefillNotePrice")) ?? prefillPrice;
    let priceInfo = { price: prefillPrice, trend: String(fd.get("prefillTrend") || "Unknown") };
    try {
      const live = await fetchMemoPrice(ticker);
      priceInfo = {
        ...live,
        price: memoToNum(live.price) ?? prefillPrice,
        trend: live.trend && live.trend !== "Unknown" ? live.trend : (String(fd.get("prefillTrend") || "Unknown"))
      };
    } catch (_) {}
    const existing = memoState.memos.find(x => x.id === memoState.editingId);
    const base = existing || { id: uid(), createdAt: memoNow(), notePrice: prefillNotePrice ?? priceInfo.price };
    const next = enrichMemo({
      ...base,
      ticker,
      reason: String(fd.get("reason")||"").trim(),
      sourceLink: String(fd.get("sourceLink")||"").trim(),
      targetPrice: memoToNum(fd.get("targetPrice")),
      targetDirection: fd.get("targetDirection") || "lte",
      conviction: fd.get("conviction") || "Medium",
      memoPhase: fd.get("memoPhase") || existing?.memoPhase || suggestedMemoPhase({ ticker, status: existing?.status, trend: priceInfo.trend }),
      actionPlan: fd.get("actionPlan") || "Hold off",
      customActionPlan: String(fd.get("customActionPlan")||"").trim(),
      category: fd.get("category") || "Other",
      alertType: fd.get("alertType") || "priceTarget",
      alertEmaLine: fd.get("alertEmaLine") || "EMA20",
      alertDistancePct: memoToNum(fd.get("alertDistancePct")) ?? 2,
      currentPrice: priceInfo.price ?? prefillPrice,
      trend: priceInfo.trend || "Unknown",
      emaStatus: String(fd.get("prefillEmaStatus") || existing?.emaStatus || ""),
      emaDistance: String(fd.get("prefillEmaDistance") || existing?.emaDistance || ""),
      updatedAt: memoNow(),
      status: existing?.status || "Watchlist"
    });
    if(!existing) next.notePrice = prefillNotePrice ?? priceInfo.price;
    if(next.status !== "Done" && next.status !== "Ignored" && isMemoAlertReached(next)) next.status = "Alert";
    if(existing){ memoState.memos = memoState.memos.map(x => x.id === existing.id ? next : x); }
    else { memoState.memos.unshift(next); }
    memoState.filters = { search:"", status:"All", trend:"All", conviction:"All", category:"All", actionPlan:"All", sort:"Newest first" };
    saveMemoFilters();
    saveMemos(); maybeNotify(next); closeMemoModal(); setAppView("memo"); renderMemo();
    showMemoToast("Memo saved", `${next.ticker} added to Stock Memo`);
  }

  function bindMemoEvents(){
    document.addEventListener("click", async (e)=>{
      const openTicker = e.target.closest("[data-memo-open-ticker]");
      if(openTicker){
        e.preventDefault();
        const ticker = memoTicker(openTicker.dataset.memoOpenTicker);
        if(ticker){
          state.selected = ticker;
          state.scannerTab = "technical";
          state.detailTab = "technical";
          setAppView("scanner");
          saveSettings?.();
          renderAll?.();
          ensureSymbolDetail?.(ticker, false);
          if (window.matchMedia("(max-width: 767px)").matches) {
            openMobileDetail?.();
          } else {
            document.getElementById("detailPanel")?.scrollIntoView({ behavior:"smooth", block:"start" });
          }
        }
        return;
      }
      const app = e.target.closest("[data-app-view]"); if(app){ e.preventDefault(); setAppView(app.dataset.appView); return; }
      if(e.target.closest("[data-memo-fab]")){ e.preventDefault(); openMemoActionSheet(); return; }
      if(e.target.closest("[data-memo-action-close]")){ e.preventDefault(); closeMemoActionSheet(); return; }
      if(e.target.closest("[data-memo-action-add]")){ e.preventDefault(); openMemoModal(); return; }
      if(e.target.closest("[data-memo-action-picker], [data-memo-add-from-screener]")){ e.preventDefault(); openMemoPicker(); return; }
      if(e.target.closest("[data-memo-action-current], [data-memo-import-current]")){ e.preventDefault(); openMemoModal(null, currentSelectedPrefill()); return; }
      if(e.target.closest("[data-memo-picker-cancel]")){ e.preventDefault(); closeMemoPicker(); return; }
      const manualPick = e.target.closest("[data-memo-pick-manual]");
      if(manualPick){ e.preventDefault(); openMemoModal(null, { ticker: manualPick.dataset.memoPickManual, trend:"Unknown" }); return; }
      const stockPick = e.target.closest("[data-memo-pick-stock]");
      if(stockPick){
        e.preventDefault();
        const t = memoTicker(stockPick.dataset.memoPickStock);
        const s = memoStockList().find(x => memoTicker(x.ticker || x.symbol) === t) || { ticker:t };
        openMemoModal(null, stockToMemoPrefill(s));
        return;
      }
      const viewBtn = e.target.closest("[data-memo-view]");
      if(viewBtn){ e.preventDefault(); localStorage.setItem(MEMO_STORAGE.mobileView, viewBtn.dataset.memoView || "cards"); renderMemo(); return; }
      if(e.target.closest("[data-memo-add]")){ e.preventDefault(); openMemoModal(); return; }
      if(e.target.closest("[data-memo-refresh]")){ e.preventDefault(); await refreshAllMemos(); return; }
      if(e.target.closest("[data-memo-cancel]")){ e.preventDefault(); closeMemoModal(); return; }
      const status = e.target.closest("[data-memo-status]"); if(status){ const m=memoState.memos.find(x=>x.id===status.dataset.memoId); if(m){ m.status = status.dataset.memoStatus; saveMemos(); renderMemo(); } return; }
      const edit = e.target.closest("[data-memo-edit]"); if(edit){ openMemoModal(edit.dataset.memoEdit); return; }
      const del = e.target.closest("[data-memo-delete]"); if(del){ if(confirm("Delete this memo?")){ memoState.memos = memoState.memos.filter(x=>x.id!==del.dataset.memoDelete); saveMemos(); renderMemo(); } return; }
      const ref = e.target.closest("[data-memo-refresh-one]"); if(ref){ const m=memoState.memos.find(x=>x.id===ref.dataset.memoRefreshOne); if(m) await refreshMemo(m); return; }
    }, true);
    document.addEventListener("input", (e)=>{
      const pickerSearch = e.target.closest("[data-memo-picker-search]");
      if (pickerSearch) { renderMemoPicker(pickerSearch.value); return; }
      const f = e.target.closest("[data-memo-filter]"); if(!f) return;
      memoState.filters[f.dataset.memoFilter] = f.value; saveMemoFilters(); renderMemo();
    });
    document.addEventListener("change", (e)=>{
      const f = e.target.closest("[data-memo-filter]"); if(!f) return;
      memoState.filters[f.dataset.memoFilter] = f.value; saveMemoFilters(); renderMemo();
    });
    document.addEventListener("submit", async (e)=>{ if(e.target && e.target.id === "memoForm"){ e.preventDefault(); await saveMemoFromForm(); } });
    document.addEventListener("keydown", (e)=>{ if(e.key === "Escape" && !document.getElementById("memoModal")?.hidden) closeMemoModal(); });
  }

  function seedExampleIfEmpty(){
    if(memoState.memos.length) return;
    const examples = [
      { ticker:"NVDA", reason:"AI leader; watch for pullback near key EMA support before adding.", targetPrice:210, targetDirection:"lte", conviction:"High", actionPlan:"Buy on pullback", category:"Technical setup", currentPrice:null, notePrice:null, trend:"Unknown" },
      { ticker:"HOOD", reason:"Retail trading recovery idea; recheck if price breaks above trend with volume.", targetPrice:85, targetDirection:"gte", conviction:"Medium", actionPlan:"Buy breakout", category:"Breakout", currentPrice:null, notePrice:null, trend:"Unknown" }
    ];
    memoState.memos = examples.map(x => enrichMemo({ id:uid(), createdAt:memoNow(), status:"Watchlist", sourceLink:"", ...x }));
    saveMemos();
  }

  try {
    const dismissed = JSON.parse(localStorage.getItem("stockTimingRadar.alertDismissed.v62") || "[]");
    if (Array.isArray(dismissed)) {
      const cleaned = dismissed.filter(id => !String(id).startsWith("memo-"));
      if (cleaned.length !== dismissed.length) localStorage.setItem("stockTimingRadar.alertDismissed.v62", JSON.stringify(cleaned));
      if (state && state.dismissedAlerts instanceof Set) state.dismissedAlerts = new Set(cleaned);
    }
  } catch (_) {}
  buildAppNav(); buildMemoPage(); bindMemoEvents();
  const savedView = localStorage.getItem(MEMO_STORAGE.view) || "scanner";
  setAppView(savedView === "memo" ? "memo" : "scanner");
})();


/* v5.6 mobile interaction + memo ticker hotfix */
(function v56InteractionFix(){
  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function safeCall(fn, ...args){ try { if (typeof fn === "function") return fn(...args); } catch (err) { console.error("v5.6 interaction error", err); } }
  function forceOpenSheet(id){
    const sheet = qs("#" + id);
    const backdrop = qs("#sheetBackdrop");
    if (!sheet) { console.warn("Sheet not found", id); return; }
    qsa(".bottom-sheet").forEach(s => { if (s !== sheet) { s.classList.remove("open"); s.setAttribute("aria-hidden", "true"); } });
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add("sheet-open");
    sheet.hidden = false;
    sheet.classList.add("open", "sheet-visible-force");
    sheet.setAttribute("aria-hidden", "false");
    sheet.style.transform = "translate3d(0, 0, 0)";
    sheet.style.opacity = "1";
    sheet.style.visibility = "visible";
    sheet.style.pointerEvents = "auto";
    const input = sheet.querySelector("textarea, input:not([type=checkbox]), button:not([data-close-sheet])");
    if (id === "bulkAddSheet" || id === "quickScanSheet") setTimeout(() => input?.focus(), 80);
  }
  function forceCloseSheets(){ safeCall(closeSheets); qsa(".bottom-sheet").forEach(s => { s.classList.remove("sheet-visible-force"); s.style.transform=""; }); }
  function applyFilterAndRender(source){
    safeCall(syncFiltersFromUi, source || "desktop");
    safeCall(saveSettings);
    safeCall(renderAll);
  }
  document.addEventListener("click", function(e){
    const close = e.target.closest?.("[data-close-sheet]");
    if (close) { e.preventDefault(); e.stopImmediatePropagation(); forceCloseSheets(); return; }
    const scanMobile = e.target.closest?.("#mobileScanNow");
    if (scanMobile) { e.preventDefault(); e.stopImmediatePropagation(); if (typeof openQuickScanSheet === "function") openQuickScanSheet(); else forceOpenSheet("quickScanSheet"); return; }
    const openPanel = e.target.closest?.("[data-open-panel]");
    if (openPanel) {
      e.preventDefault(); e.stopImmediatePropagation();
      const panel = openPanel.dataset.openPanel;
      forceOpenSheet(panel === "columns" ? "columnsSheet" : panel === "filters" ? "filtersSheet" : panel === "sort" ? "sortSheet" : "bulkAddSheet");
      return;
    }
    const th = e.target.closest?.("th[data-sort]");
    if (th) {
      e.preventDefault(); e.stopImmediatePropagation();
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortAsc = !state.sortAsc;
      else { state.sortKey = key; state.sortAsc = /Pct|Yoy|QoQ/i.test(key); }
      safeCall(saveSettings); safeCall(renderAll);
      return;
    }
    const pick = e.target.closest?.("[data-sort-pick]");
    if (pick) {
      e.preventDefault(); e.stopImmediatePropagation();
      state.sortKey = pick.dataset.sortPick;
      state.sortAsc = pick.dataset.sortDir !== "desc";
      safeCall(saveSettings); forceCloseSheets(); safeCall(renderAll);
      return;
    }
    const desktopScan = e.target.closest?.("#scanNowDesktop");
    if (desktopScan) { e.preventDefault(); e.stopImmediatePropagation(); applyFilterAndRender("desktop"); safeCall(scan, true); return; }
    const filterPrimary = e.target.closest?.("#filtersSheet .sheet-actions .primary-btn");
    if (filterPrimary) { e.preventDefault(); e.stopImmediatePropagation(); applyFilterAndRender("sheet"); forceCloseSheets(); safeCall(scan, true); return; }
    const filterReset = e.target.closest?.("#filtersSheet .sheet-actions .secondary-btn");
    if (filterReset) { e.preventDefault(); e.stopImmediatePropagation(); safeCall(resetFilters); return; }
    const scanCurrent = e.target.closest?.("[data-scan-current]");
    if (scanCurrent) { e.preventDefault(); e.stopImmediatePropagation(); forceCloseSheets(); safeCall(scan, true); return; }
    const temp = e.target.closest?.("[data-scan-temp]");
    if (temp) {
      e.preventDefault(); e.stopImmediatePropagation();
      const symbols = typeof parseTickerList === "function" ? parseTickerList(qs("#quickScanInput")?.value || "") : [];
      if (!symbols.length) { const s=qs("#quickScanSummary"); if(s) s.textContent="ใส่ ticker อย่างน้อย 1 ตัว"; return; }
      forceCloseSheets(); safeCall(scan, true, { symbols, message:`Scanning temporary list · ${symbols.length} symbols` }); return;
    }
    const append = e.target.closest?.("[data-append-scan]");
    if (append) { e.preventDefault(); e.stopImmediatePropagation(); const r=safeCall(addSymbolsBulk, qs("#quickScanInput")?.value||"", "append"); if(r?.total){ forceCloseSheets(); safeCall(scan,true); } return; }
    const repl = e.target.closest?.("[data-replace-scan]");
    if (repl) { e.preventDefault(); e.stopImmediatePropagation(); const r=safeCall(addSymbolsBulk, qs("#quickScanInput")?.value||"", "replace"); if(r?.total){ forceCloseSheets(); safeCall(scan,true); } return; }
  }, true);
  document.addEventListener("input", function(e){
    const el = e.target;
    if (!el) return;
    if (el.id === "scoreRange" || el.id === "sheetScoreRange") { state.filters.score = Number(el.value || 0); safeCall(applyFilterUi); safeCall(saveSettings); safeCall(renderAll); return; }
  }, true);
  document.addEventListener("change", function(e){
    const el = e.target;
    if (!el) return;
    const filterIds = new Set(["filterAbove200","filterEmaStack","filterSweetRsi","filterVolume20","filterMacdSignal","sheetFilterAbove200","sheetFilterEmaStack","sheetFilterSweetRsi","sheetFilterVolume20","sheetFilterMacdSignal"]);
    if (filterIds.has(el.id)) { e.stopImmediatePropagation(); applyFilterAndRender(el.id.startsWith("sheet") ? "sheet" : "desktop"); }
  }, true);
})();

/* v5.8 patch: portfolio tabs + screener action buttons must be real buttons. */
(function v58ScreenerInteractionPatch(){
  const BUILT_INS = new Set(["default", "momentum", "thai", "dividend", "quality"]);
  function markActiveScreener(key){
    try {
      document.querySelectorAll(".portfolio-tab[data-screener]").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.screener === key);
        btn.setAttribute("aria-selected", btn.dataset.screener === key ? "true" : "false");
      });
    } catch (_) {}
  }
  function refreshAfterScreenerAction(){
    try { renderPortfolioTabs(); } catch (_) {}
    try { renderAll(); } catch (_) {}
  }
  function switchScreenerNow(key){
    if (!key) return;
    try { state.activeScreener = key; } catch (_) {}
    markActiveScreener(key);
    try {
      loadScreener(key);
      return;
    } catch (err) {
      console.error("Screener switch failed", err);
    }
    // Fallback path if loadScreener is interrupted by a stale handler.
    try {
      const defaults = {
        default: BASE_WATCHLIST,
        momentum: ["NVDA", "AMD", "AVGO", "TSLA", "PLTR", "APP", "CRWD", "DDOG", "HOOD", "COIN"],
        thai: ["PTT.BK", "CPALL.BK", "AOT.BK", "ADVANC.BK", "KBANK.BK", "BDMS.BK", "DELTA.BK", "GULF.BK", "TRUE.BK", "PTTEP.BK"],
        dividend: ["JEPQ", "QQQI", "KO", "PEP", "CVX", "ABBV", "WMT", "COST", "BAC", "AXP"],
        quality: ["MSFT", "COST", "ASML", "LIN", "ISRG", "BKNG", "ADP", "ORLY", "INTU", "VRSK"],
      };
      const saved = getScreeners()[key] || {};
      state.watchlist = normalizeTickers(saved.watchlist || defaults[key] || state.watchlist || BASE_WATCHLIST);
      if (saved.filters) state.filters = { ...state.filters, ...saved.filters };
      if (saved.columns) state.columns = { ...state.columns, ...saved.columns };
      if (saved.scannerTab) state.scannerTab = saved.scannerTab;
      if (saved.mobileView) state.mobileView = saved.mobileView;
      if (saved.sortKey) state.sortKey = saved.sortKey;
      if (typeof saved.sortAsc === "boolean") state.sortAsc = saved.sortAsc;
      state.selected = state.watchlist[0] || state.selected || "NVDA";
      saveWatchlist();
      saveSettings();
      applyFilterUi();
      refreshAfterScreenerAction();
      scan(false);
    } catch (fallbackErr) {
      console.error("Fallback screener switch failed", fallbackErr);
      alert("เปลี่ยน watchlist ไม่สำเร็จ: " + (fallbackErr?.message || fallbackErr));
    }
  }
  function renameNow(){
    try {
      renameActiveScreener();
      refreshAfterScreenerAction();
    } catch (err) {
      console.error("Rename screener failed", err);
      alert("Rename ไม่สำเร็จ: " + (err?.message || err));
    }
  }
  function deleteNow(){
    try {
      deleteActiveScreener();
      refreshAfterScreenerAction();
    } catch (err) {
      console.error("Delete screener failed", err);
      alert("Delete ไม่สำเร็จ: " + (err?.message || err));
    }
  }
  function importNow(){
    try {
      importScreeners();
      refreshAfterScreenerAction();
    } catch (err) {
      console.error("Import screener failed", err);
      alert("Import ไม่สำเร็จ: " + (err?.message || err));
    }
  }
  function newNow(){
    try {
      newScreener();
      refreshAfterScreenerAction();
    } catch (err) {
      console.error("New screener failed", err);
      alert("สร้าง screener ไม่สำเร็จ: " + (err?.message || err));
    }
  }
  document.addEventListener("click", function(e){
    const tab = e.target.closest?.(".portfolio-tabs .portfolio-tab[data-screener]");
    if (tab && !tab.classList.contains("add-tab") && !tab.classList.contains("more-tab")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      switchScreenerNow(tab.dataset.screener || "default");
      return;
    }
    if (e.target.closest?.("#newScreenerBtn, .portfolio-tabs .add-tab")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      newNow();
      return;
    }
    if (e.target.closest?.("[data-rename-screener]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      renameNow();
      return;
    }
    if (e.target.closest?.("[data-delete-screener]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      deleteNow();
      return;
    }
    if (e.target.closest?.("[data-import-screeners]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      importNow();
      return;
    }
  }, true);
  // Give custom tabs an explicit accessible role after every render.
  try {
    document.querySelectorAll(".portfolio-tab[data-screener]").forEach(btn => {
      btn.setAttribute("type", "button");
      btn.setAttribute("role", "tab");
    });
  } catch (_) {}
})();


/* v6.8 mobile fixes
   - Prevent mobile portfolio tab taps/swipes from being interpreted as long-press delete.
   - Keep + New screener as a create action only on mobile.
   - Separate memo create FAB from alert bell FAB so they never overlap.
*/
(function v68MobileScreenerAndFabFix(){
  const isMobile = () => window.matchMedia && window.matchMedia('(max-width: 767px)').matches;

  // The older desktop long-press-to-delete handler listens on body pointerdown.
  // On iOS/Safari, horizontal tab taps/swipes can accidentally keep that timer alive,
  // so stop portfolio pointer events during the capture phase on mobile only.
  document.addEventListener('pointerdown', function(e){
    if (!isMobile()) return;
    const tab = e.target && e.target.closest && e.target.closest('.portfolio-tabs .portfolio-tab');
    if (!tab) return;
    e.stopPropagation();
  }, true);

  document.addEventListener('dblclick', function(e){
    if (!isMobile()) return;
    if (e.target && e.target.closest && e.target.closest('.portfolio-tabs .portfolio-tab')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  document.addEventListener('contextmenu', function(e){
    if (!isMobile()) return;
    if (e.target && e.target.closest && e.target.closest('.portfolio-tabs .portfolio-tab')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  // Belt-and-suspenders: on mobile, + New must never route to delete/rename.
  document.addEventListener('click', function(e){
    if (!isMobile()) return;
    const add = e.target && e.target.closest && e.target.closest('#newScreenerBtn, .portfolio-tabs .add-tab');
    if (!add) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    try { newScreener(); }
    catch (err) {
      console.error('Create screener failed', err);
      alert('สร้าง screener ไม่สำเร็จ: ' + (err && err.message ? err.message : err));
    }
  }, true);
})();

/* v6.9 mobile screener creation + fundamental deploy robustness
   - Mobile + New uses explicit bottom sheet instead of prompt/long-press paths.
   - Save current state as a new screener from mobile/desktop.
   - Screener settings sheet owns rename/delete/import/export on mobile.
   - Custom screener labels persist and all custom tabs render horizontally.
*/
(function v69MobileScreenerCreationFix(){
  const BUILT_INS = new Set(["default", "momentum", "thai", "dividend", "quality"]);
  const builtInTabs = [
    ["default", "⭐ Default"], ["momentum", "🚀 Momentum"], ["thai", "🇹🇭 Thai"], ["dividend", "🏦 Dividend"], ["quality", "🧱 High Quality"],
  ];
  const isMobile = () => window.matchMedia && window.matchMedia("(max-width: 767px)").matches;
  const slugify = (name) => String(name || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9ก-๙]+/gi, "-")
    .replace(/^-|-$/g, "") || `screener-${Date.now()}`;
  const labelFor = (key, saved = null) => {
    const builtin = builtInTabs.find(([k]) => k === key);
    if (builtin) return builtin[1];
    const rec = saved || getScreeners()[key] || {};
    return rec.label || rec.name || `⭐ ${key.replace(/-/g, " ")}`;
  };
  const snapshot = (label) => ({
    label,
    watchlist: Array.isArray(state.watchlist) ? [...state.watchlist] : [],
    filters: { ...state.filters },
    columns: { ...state.columns },
    scannerTab: state.scannerTab,
    mobileView: state.mobileView,
    sortKey: state.sortKey,
    sortAsc: state.sortAsc,
    savedAt: new Date().toISOString(),
  });
  const oldPersist = persistActiveScreener;
  persistActiveScreener = function patchedPersistActiveScreener(){
    const screeners = getScreeners();
    const existing = screeners[state.activeScreener] || {};
    screeners[state.activeScreener] = {
      ...existing,
      ...snapshot(existing.label || existing.name || labelFor(state.activeScreener, existing)),
    };
    setScreeners(screeners);
  };
  renderPortfolioTabs = function patchedRenderPortfolioTabs(){
    const nav = document.querySelector(".portfolio-tabs");
    if (!nav) return;
    const saved = getScreeners();
    const custom = Object.keys(saved)
      .filter(k => !BUILT_INS.has(k))
      .sort((a, b) => String(saved[a]?.savedAt || "").localeCompare(String(saved[b]?.savedAt || "")) || a.localeCompare(b))
      .map(k => [k, labelFor(k, saved[k])]);
    const tabs = [...builtInTabs, ...custom];
    nav.innerHTML = tabs.map(([key, label]) => `<button type="button" role="tab" class="portfolio-tab ${key === state.activeScreener ? "active" : ""}" data-screener="${esc(key)}">${esc(label)}</button>`).join("") + `
      <button type="button" class="portfolio-tab more-tab" data-open-screener-settings>⚙</button>
      <button type="button" class="portfolio-tab add-tab" id="newScreenerBtn" data-save-as-screener>+ New</button>`;
    updateScreenerSettingsLabel();
  };
  function updateScreenerSettingsLabel(){
    const el = document.getElementById("activeScreenerLabel");
    if (el) el.textContent = `Active screener: ${labelFor(state.activeScreener)}`;
  }
  function showSaveSheet(defaultName = ""){
    const input = document.getElementById("saveScreenerName");
    const status = document.getElementById("saveScreenerStatus");
    if (input) input.value = defaultName;
    if (status) status.textContent = "";
    try { openSheet("saveScreenerSheet"); } catch (_) {}
    setTimeout(() => input?.focus(), 120);
  }
  function saveAsNewScreener(){
    const input = document.getElementById("saveScreenerName");
    const clone = document.getElementById("saveScreenerClone")?.checked !== false;
    const rawName = input?.value?.trim() || "My Screener";
    const keyBase = slugify(rawName);
    const screeners = getScreeners();
    let key = keyBase;
    let i = 2;
    while (screeners[key] || BUILT_INS.has(key)) key = `${keyBase}-${i++}`;
    screeners[key] = clone ? snapshot(rawName) : { ...snapshot(rawName), watchlist: [] };
    setScreeners(screeners);
    state.activeScreener = key;
    if (!clone) state.watchlist = [];
    saveSettings();
    try { closeSheets(); } catch (_) {}
    renderAll();
    // Do not force a heavy scan on GitHub Pages; static data reloads when Scan is tapped.
    const nav = document.querySelector(".portfolio-tabs");
    const btn = nav?.querySelector(`[data-screener="${CSS.escape(key)}"]`);
    btn?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    setLoading(false, `Saved screener: ${rawName}`);
  }
  newScreener = function patchedNewScreener(){
    if (isMobile()) { showSaveSheet("My Screener"); return; }
    const name = prompt("ตั้งชื่อ screener ใหม่", "My Screener");
    if (!name) return;
    const input = document.getElementById("saveScreenerName");
    if (input) input.value = name;
    saveAsNewScreener();
  };
  const oldRename = renameActiveScreener;
  renameActiveScreener = function patchedRenameActiveScreener(){
    const current = state.activeScreener;
    const currentLabel = labelFor(current).replace(/^⭐\s*/, "");
    const name = prompt("Rename screener", currentLabel);
    if (!name) return;
    const newKeyBase = slugify(name);
    const screeners = getScreeners();
    let newKey = BUILT_INS.has(current) ? `${newKeyBase}-${Date.now()}` : newKeyBase;
    let i = 2;
    while (newKey !== current && (screeners[newKey] || BUILT_INS.has(newKey))) newKey = `${newKeyBase}-${i++}`;
    const existing = screeners[current] || snapshot(currentLabel);
    screeners[newKey] = { ...existing, label: name, name, savedAt: new Date().toISOString() };
    if (newKey !== current && !BUILT_INS.has(current)) delete screeners[current];
    setScreeners(screeners);
    state.activeScreener = newKey;
    saveSettings();
    renderAll();
  };
  document.addEventListener("click", function(e){
    const target = e.target;
    if (!target || !target.closest) return;
    if (target.closest("[data-save-as-screener]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      showSaveSheet("");
      return;
    }
    if (target.closest("[data-confirm-save-screener]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      saveAsNewScreener();
      return;
    }
    if (target.closest("[data-open-screener-settings]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      updateScreenerSettingsLabel();
      try { openSheet("screenerSettingsSheet"); } catch (_) {}
      return;
    }
  }, true);
  // Mobile: disable accidental long-press-to-delete completely.
  document.addEventListener("pointerdown", function(e){
    if (!isMobile()) return;
    if (e.target?.closest?.(".portfolio-tabs")) e.stopImmediatePropagation();
  }, true);
  // Initial repaint with patched renderer.
  setTimeout(() => { try { renderPortfolioTabs(); updateTabs(); } catch (_) {} }, 0);
})();

/* v7.0: hard fix mobile screener creation/render
   Root cause: older mobile handlers use data-save-as-screener / data-confirm-save-screener
   and can intercept + New before the tab renderer refreshes. This patch uses unique v70
   attributes, renders from the single localStorage screeners state, and puts the active
   custom screener first on mobile so newly-created tabs are immediately visible.
*/
(function v70HardFixMobileScreenerRender(){
  const BUILT_INS = new Set(["default", "momentum", "thai", "dividend", "quality"]);
  const BUILTIN_TABS = [
    ["default", "⭐ Default"],
    ["momentum", "🚀 Momentum"],
    ["thai", "🇹🇭 Thai"],
    ["dividend", "🏦 Dividend"],
    ["quality", "🧱 High Quality"],
  ];
  const isMobile = () => window.matchMedia && window.matchMedia("(max-width: 767px)").matches;
  const normalizeName = (name) => String(name || "").trim();
  const slugifyV70 = (name) => normalizeName(name)
    .toLowerCase()
    .replace(/[^a-z0-9ก-๙]+/gi, "-")
    .replace(/^-|-$/g, "") || `screener-${Date.now()}`;
  const getAllScreenersV70 = () => {
    try { return JSON.parse(localStorage.getItem(STORAGE.screeners) || "{}"); }
    catch (_) { return {}; }
  };
  const setAllScreenersV70 = (screeners) => localStorage.setItem(STORAGE.screeners, JSON.stringify(screeners || {}));
  const labelForV70 = (key, screeners = getAllScreenersV70()) => {
    const builtIn = BUILTIN_TABS.find(([k]) => k === key);
    if (builtIn) return builtIn[1];
    const rec = screeners[key] || {};
    return rec.label || rec.name || `⭐ ${String(key).replace(/-/g, " ")}`;
  };
  const snapshotV70 = (label) => ({
    label,
    name: label,
    watchlist: Array.isArray(state.watchlist) ? [...state.watchlist] : [],
    filters: { ...state.filters },
    columns: { ...state.columns },
    scannerTab: state.scannerTab,
    mobileView: state.mobileView,
    sortKey: state.sortKey,
    sortAsc: state.sortAsc,
    savedAt: new Date().toISOString(),
  });

  function ensureV70Sheet(){
    if (document.getElementById("saveScreenerSheetV70")) return;
    const sheet = document.createElement("section");
    sheet.className = "bottom-sheet save-screener-v70";
    sheet.id = "saveScreenerSheetV70";
    sheet.setAttribute("aria-hidden", "true");
    sheet.setAttribute("aria-label", "Save as new screener");
    sheet.innerHTML = `
      <div class="sheet-grip"></div>
      <div class="sheet-header"><h2>＋ Save as New Screener</h2><button class="icon-btn" data-v70-close-sheet>×</button></div>
      <div class="sheet-body screener-sheet-body">
        <p class="helper-text">บันทึก watchlist, filters, columns และมุมมองปัจจุบันเป็น screener ใหม่</p>
        <label class="form-field"><span>Screener name</span><input id="saveScreenerNameV70" type="text" placeholder="เช่น AI Leaders / Thai Momentum" autocomplete="off" /></label>
        <label class="toggle-row"><span>Clone current watchlist + settings</span><input id="saveScreenerCloneV70" type="checkbox" checked /></label>
        <p id="saveScreenerStatusV70" class="bulk-import-summary" aria-live="polite"></p>
      </div>
      <div class="sheet-actions"><button class="secondary-btn" data-v70-close-sheet>Cancel</button><button class="primary-btn" data-v70-confirm-save-screener>Save Screener</button></div>`;
    document.body.appendChild(sheet);
  }

  function closeV70Sheets(){
    document.querySelectorAll(".bottom-sheet").forEach(s => {
      s.classList.remove("open");
      s.setAttribute("aria-hidden", "true");
    });
    const backdrop = document.getElementById("sheetBackdrop");
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove("sheet-open");
  }

  function openV70SaveSheet(defaultName = ""){
    ensureV70Sheet();
    const input = document.getElementById("saveScreenerNameV70");
    const status = document.getElementById("saveScreenerStatusV70");
    if (input) input.value = defaultName;
    if (status) status.textContent = "";
    document.querySelectorAll(".bottom-sheet").forEach(s => {
      s.classList.remove("open");
      s.setAttribute("aria-hidden", "true");
    });
    const sheet = document.getElementById("saveScreenerSheetV70");
    const backdrop = document.getElementById("sheetBackdrop");
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add("sheet-open");
    sheet?.classList.add("open");
    sheet?.setAttribute("aria-hidden", "false");
    setTimeout(() => input?.focus(), 140);
  }

  function createScreenerV70(){
    ensureV70Sheet();
    const input = document.getElementById("saveScreenerNameV70");
    const clone = document.getElementById("saveScreenerCloneV70")?.checked !== false;
    const rawName = normalizeName(input?.value || "") || `Screener ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}`;
    const screeners = getAllScreenersV70();
    const base = slugifyV70(rawName);
    let key = base;
    let idx = 2;
    while (BUILT_INS.has(key) || screeners[key]) key = `${base}-${idx++}`;
    screeners[key] = clone ? snapshotV70(rawName) : { ...snapshotV70(rawName), watchlist: [] };
    setAllScreenersV70(screeners);

    state.activeScreener = key;
    if (!clone) state.watchlist = [];
    state.selected = state.watchlist[0] || state.selected || "NVDA";
    saveSettings();
    closeV70Sheets();
    renderPortfolioTabs();
    updateTabs();
    renderAll();
    setTimeout(() => {
      const btn = document.querySelector(`.portfolio-tabs [data-screener="${CSS.escape(key)}"]`);
      btn?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
      btn?.classList.add("active");
    }, 40);
    if (typeof setLoading === "function") setLoading(false, `Saved screener: ${rawName}`);
  }

  function switchScreenerV70(key){
    if (!key) return;
    try {
      loadScreener(key);
    } catch (err) {
      console.warn("loadScreener failed; using fallback", err);
      const screeners = getAllScreenersV70();
      const rec = screeners[key];
      const defaults = {
        default: BASE_WATCHLIST,
        momentum: ["NVDA", "AMD", "AVGO", "TSLA", "PLTR", "APP", "CRWD", "DDOG", "HOOD", "COIN"],
        thai: ["PTT.BK", "CPALL.BK", "AOT.BK", "ADVANC.BK", "KBANK.BK", "BDMS.BK", "DELTA.BK", "GULF.BK", "TRUE.BK", "PTTEP.BK"],
        dividend: ["JEPQ", "QQQI", "KO", "PEP", "CVX", "ABBV", "WMT", "COST", "BAC", "AXP"],
        quality: ["MSFT", "COST", "ASML", "LIN", "ISRG", "BKNG", "ADP", "ORLY", "INTU", "VRSK"],
      };
      state.activeScreener = key;
      state.watchlist = normalizeTickers(rec?.watchlist || defaults[key] || state.watchlist || []);
      if (rec?.filters) state.filters = { ...state.filters, ...rec.filters };
      if (rec?.columns) state.columns = { ...state.columns, ...rec.columns };
      if (rec?.scannerTab) state.scannerTab = rec.scannerTab;
      if (rec?.mobileView) state.mobileView = rec.mobileView;
      state.selected = state.watchlist[0] || state.selected || "NVDA";
      saveSettings();
      renderAll();
    }
  }

  // Override renderer completely. On mobile, put active custom first so it is visible immediately.
  renderPortfolioTabs = function renderPortfolioTabsV70(){
    const nav = document.querySelector(".portfolio-tabs");
    if (!nav) return;
    const screeners = getAllScreenersV70();
    let custom = Object.keys(screeners)
      .filter(k => !BUILT_INS.has(k))
      .sort((a, b) => String(screeners[b]?.savedAt || "").localeCompare(String(screeners[a]?.savedAt || "")) || a.localeCompare(b))
      .map(k => [k, labelForV70(k, screeners)]);
    if (isMobile() && !BUILT_INS.has(state.activeScreener)) {
      const active = custom.find(([k]) => k === state.activeScreener);
      custom = [...(active ? [active] : []), ...custom.filter(([k]) => k !== state.activeScreener)];
    }
    const tabs = [...BUILTIN_TABS, ...custom];
    nav.innerHTML = tabs.map(([key, label]) => `<button type="button" role="tab" class="portfolio-tab ${key === state.activeScreener ? "active" : ""}" data-screener="${esc(key)}" aria-selected="${key === state.activeScreener ? "true" : "false"}">${esc(label)}</button>`).join("") + `
      <button type="button" class="portfolio-tab screener-settings-tab" data-v70-open-screener-settings>⚙</button>
      <button type="button" class="portfolio-tab add-tab" id="newScreenerBtn" data-v70-save-screener>+ New</button>`;
  };

  // Remove old data attributes that trigger earlier v6.x handlers, then add v70 attributes.
  function patchExistingButtons(){
    document.querySelectorAll("[data-save-as-screener]").forEach(btn => {
      btn.removeAttribute("data-save-as-screener");
      btn.setAttribute("data-v70-save-screener", "");
    });
    document.querySelectorAll("[data-confirm-save-screener]").forEach(btn => {
      btn.removeAttribute("data-confirm-save-screener");
      btn.setAttribute("data-v70-confirm-save-screener", "");
    });
    document.querySelectorAll("[data-open-screener-settings]").forEach(btn => {
      btn.removeAttribute("data-open-screener-settings");
      btn.setAttribute("data-v70-open-screener-settings", "");
    });
  }

  // Explicit capture handler with unique v70 attributes.
  document.addEventListener("click", function(e){
    const target = e.target;
    if (!target || !target.closest) return;
    const saveBtn = target.closest("[data-v70-save-screener], #newScreenerBtn.add-tab");
    if (saveBtn) {
      e.preventDefault();
      e.stopImmediatePropagation();
      openV70SaveSheet("");
      return;
    }
    if (target.closest("[data-v70-confirm-save-screener]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      createScreenerV70();
      return;
    }
    if (target.closest("[data-v70-close-sheet]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      closeV70Sheets();
      return;
    }
    const tab = target.closest(".portfolio-tabs .portfolio-tab[data-screener]");
    if (tab) {
      e.preventDefault();
      e.stopImmediatePropagation();
      switchScreenerV70(tab.dataset.screener);
      return;
    }
  }, true);

  // Do not block pointer/click propagation inside portfolio tabs; old mobile long-press guard was too aggressive.
  document.addEventListener("pointerdown", function(e){
    if (!isMobile()) return;
    if (e.target?.closest?.(".portfolio-tabs .portfolio-tab")) {
      // Let the later click handler above handle it; just prevent text selection/long touch menu.
      e.target.closest(".portfolio-tab")?.classList.add("touching");
      setTimeout(() => e.target.closest?.(".portfolio-tab")?.classList.remove("touching"), 220);
    }
  }, true);

  // Public debug helper for console testing.
  window.__stockcheckCreateScreenerV70 = function(name = "Debug Screener"){
    ensureV70Sheet();
    document.getElementById("saveScreenerNameV70").value = name;
    document.getElementById("saveScreenerCloneV70").checked = true;
    createScreenerV70();
    return { active: state.activeScreener, screeners: getAllScreenersV70() };
  };

  document.addEventListener("DOMContentLoaded", () => {
    ensureV70Sheet();
    patchExistingButtons();
    renderPortfolioTabs();
    updateTabs();
  });
  setTimeout(() => { ensureV70Sheet(); patchExistingButtons(); renderPortfolioTabs(); updateTabs(); }, 0);
})();

/* v7.1 — Mobile fixed reserve screeners
   Mobile + New screener creation was unreliable on Safari due to legacy tab handlers.
   Instead, expose three permanent reserve portfolio slots after Thai: Port 1 / Port 2 / Port 3.
   They are normal screeners stored in localStorage and can be edited via Import/Replace/Append.
*/
(function v71MobileReserveScreeners(){
  const MOBILE_QUERY = "(max-width: 767px)";
  const reserveTabs = [
    ["default", "Default"],
    ["momentum", "Momentum"],
    ["thai", "Thai"],
    ["port1", "Port 1"],
    ["port2", "Port 2"],
    ["port3", "Port 3"],
  ];
  const defaultLists = {
    default: BASE_WATCHLIST,
    momentum: ["NVDA", "AMD", "AVGO", "TSLA", "PLTR", "APP", "CRWD", "DDOG", "HOOD", "COIN"],
    thai: ["PTT.BK", "CPALL.BK", "AOT.BK", "ADVANC.BK", "KBANK.BK", "BDMS.BK", "DELTA.BK", "GULF.BK", "TRUE.BK", "PTTEP.BK"],
    port1: [],
    port2: [],
    port3: [],
  };
  const escHtml = (x) => String(x ?? "").replace(/[&<>\"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const mobile = () => window.matchMedia(MOBILE_QUERY).matches;
  const getAll = () => {
    try { return JSON.parse(localStorage.getItem(STORAGE.screeners) || "{}"); }
    catch (_) { return {}; }
  };
  const setAll = (obj) => localStorage.setItem(STORAGE.screeners, JSON.stringify(obj || {}));
  function snapshot(label){
    return {
      label,
      name: label,
      watchlist: Array.isArray(state.watchlist) ? [...state.watchlist] : [],
      filters: { ...state.filters },
      columns: { ...state.columns },
      scannerTab: state.scannerTab,
      mobileView: state.mobileView,
      sortKey: state.sortKey,
      sortAsc: state.sortAsc,
      savedAt: new Date().toISOString(),
    };
  }
  function ensureReserveRecords(){
    const screeners = getAll();
    let changed = false;
    for (const [key, label] of reserveTabs) {
      if (!screeners[key]) {
        screeners[key] = {
          label,
          name: label,
          watchlist: defaultLists[key] || [],
          filters: { ...state.filters },
          columns: { ...state.columns },
          scannerTab: state.scannerTab || "technical",
          mobileView: state.mobileView || "cards",
          sortKey: state.sortKey || "score",
          sortAsc: !!state.sortAsc,
          savedAt: new Date().toISOString(),
          reserved: true,
        };
        changed = true;
      }
    }
    if (changed) setAll(screeners);
    return screeners;
  }
  function saveCurrentIntoActive(){
    try {
      const key = state.activeScreener || "default";
      const screeners = ensureReserveRecords();
      const existing = screeners[key] || {};
      const label = existing.label || existing.name || reserveTabs.find(([k]) => k === key)?.[1] || key;
      screeners[key] = { ...existing, ...snapshot(label), reserved: existing.reserved || ["default","momentum","thai","port1","port2","port3"].includes(key) };
      setAll(screeners);
    } catch (err) {
      console.warn("v7.1 save current screener failed", err);
    }
  }
  function renderMobileReserveTabs(){
    const nav = document.querySelector(".portfolio-tabs");
    if (!nav) return;
    ensureReserveRecords();
    nav.classList.add("portfolio-tabs-v71");
    const active = state.activeScreener || "default";
    nav.innerHTML = reserveTabs.map(([key, fallback]) => {
      const rec = getAll()[key] || {};
      const label = rec.label || rec.name || fallback;
      return `<button type="button" role="tab" class="portfolio-tab-v71 ${key === active ? "active" : ""}" data-v71-screener="${escHtml(key)}" aria-selected="${key === active ? "true" : "false"}">${escHtml(label)}</button>`;
    }).join("") + `<button type="button" class="portfolio-tab-v71 settings" data-v71-screener-settings aria-label="Screener settings">Settings</button>`;
    const activeBtn = nav.querySelector(`[data-v71-screener="${CSS.escape(active)}"]`);
    setTimeout(() => activeBtn?.scrollIntoView({ inline: "center", block: "nearest" }), 0);
  }
  const previousRenderPortfolioTabs = renderPortfolioTabs;
  renderPortfolioTabs = function renderPortfolioTabsV71(...args){
    if (mobile()) return renderMobileReserveTabs();
    return previousRenderPortfolioTabs.apply(this, args);
  };
  function switchToReserve(key){
    if (!key) return;
    saveCurrentIntoActive();
    const screeners = ensureReserveRecords();
    const rec = screeners[key] || {};
    state.activeScreener = key;
    state.watchlist = normalizeTickers(rec.watchlist || defaultLists[key] || []);
    state.filters = { ...state.filters, ...(rec.filters || {}) };
    state.columns = { ...state.columns, ...(rec.columns || {}) };
    state.scannerTab = rec.scannerTab || state.scannerTab || "technical";
    state.mobileView = rec.mobileView || state.mobileView || "cards";
    state.sortKey = rec.sortKey || state.sortKey || "score";
    state.sortAsc = !!rec.sortAsc;
    state.selected = state.watchlist[0] || state.selected || "NVDA";
    try { localStorage.setItem(STORAGE.activeScreener, key); } catch (_) {}
    try { saveSettings(); } catch (_) {}
    renderMobileReserveTabs();
    try { renderAll(); } catch (err) { console.warn("v7.1 render after reserve switch failed", err); }
  }
  document.addEventListener("click", function(e){
    if (!mobile()) return;
    const target = e.target;
    if (!target || !target.closest) return;
    const tab = target.closest("[data-v71-screener]");
    if (tab) {
      e.preventDefault();
      e.stopImmediatePropagation();
      switchToReserve(tab.getAttribute("data-v71-screener"));
      return;
    }
    if (target.closest("[data-v71-screener-settings]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      try {
        const el = document.getElementById("activeScreenerLabel");
        if (el) el.textContent = `Active screener: ${getAll()[state.activeScreener]?.label || state.activeScreener || "Default"}`;
        openSheet("screenerSettingsSheet");
      } catch (err) {
        alert(`Active screener: ${state.activeScreener || "default"}`);
      }
      return;
    }
  }, true);
  // Make Rename update the fixed Port label instead of creating a hidden custom tab on mobile.
  const previousRename = typeof renameActiveScreener === "function" ? renameActiveScreener : null;
  renameActiveScreener = function renameActiveScreenerV71(){
    if (!mobile()) return previousRename ? previousRename() : undefined;
    const key = state.activeScreener || "default";
    const screeners = ensureReserveRecords();
    const current = screeners[key]?.label || reserveTabs.find(([k]) => k === key)?.[1] || key;
    const name = prompt("Rename screener", current);
    if (!name) return;
    screeners[key] = { ...(screeners[key] || {}), label: name.trim(), name: name.trim(), savedAt: new Date().toISOString() };
    setAll(screeners);
    renderMobileReserveTabs();
    try { renderAll(); } catch (_) {}
  };
  // Delete on mobile clears the reserved slot instead of removing its tab.
  const previousDelete = typeof deleteActiveScreener === "function" ? deleteActiveScreener : null;
  deleteActiveScreener = function deleteActiveScreenerV71(){
    if (!mobile()) return previousDelete ? previousDelete() : undefined;
    const key = state.activeScreener || "default";
    const label = getAll()[key]?.label || reserveTabs.find(([k]) => k === key)?.[1] || key;
    if (!confirm(`Clear screener ${label}?`)) return;
    const screeners = ensureReserveRecords();
    screeners[key] = {
      label,
      name: label,
      watchlist: [],
      filters: { ...state.filters },
      columns: { ...state.columns },
      scannerTab: state.scannerTab || "technical",
      mobileView: state.mobileView || "cards",
      sortKey: state.sortKey || "score",
      sortAsc: !!state.sortAsc,
      savedAt: new Date().toISOString(),
      reserved: true,
    };
    setAll(screeners);
    state.watchlist = [];
    state.rows = [];
    state.quotes = {};
    try { saveSettings(); } catch (_) {}
    renderMobileReserveTabs();
    try { renderAll(); } catch (_) {}
  };
  window.__stockcheckRenderReserveTabsV71 = renderMobileReserveTabs;
  window.__stockcheckSwitchReserveV71 = switchToReserve;
  setTimeout(() => { if (mobile()) { ensureReserveRecords(); renderMobileReserveTabs(); } }, 0);
})();

/* v8.0 Stability & Data Integrity
   Release goal: stop adding new surface area; make existing scanner/memo/screener/data states resilient.
   - Mobile uses stable fixed screeners: Default / Momentum / Thai / Port 1 / Port 2 / Port 3 / Settings.
   - Portfolio rendering is idempotent and no longer depends on dynamic mobile tab creation.
   - Data integrity banner shows technical/fundamental freshness and missing-layer warnings.
   - Memo alerts remain persistent until user action; dismissed memo-alert ghosts are cleaned.
   - Exposes window.__stockcheckDiagnosticsV80() for quick support/debug checks.
*/
(function v80StabilityRelease(){
  const BUILD = "v8.0 Stability & Data Integrity";
  const MOBILE_QUERY = "(max-width: 767px)";
  const mobile = () => window.matchMedia && window.matchMedia(MOBILE_QUERY).matches;
  const fixedTabs = [
    ["default", "Default"],
    ["momentum", "Momentum"],
    ["thai", "Thai"],
    ["port1", "Port 1"],
    ["port2", "Port 2"],
    ["port3", "Port 3"],
  ];
  const fixedKeys = new Set(fixedTabs.map(([k]) => k));
  const defaultLists = {
    default: BASE_WATCHLIST,
    momentum: ["NVDA", "AMD", "AVGO", "TSLA", "PLTR", "APP", "CRWD", "DDOG", "HOOD", "COIN"],
    thai: ["PTT.BK", "CPALL.BK", "AOT.BK", "ADVANC.BK", "KBANK.BK", "BDMS.BK", "DELTA.BK", "GULF.BK", "TRUE.BK", "PTTEP.BK"],
    port1: [], port2: [], port3: [],
  };
  const safeHtml = (v) => String(v ?? "").replace(/[&<>\"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
  const getStore = () => { try { return JSON.parse(localStorage.getItem(STORAGE.screeners) || "{}"); } catch { return {}; } };
  const setStore = (x) => localStorage.setItem(STORAGE.screeners, JSON.stringify(x || {}));
  const snapshot = (label) => ({
    label,
    name: label,
    watchlist: normalizeTickers(Array.isArray(state.watchlist) ? state.watchlist : []),
    filters: { ...state.filters },
    columns: { ...state.columns },
    scannerTab: state.scannerTab || "technical",
    mobileView: state.mobileView || "cards",
    sortKey: state.sortKey || "score",
    sortAsc: !!state.sortAsc,
    savedAt: new Date().toISOString(),
    v8Stable: true,
  });
  function ensureFixedScreeners(){
    const screeners = getStore();
    let changed = false;
    fixedTabs.forEach(([key, label]) => {
      const existing = screeners[key] || {};
      if (!screeners[key] || !Array.isArray(existing.watchlist)) {
        screeners[key] = {
          label: existing.label || existing.name || label,
          name: existing.name || existing.label || label,
          watchlist: normalizeTickers(existing.watchlist || defaultLists[key] || []),
          filters: { ...state.filters, ...(existing.filters || {}) },
          columns: { ...state.columns, ...(existing.columns || {}) },
          scannerTab: existing.scannerTab || state.scannerTab || "technical",
          mobileView: existing.mobileView || state.mobileView || "cards",
          sortKey: existing.sortKey || state.sortKey || "score",
          sortAsc: !!existing.sortAsc,
          savedAt: existing.savedAt || new Date().toISOString(),
          reserved: true,
          v8Stable: true,
        };
        changed = true;
      } else if (!existing.reserved || !existing.v8Stable) {
        screeners[key] = { ...existing, reserved: true, v8Stable: true, label: existing.label || existing.name || label, name: existing.name || existing.label || label };
        changed = true;
      }
    });
    if (changed) setStore(screeners);
    return screeners;
  }
  function saveActiveFixedScreener(){
    try {
      const key = state.activeScreener || "default";
      const screeners = ensureFixedScreeners();
      const existing = screeners[key] || {};
      const label = existing.label || existing.name || fixedTabs.find(([k]) => k === key)?.[1] || key;
      screeners[key] = { ...existing, ...snapshot(label), reserved: fixedKeys.has(key) || existing.reserved };
      setStore(screeners);
      localStorage.setItem(STORAGE.activeScreener, key);
    } catch (err) { console.warn("v8 save screener failed", err); }
  }
  function renderMobileTabsV80(){
    const nav = document.querySelector(".portfolio-tabs");
    if (!nav) return;
    const screeners = ensureFixedScreeners();
    const active = state.activeScreener || "default";
    nav.classList.add("portfolio-tabs-v80");
    nav.classList.remove("portfolio-tabs-v71");
    nav.innerHTML = fixedTabs.map(([key, fallback]) => {
      const rec = screeners[key] || {};
      const label = rec.label || rec.name || fallback;
      return `<button type="button" role="tab" class="portfolio-tab-v80 ${key === active ? "active" : ""}" data-v80-screener="${safeHtml(key)}" aria-selected="${key === active ? "true" : "false"}">${safeHtml(label)}</button>`;
    }).join("") + `<button type="button" class="portfolio-tab-v80 settings" data-v80-screener-settings aria-label="Screener settings">Settings</button>`;
    setTimeout(() => nav.querySelector(`[data-v80-screener="${CSS.escape(active)}"]`)?.scrollIntoView({ inline:"center", block:"nearest" }), 0);
  }
  function switchMobileScreenerV80(key){
    if (!key) return;
    saveActiveFixedScreener();
    const screeners = ensureFixedScreeners();
    const rec = screeners[key] || {};
    state.activeScreener = key;
    state.watchlist = normalizeTickers(rec.watchlist || defaultLists[key] || []);
    state.filters = { ...state.filters, ...(rec.filters || {}) };
    state.columns = { ...state.columns, ...(rec.columns || {}) };
    state.scannerTab = rec.scannerTab || state.scannerTab || "technical";
    state.mobileView = rec.mobileView || state.mobileView || "cards";
    state.sortKey = rec.sortKey || state.sortKey || "score";
    state.sortAsc = !!rec.sortAsc;
    state.selected = state.watchlist[0] || state.selected || "NVDA";
    try { saveSettings(); } catch (_) {}
    renderMobileTabsV80();
    try { renderAll(); } catch (err) { console.warn("v8 render after screener switch failed", err); }
  }
  const previousRenderPortfolioTabsV80 = typeof renderPortfolioTabs === "function" ? renderPortfolioTabs : null;
  renderPortfolioTabs = function renderPortfolioTabsV80(...args){
    if (mobile()) return renderMobileTabsV80();
    return previousRenderPortfolioTabsV80 ? previousRenderPortfolioTabsV80.apply(this, args) : undefined;
  };
  const previousSaveWatchlistV80 = typeof saveWatchlist === "function" ? saveWatchlist : null;
  saveWatchlist = function saveWatchlistV80(){
    if (previousSaveWatchlistV80) previousSaveWatchlistV80.apply(this, arguments);
    if (mobile() && fixedKeys.has(state.activeScreener || "default")) saveActiveFixedScreener();
  };
  function renderDataIntegrityBanner(){
    const host = document.getElementById("scannerSubtitle");
    if (!host) return;
    let bar = document.getElementById("v80DataIntegrityBar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "v80DataIntegrityBar";
      bar.className = "v80-data-bar";
      host.insertAdjacentElement("afterend", bar);
    }
    const tech = state.staticPayloads?.technical || {};
    const fund = state.staticPayloads?.fundamental || {};
    const techCount = Array.isArray(tech.rows) ? tech.rows.length : (state.rows || []).length;
    const fundCount = Array.isArray(fund.rows) ? fund.rows.length : 0;
    const errors = [ ...(Array.isArray(tech.errors) ? tech.errors : []), ...(Array.isArray(fund.errors) ? fund.errors : []), ...(Array.isArray(state.errors) ? state.errors : []) ];
    const missingFund = state.scannerTab === "fundamental" && fundCount === 0;
    const tone = missingFund || errors.length ? "warn" : "ok";
    const techAt = tech.generatedAtTechnical || tech.generatedAt || "—";
    const fundAt = fund.generatedAtFundamental || fund.generatedAt || "—";
    bar.className = `v80-data-bar ${tone}`;
    bar.innerHTML = `<span class="v80-build">${safeHtml(BUILD)}</span><span>Technical: ${safeHtml(String(techCount))} rows · ${safeHtml(String(techAt))}</span><span>Fundamental: ${safeHtml(String(fundCount))} rows · ${safeHtml(String(fundAt))}</span>${missingFund ? `<span class="v80-warning">Run fundamental workflow</span>` : ""}${errors.length ? `<span class="v80-warning">${errors.length} data warning${errors.length === 1 ? "" : "s"}</span>` : ""}`;
  }
  const previousRenderAllV80 = typeof renderAll === "function" ? renderAll : null;
  renderAll = function renderAllV80(){
    try {
      if (previousRenderAllV80) previousRenderAllV80.apply(this, arguments);
    } catch (err) {
      console.error("v8 renderAll error", err);
      const panel = document.querySelector(".scanner-panel");
      if (panel && !document.getElementById("v80RenderError")) {
        panel.insertAdjacentHTML("afterbegin", `<div id="v80RenderError" class="v80-render-error"><b>Render warning</b><br>${safeHtml(err.message || String(err))}</div>`);
      }
    }
    renderDataIntegrityBanner();
    if (mobile()) renderMobileTabsV80();
  };
  function cleanLegacyStorage(){
    try {
      ensureFixedScreeners();
      const dismissed = JSON.parse(localStorage.getItem(STORAGE.alertDismissed) || "[]");
      if (Array.isArray(dismissed)) {
        const cleaned = dismissed.filter(id => !String(id).startsWith("memo-") && !String(id).includes("memo"));
        if (cleaned.length !== dismissed.length) localStorage.setItem(STORAGE.alertDismissed, JSON.stringify(cleaned));
      }
      const memos = JSON.parse(localStorage.getItem("stockTimingRadar.memos.v55") || "[]");
      if (!Array.isArray(memos)) localStorage.setItem("stockTimingRadar.memos.v55", "[]");
      localStorage.setItem("stockTimingRadar.build", BUILD);
    } catch (err) { console.warn("v8 storage cleanup skipped", err); }
  }
  document.addEventListener("click", function(e){
    if (!mobile()) return;
    const target = e.target;
    if (!target || !target.closest) return;
    const tab = target.closest("[data-v80-screener]");
    if (tab) {
      e.preventDefault();
      e.stopImmediatePropagation();
      switchMobileScreenerV80(tab.getAttribute("data-v80-screener"));
      return;
    }
    if (target.closest("[data-v80-screener-settings]")) {
      e.preventDefault();
      e.stopImmediatePropagation();
      try {
        const screeners = ensureFixedScreeners();
        const label = screeners[state.activeScreener || "default"]?.label || state.activeScreener || "Default";
        const el = document.getElementById("activeScreenerLabel");
        if (el) el.textContent = `Active screener: ${label}`;
        openSheet("screenerSettingsSheet");
      } catch (err) { alert(`Active screener: ${state.activeScreener || "default"}`); }
      return;
    }
  }, true);
  window.__stockcheckDiagnosticsV80 = function(){
    const screeners = getStore();
    const memosRaw = localStorage.getItem("stockTimingRadar.memos.v55") || "[]";
    let memos = [];
    try { memos = JSON.parse(memosRaw); } catch (_) {}
    const out = {
      build: BUILD,
      host: location.href,
      staticMode: !!state.staticMode,
      activeScreener: state.activeScreener,
      watchlistCount: state.watchlist?.length || 0,
      rows: state.rows?.length || 0,
      scannerTab: state.scannerTab,
      mobileView: state.mobileView,
      technicalGeneratedAt: state.staticPayloads?.technical?.generatedAtTechnical || state.staticPayloads?.technical?.generatedAt,
      fundamentalGeneratedAt: state.staticPayloads?.fundamental?.generatedAtFundamental || state.staticPayloads?.fundamental?.generatedAt,
      fundamentalRows: state.staticPayloads?.fundamental?.rows?.length || 0,
      dataErrors: state.errors || [],
      screenerKeys: Object.keys(screeners),
      memoCount: Array.isArray(memos) ? memos.length : "invalid",
      localStorageKeys: Object.keys(localStorage).filter(k => k.toLowerCase().includes("stock")),
    };
    console.table(out);
    return out;
  };
  document.addEventListener("DOMContentLoaded", () => {
    cleanLegacyStorage();
    renderPortfolioTabs();
    renderDataIntegrityBanner();
  });
  setTimeout(() => { cleanLegacyStorage(); try { renderPortfolioTabs(); renderDataIntegrityBanner(); } catch (_) {} }, 0);
})();

/* v8.1 Today's Attention List: quiet radar / daily attention filter */
(function initAttentionList(){
  const ATTENTION_URL = "data/attention_today.json";
  const PORTFOLIO_URL = "data/portfolio.json";
  const STORAGE_VIEW = "stockTimingRadar.appView.v55";
  const state = { data:null, portfolio:[], filter:"all", loading:false, error:null };
  const escA = (v) => String(v ?? "").replace(/[&<>"']/g, s => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[s]));
  const numA = (v) => { const n = Number(v); return Number.isFinite(n) ? n : null; };
  const moneyA = (v) => { const n=numA(v); return n==null ? "—" : `$${n.toLocaleString(undefined,{maximumFractionDigits:2, minimumFractionDigits:n < 10 ? 2 : 0})}`; };
  const pctA = (v) => { const n=numA(v); return n==null ? "—" : `${n>0?"+":""}${n.toFixed(1)}%`; };
  const clsPctA = (v) => { const n=numA(v); return n==null ? "neutral" : n < 0 ? "red" : n > 0 ? "green" : "neutral"; };

  const TRIGGERS = {
    price_move: { icon:"📈", label:"Price Move", color:"price" },
    sec_filing: { icon:"📄", label:"SEC Filing", color:"sec" },
    earnings_soon: { icon:"📅", label:"Earnings", color:"earnings" },
    earnings_today: { icon:"📅", label:"Earnings", color:"earnings" },
    buy_zone: { icon:"🟢", label:"Buy Zone", color:"buy" },
    trim_zone: { icon:"✂️", label:"Trim Zone", color:"trim" },
  };
  const FILTERS = [
    ["all", "All"], ["price_move", "Price Move"], ["sec_filing", "SEC Filing"], ["earnings", "Earnings"], ["zone", "Buy/Trim Zone"]
  ];

  function ensureNav(){
    const nav = document.querySelector(".app-mode-nav");
    if(!nav || nav.querySelector('[data-app-view="attention"]')) return;
    const btn = document.createElement("button");
    btn.className = "app-mode-btn attention-mode-btn";
    btn.type = "button";
    btn.dataset.appView = "attention";
    btn.innerHTML = `📡 Today <span class="attention-nav-badge" id="attentionNavBadge" hidden>0</span>`;
    const memoBtn = nav.querySelector('[data-app-view="memo"]');
    memoBtn ? nav.insertBefore(btn, memoBtn) : nav.appendChild(btn);
  }

  function buildPage(){
    if(document.getElementById("attentionPage")) return;
    const shell = document.querySelector(".app-shell") || document.body;
    const page = document.createElement("section");
    page.id = "attentionPage";
    page.className = "attention-page";
    page.innerHTML = `
      <div class="attention-shell">
        <section class="panel-card attention-hero" id="attentionHero"></section>
        <section class="attention-filter-bar" id="attentionFilterBar"></section>
        <section class="panel-card attention-table-card" id="attentionTableCard"></section>
        <section class="attention-card-list" id="attentionCardList"></section>
      </div>`;
    shell.insertAdjacentElement("afterend", page);
  }

  function isStale(updatedAt){
    if(!updatedAt) return true;
    const t = Date.parse(updatedAt);
    if(!Number.isFinite(t)) return true;
    return (Date.now() - t) / 36e5 > 36;
  }
  function fmtTime(iso){
    if(!iso) return "not generated yet";
    const d = new Date(iso);
    if(Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString(undefined, { day:"2-digit", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit", timeZoneName:"short" });
  }
  function triggerMeta(type){ return TRIGGERS[type] || { icon:"•", label:String(type || "Trigger"), color:"default" }; }
  function triggerBadge(type){ const m=triggerMeta(type); return `<span class="trigger-badge trigger-${escA(m.color)}"><span>${m.icon}</span>${escA(m.label)}</span>`; }
  function severityBadge(sev){
    const s=String(sev || "low").toLowerCase();
    const label = s === "high" ? "🔴 High" : s === "medium" ? "🟡 Med" : "⚪ Low";
    return `<span class="severity-badge severity-${escA(s)}">${label}</span>`;
  }
  function itemMatchesFilter(item){
    const f = state.filter;
    if(f === "all") return true;
    const primary = item.primary_trigger;
    const signals = Array.isArray(item.signals) ? item.signals.join(" ").toLowerCase() : "";
    if(f === "earnings") return primary === "earnings_soon" || primary === "earnings_today" || signals.includes("earning");
    if(f === "zone") return primary === "buy_zone" || primary === "trim_zone" || signals.includes("buy zone") || signals.includes("trim");
    return primary === f;
  }
  function sevWeight(sev){ return ({ high:0, medium:1, low:2 }[String(sev||"").toLowerCase()] ?? 3); }
  function trigWeight(type){ return ({ sec_filing:1, earnings_today:2, price_move:3, buy_zone:4, trim_zone:4, earnings_soon:5 }[type] ?? 9); }
  function sortedItems(){
    const items = Array.isArray(state.data?.items) ? [...state.data.items] : [];
    return items.filter(itemMatchesFilter).sort((a,b)=> sevWeight(a.severity)-sevWeight(b.severity) || trigWeight(a.primary_trigger)-trigWeight(b.primary_trigger) || String(a.ticker).localeCompare(String(b.ticker)));
  }
  function actionLabel(key){ return ({ tradingview:"TradingView", yahoo:"Yahoo", raw_data:"Raw Data", sec_filing:"SEC Filing", sec_search:"SEC Search", company_ir:"Company IR" }[key] || key); }
  function actionButtons(actions){
    if(!actions || typeof actions !== "object") return "";
    const order = ["sec_filing", "sec_search", "tradingview", "yahoo", "company_ir", "raw_data"];
    return order.filter(k => actions[k]).map(k => `<a class="attention-action-btn" href="${escA(actions[k])}" target="_blank" rel="noopener noreferrer">${escA(actionLabel(k))}</a>`).join("");
  }
  function signalsInline(item){ return (Array.isArray(item.signals) ? item.signals : []).map(s => `<span>${escA(s)}</span>`).join(`<b class="signal-dot">·</b>`); }
  function signalsList(item){ return (Array.isArray(item.signals) ? item.signals : []).map(s => `<li>${escA(s)}</li>`).join(""); }

  function renderHero(){
    const hero = document.getElementById("attentionHero"); if(!hero) return;
    const total = state.data?.total_monitored ?? state.portfolio.length ?? 0;
    const count = Array.isArray(state.data?.items) ? state.data.items.length : 0;
    const stale = isStale(state.data?.updated_at);
    if(state.loading){
      hero.innerHTML = `<div class="attention-title"><h2>📡 Today's Attention List</h2><p>Loading attention radar…</p></div><div class="attention-skeleton-line"></div>`;
      return;
    }
    if(state.error){
      hero.innerHTML = `<div class="attention-title"><h2>📡 Today's Attention List</h2><p class="red">Could not load attention_today.json · ${escA(state.error)}</p></div>`;
      return;
    }
    hero.innerHTML = `
      <div class="attention-title">
        <h2>📡 Today's Attention List</h2>
        <p>${count ? `${count} stocks need attention` : `${total || "—"} stocks monitored — all clear`} · Last updated: ${escA(fmtTime(state.data?.updated_at))}</p>
      </div>
      ${stale ? `<div class="attention-stale">⚠️ Data may be stale. Last update is older than 36 hours.</div>` : ""}`;
  }
  function renderFilters(){
    const bar = document.getElementById("attentionFilterBar"); if(!bar) return;
    bar.innerHTML = FILTERS.map(([id,label]) => `<button type="button" class="attention-filter ${state.filter===id?"active":""}" data-attention-filter="${escA(id)}">${escA(label)}</button>`).join("");
  }
  function renderEmpty(container, filtered=false){
    const total = state.data?.total_monitored ?? state.portfolio.length ?? 0;
    container.innerHTML = `<div class="attention-empty">
      <h3>✅ ${filtered ? "No matching triggers" : "All clear today"}</h3>
      <p>${filtered ? "Try another filter." : `${total || 0} stocks monitored — no triggers.`}</p>
      <div class="attention-checklist">
        <span>✓ No price move &gt; 5%</span>
        <span>✓ No new SEC filings</span>
        <span>✓ No earnings within 7 days</span>
        <span>✓ No buy/trim zone triggered</span>
      </div>
      <p class="muted">Last updated: ${escA(fmtTime(state.data?.updated_at))}</p>
    </div>`;
  }
  function renderTable(){
    const card = document.getElementById("attentionTableCard"); if(!card) return;
    const items = sortedItems();
    if(!items.length){ renderEmpty(card, (state.data?.items || []).length > 0); return; }
    card.innerHTML = `<div class="attention-table-wrap"><table class="attention-table"><thead><tr>
      <th>Ticker</th><th>Role</th><th>Trigger</th><th>Signals</th><th>Severity</th><th>Actions</th>
    </tr></thead><tbody>${items.map(item => `<tr class="attention-row severity-row-${escA(item.severity || "low")}">
      <td><strong>${escA(item.ticker)}</strong><small>${escA(item.name || "")}</small></td>
      <td>${escA(item.role || "Watchlist")}</td>
      <td>${triggerBadge(item.primary_trigger)}</td>
      <td class="attention-signals">${signalsInline(item)}</td>
      <td>${severityBadge(item.severity)}</td>
      <td><div class="attention-actions">${actionButtons(item.actions)}</div></td>
    </tr>`).join("")}</tbody></table></div>`;
  }
  function renderCards(){
    const list = document.getElementById("attentionCardList"); if(!list) return;
    const items = sortedItems();
    if(!items.length){ renderEmpty(list, (state.data?.items || []).length > 0); return; }
    list.innerHTML = items.map(item => `<article class="attention-card severity-row-${escA(item.severity || "low")}">
      <div class="attention-card-head"><div><strong>${escA(item.ticker)}</strong><span>${escA(item.role || "Watchlist")}</span></div>${severityBadge(item.severity)}</div>
      <div class="attention-card-trigger">${triggerBadge(item.primary_trigger)}</div>
      <ul class="attention-card-signals">${signalsList(item)}</ul>
      <div class="attention-price-strip"><span>Price ${moneyA(item.price)}</span><span class="${clsPctA(item.day_change_pct)}">${pctA(item.day_change_pct)}</span></div>
      <div class="attention-actions attention-mobile-actions">${actionButtons(item.actions)}</div>
    </article>`).join("");
  }
  function updateNavBadge(){
    const badge = document.getElementById("attentionNavBadge");
    const count = Array.isArray(state.data?.items) ? state.data.items.length : 0;
    if(badge){ badge.hidden = count <= 0; badge.textContent = String(count); }
    const nav = document.querySelector('[data-app-view="attention"]');
    if(nav){ nav.classList.toggle("has-attention", count > 0); }
  }
  function render(){ renderHero(); renderFilters(); renderTable(); renderCards(); updateNavBadge(); }

  async function load(){
    state.loading = true; state.error = null; render();
    try{
      const [attnRes, portRes] = await Promise.all([
        fetch(`${ATTENTION_URL}?v=${Date.now()}`, { cache:"no-store" }),
        fetch(`${PORTFOLIO_URL}?v=${Date.now()}`, { cache:"no-store" }).catch(()=>null)
      ]);
      if(!attnRes.ok) throw new Error(`HTTP ${attnRes.status}`);
      state.data = await attnRes.json();
      if(portRes && portRes.ok){ const p = await portRes.json(); state.portfolio = Array.isArray(p) ? p : []; }
    }catch(err){
      console.error("attention load failed", err);
      state.error = err.message || String(err);
      state.data = { updated_at:null, total_monitored:0, items:[] };
    }finally{ state.loading = false; render(); }
  }

  function setAttentionActive(active){
    document.body.classList.toggle("attention-active", !!active);
    if(active){
      document.body.classList.remove("memo-active");
      document.querySelectorAll("[data-app-view]").forEach(b => b.classList.toggle("active", b.dataset.appView === "attention"));
      localStorage.setItem(STORAGE_VIEW, "attention");
      if(!state.data && !state.loading) load();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function bind(){
    document.addEventListener("click", (e) => {
      const nav = e.target.closest('[data-app-view]');
      if(nav && nav.dataset.appView === "attention"){
        e.preventDefault(); e.stopPropagation(); setAttentionActive(true); return;
      }
      if(nav && nav.dataset.appView !== "attention"){
        setTimeout(()=>setAttentionActive(false), 0);
      }
      const filter = e.target.closest("[data-attention-filter]");
      if(filter){ e.preventDefault(); state.filter = filter.dataset.attentionFilter || "all"; render(); }
    }, true);
  }

  function init(){
    ensureNav(); buildPage(); bind(); load();
    if(localStorage.getItem(STORAGE_VIEW) === "attention") setAttentionActive(true);
  }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.__stockcheckAttentionRefresh = load;
})();
