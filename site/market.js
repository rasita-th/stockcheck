const PULSE_MODE_KEY = "stockTimingRadar.marketPulse.mode.v1";
const WATCHLIST_KEY = "stockTimingRadar.watchlist.v54";
const PULSE_MODES = ["balanced", "portfolio", "action", "news", "risk"];
const state = {
  data: null,
  narrative: null,
  technical: null,
  technicalError: null,
  mode: PULSE_MODES.includes(localStorage.getItem(PULSE_MODE_KEY)) ? localStorage.getItem(PULSE_MODE_KEY) : "balanced",
  periods: { globalTable: "ytd_pct", usIndexTable: "week_pct", sectorTable: "week_pct", themeTable: "week_pct" },
  region: "All",
};
const periods = [["day_pct", "1D"], ["week_pct", "1W"], ["month_pct", "1M"], ["ytd_pct", "YTD"], ["year_pct", "1Y"]];
const fmt = v => v == null || !Number.isFinite(Number(v)) ? "—" : `${Number(v) > 0 ? "+" : ""}${Number(v).toFixed(1)}%`;
const cls = v => v == null || Number(v) === 0 ? "neutral" : Number(v) > 0 ? "positive" : "negative";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const asArray = v => Array.isArray(v) ? v : [];
const numeric = v => v == null || v === "" ? null : Number.isFinite(Number(v)) ? Number(v) : null;

function normalise(raw) {
  const d = raw && typeof raw === "object" ? raw : {};
  return {
    ...d,
    global_markets: asArray(d.global_markets || d.markets || d.global_indices),
    us_indices: asArray(d.us_indices || d.us_markets || d.usa_indices),
    us_sectors: asArray(d.us_sectors || d.sectors || d.sector_rotation),
    themes: asArray(d.themes || d.investment_themes || d.theme_rotation),
    today_pulse: asArray(d.today_pulse || d.pulse),
    failed_symbols: asArray(d.failed_symbols),
  };
}

function makeTabs() {
  document.querySelectorAll(".tabs").forEach(t => {
    const target = t.dataset.target;
    t.innerHTML = periods.map(([p, l]) => `<button type="button" class="${state.periods[target] === p ? "active" : ""}" data-period="${p}">${l}</button>`).join("");
  });
}

function card(r, period, max) {
  const v = r[period];
  const width = v == null ? 0 : Math.max(3, Math.min(100, Math.abs(v) / max * 100));
  return `<article class="market-card"><div><div class="market-head"><span class="flag">${esc(r.flag || "•")}</span><span class="market-name"><strong>${esc(r.label || r.name || r.symbol || "Unknown")}</strong><small>${esc(r.country || r.category || r.sector || r.theme || "")} · ${esc(r.symbol || "")}</small></span></div><p class="market-desc">${esc(r.description || "")}</p></div><div class="market-value ${cls(v)}">${fmt(v)}<small>${esc(r.as_of || "unavailable")}</small></div><div class="spark"><span class="${Number(v) >= 0 ? "positive-bg" : "negative-bg"}" style="width:${width}%"></span></div></article>`;
}

function emptyMessage(id) {
  const key = { usIndexTable: "us_indices", sectorTable: "us_sectors", themeTable: "themes", globalTable: "global_markets" }[id];
  const schema = state.data?.schema_version || "ไม่ระบุ";
  return `<div class="empty"><strong>ยังไม่มีข้อมูลในหมวดนี้</strong><br>ไฟล์ market_pulse.json ที่โหลดสำเร็จไม่มีชุด <code>${key}</code> (schema ${esc(schema)}) — ให้รัน workflow Refresh Market Pulse เพื่อสร้าง JSON ใหม่</div>`;
}

function renderRows(id, rows, period) {
  const el = document.getElementById(id);
  if (!el) return;
  let filtered = rows;
  if (id === "globalTable" && state.region !== "All") filtered = rows.filter(r => r.region === state.region);
  const sorted = [...filtered].sort((a, b) => (b[period] ?? -9999) - (a[period] ?? -9999));
  const max = Math.max(1, ...sorted.map(r => Math.abs(Number(r[period]) || 0)));
  el.innerHTML = sorted.length ? sorted.map(r => card(r, period, max)).join("") : emptyMessage(id);
}

function renderPulse() {
  const el = document.getElementById("todayPulse");
  const rows = state.data.today_pulse || [];
  el.innerHTML = rows.length
    ? rows.slice(0, 8).map(r => `<article class="pulse-card"><strong>${esc(r.label || r.symbol)}</strong><small>${esc(r.group)} · ${esc(r.direction)}</small><div class="pulse-number ${cls(r.week_pct)}">1D ${fmt(r.day_pct)} · 1W ${fmt(r.week_pct)}</div></article>`).join("")
    : `<div class="empty">ไม่มีข้อมูล pulse ที่ผ่านเกณฑ์ หรือ workflow ยังไม่ได้สร้างข้อมูลล่าสุด</div>`;
}

function renderRegions() {
  const regions = ["All", ...new Set((state.data.global_markets || []).map(r => r.region).filter(Boolean))];
  const el = document.getElementById("regionFilter");
  el.innerHTML = regions.map(r => `<button type="button" class="${r === state.region ? "active" : ""}" data-region="${esc(r)}">${esc(r)}</button>`).join("");
}

function marketMetrics(d) {
  const sectors = asArray(d.us_sectors).filter(r => numeric(r.week_pct) !== null);
  const us = asArray(d.us_indices).filter(r => numeric(r.week_pct) !== null && r.symbol !== "^VIX");
  const themes = asArray(d.themes).filter(r => numeric(r.week_pct) !== null);
  const globals = asArray(d.global_markets).filter(r => numeric(r.week_pct) !== null);
  const average = (rows, key) => rows.length ? rows.reduce((sum, row) => sum + Number(row[key]), 0) / rows.length : 0;
  const sorted = (rows, key) => [...rows].sort((a, b) => Number(b[key]) - Number(a[key]));
  const sectorAvg = average(sectors, "week_pct");
  const usAvg = average(us, "week_pct");
  const positiveWeek = sectors.filter(r => Number(r.week_pct) > 0).length;
  const breadthRatio = sectors.length ? positiveWeek / sectors.length : 0.5;
  const score = sectorAvg * 0.55 + usAvg * 0.45 + (breadthRatio - 0.5) * 4;
  const regime = score > 1 ? "risk-on" : score < -1 ? "risk-off" : "mixed";
  const vix = asArray(d.us_indices).find(r => r.symbol === "^VIX" || /vix|volatility/i.test(r.label || ""));
  const vixWeek = numeric(vix?.week_pct);
  const riskLevel = regime === "risk-off" || breadthRatio < 0.3 || (vixWeek !== null && vixWeek > 8) ? "elevated" : regime === "risk-on" && breadthRatio > 0.65 ? "contained" : "moderate";
  return {
    sectors, us, themes, globals, sectorAvg, usAvg, breadthRatio, regime, riskLevel, vixWeek,
    sectorLeader: sorted(sectors, "week_pct")[0], sectorLaggard: sorted(sectors, "week_pct").at(-1),
    themeLeader: sorted(themes, "week_pct")[0], themeLaggard: sorted(themes, "week_pct").at(-1),
    globalLeader: sorted(globals, "week_pct")[0], globalLaggard: sorted(globals, "week_pct").at(-1),
  };
}

function pickNames(rows, limit = 3) {
  return asArray(rows).filter(Boolean).slice(0, limit).map(r => r.label || r.symbol).filter(Boolean);
}

function fallbackNarrative(d) {
  const m = marketMetrics(d);
  const breadthText = `${Math.round(m.breadthRatio * 100)}% ของ US sectors เป็นบวกในรอบสัปดาห์`;
  const leader = m.sectorLeader;
  const laggard = m.sectorLaggard;
  const theme = m.themeLeader;
  const globalLeader = m.globalLeader;
  const globalLaggard = m.globalLaggard;
  const regimeThai = m.regime === "risk-on" ? "Risk-on" : m.regime === "risk-off" ? "Risk-off" : "Mixed";
  const headline = m.regime === "risk-on"
    ? `แรงซื้อกระจายกว้าง โดย ${leader?.label || "กลุ่มนำ"} เป็นผู้นำตลาด`
    : m.regime === "risk-off"
      ? `แรงขายกดดันตลาด ขณะที่ ${laggard?.label || "กลุ่มอ่อนแอ"} ถ่วง breadth`
      : `ตลาดยังเลือกเล่นเป็นรายกลุ่ม และ breadth ยังไม่ยืนยัน Risk-on เต็มตัว`;
  const balanced = [
    `ภาวะตลาดอยู่ในโหมด ${regimeThai}; ค่าเฉลี่ย US sectors 1W อยู่ที่ ${fmt(m.sectorAvg)}.`,
    `${breadthText} สะท้อนว่าการขึ้นหรือลงกระจายตัวมากน้อยเพียงใด.`,
    `${leader?.label || "Sector ผู้นำ"} นำที่ ${fmt(leader?.week_pct)} ขณะที่ ${laggard?.label || "sector ตามหลัง"} อยู่ที่ ${fmt(laggard?.week_pct)}.`,
    `${theme?.label || "ธีมเด่น"} เป็นธีมที่แข็งที่สุดในชุดติดตามที่ ${fmt(theme?.week_pct)}.`,
    `ตลาดโลกนำโดย ${globalLeader?.label || "—"} ${fmt(globalLeader?.week_pct)} และอ่อนสุดคือ ${globalLaggard?.label || "—"} ${fmt(globalLaggard?.week_pct)}.`,
    m.riskLevel === "elevated" ? "ควรให้ความสำคัญกับ position sizing และรอ price confirmation มากกว่าการไล่ราคา." : "ภาพรวมยังเปิดทางให้ถือผู้นำ แต่ควรเพิ่มน้ำหนักเฉพาะจุดที่ราคาและ breadth สนับสนุนกัน.",
  ];
  const portfolio = [
    "Portfolio mode จะเชื่อมกับ Watchlist ที่บันทึกไว้ใน Scanner บนอุปกรณ์นี้.",
    `Market backdrop ปัจจุบันคือ ${regimeThai} และ breadth สัปดาห์อยู่ที่ ${Math.round(m.breadthRatio * 100)}%.`,
    `${leader?.label || "Sector ผู้นำ"} เป็นกลุ่มที่ช่วยหนุน relative strength ของหุ้นที่เกี่ยวข้อง.`,
    `${laggard?.label || "Sector อ่อนแอ"} เป็นกลุ่มที่ควรตรวจสอบว่าหุ้นในพอร์ตหลุดแนวรับหรือไม่.`,
    "เมื่อ technical.json โหลดสำเร็จ ระบบจะแยก Potential Add, Hold, Watch, Avoid Chasing และ Trim Risk ให้เฉพาะ Watchlist.",
  ];
  const action = [
    m.regime === "risk-off" ? "ลดการไล่ราคาและให้ความสำคัญกับการป้องกัน drawdown ก่อน." : "ถือผู้นำที่ยังมี relative strength และหลีกเลี่ยงการเพิ่มในหุ้นที่ยืดตัวเกินไป.",
    `${leader?.label || "Sector ผู้นำ"}: รอ pullback หรือ breakout ที่มี volume ยืนยัน แทนการซื้อจาก headline เพียงอย่างเดียว.`,
    `${laggard?.label || "Sector อ่อนแอ"}: ตรวจสอบแนวรับและสัญญาณหลุด EMA สำคัญก่อนตัดสินใจเพิ่มน้ำหนัก.`,
    `${theme?.label || "ธีมเด่น"}: จัด position size ให้สอดคล้องกับ volatility ของธีม ไม่ใช่ความมั่นใจใน narrative.`,
    "ใช้ Portfolio tab เพื่อดู action tag จาก technical scanner ของ Watchlist ที่บันทึกไว้.",
  ];
  const news = [
    `ตลาดสหรัฐอยู่ในภาวะ ${regimeThai} หลังค่าเฉลี่ยดัชนีหลัก 1W อยู่ที่ ${fmt(m.usAvg)}.`,
    `${leader?.label || "Sector ผู้นำ"} ปรับตัวเด่นสุดในกลุ่ม sector ที่ ${fmt(leader?.week_pct)}.`,
    `${laggard?.label || "Sector ตามหลัง"} อ่อนสุดที่ ${fmt(laggard?.week_pct)}.`,
    `ธีมเด่นคือ ${theme?.label || "—"} ที่ ${fmt(theme?.week_pct)} ขณะที่ตลาดโลกมี ${globalLeader?.label || "—"} เป็นผู้นำ.`,
    `ระดับความเสี่ยงเชิงตลาดถูกจัดเป็น ${m.riskLevel}; สรุปนี้อิงราคาและ ETF proxy ไม่ใช่ feed ข่าวเรียลไทม์.`,
  ];
  const risk = [
    `Risk level: ${m.riskLevel}; breadth สัปดาห์อยู่ที่ ${Math.round(m.breadthRatio * 100)}%.`,
    `${laggard?.label || "Sector อ่อนแอ"} เป็นจุดเสี่ยงหลักจากผลตอบแทน 1W ${fmt(laggard?.week_pct)}.`,
    `${m.themeLaggard?.label || "ธีมอ่อนแอ"} เป็นธีมที่ตามหลังมากที่สุดที่ ${fmt(m.themeLaggard?.week_pct)}.`,
    m.vixWeek !== null ? `VIX proxy เปลี่ยนแปลง ${fmt(m.vixWeek)} ในรอบสัปดาห์.` : "VIX proxy ไม่มีข้อมูลเพียงพอในรอบนี้ จึงให้น้ำหนัก breadth และดัชนีแทน.",
    "หากหุ้นใน Watchlist หลุด EMA200 หรือ scanner เปลี่ยนเป็น AVOID/WEAK ให้ถือเป็นความเสี่ยงที่ต้องตรวจสอบก่อนเพิ่มสถานะ.",
  ];
  const common = {
    positive: pickNames([leader, theme]),
    watch: pickNames([m.globalLeader, m.globalLaggard]),
    risk: pickNames([laggard, m.themeLaggard]),
  };
  return {
    schema_version: "1.0-fallback",
    default_mode: "balanced",
    regime: m.regime,
    risk_level: m.riskLevel,
    headline,
    sources: [
      { label: "Yahoo Finance / yfinance", detail: "ราคา EOD ของดัชนีและ ETF proxy" },
      { label: "Stock Timing Radar", detail: "breadth, sector rotation, theme rotation และ technical scanner" },
    ],
    modes: {
      balanced: { label: "Market", edition: "MARKET · BALANCED", headline, deck: "สรุปภาพตลาดจาก breadth, ดัชนี, sector และ theme ในข้อความ 5–10 บรรทัด", summary: balanced, ...common },
      portfolio: { label: "Portfolio", edition: "PORTFOLIO · WATCHLIST", headline: "เชื่อม Market Pulse กับ Watchlist ที่บันทึกใน Scanner", deck: "ระบบจะใช้ technical.json ใน browser เพื่อสร้างข้อความเฉพาะพอร์ตโดยไม่เปิดเผย watchlist ให้ backend", summary: portfolio, ...common },
      action: { label: "Action", edition: "ACTION · DECISION SUPPORT", headline: m.regime === "risk-off" ? "เน้นควบคุมความเสี่ยงก่อนเพิ่ม exposure" : "ถือผู้นำ รอจังหวะ และไม่ไล่ราคาที่ขยายตัวเกินไป", deck: "เปลี่ยนข้อมูลตลาดเป็นสิ่งที่ควรตรวจสอบต่อ ไม่ใช่คำสั่งซื้อขาย", summary: action, ...common },
      news: { label: "News", edition: "NEWS · MARKET TAPE", headline: `Market tape: ${regimeThai} พร้อม sector rotation ที่แตกต่างกัน`, deck: "ข่าวสั้นเชิงตลาดจากข้อมูลราคา ไม่กล่าวอ้างเหตุการณ์ที่ไม่มีแหล่งข่าวรองรับ", summary: news, ...common },
      risk: { label: "Risk", edition: "RISK · MONITOR", headline: m.riskLevel === "elevated" ? "ความเสี่ยงสูงกว่าปกติ ควรลดการตัดสินใจจาก momentum ระยะสั้น" : "ความเสี่ยงยังควบคุมได้ แต่ breadth ต้องยืนยันต่อเนื่อง", deck: "จัดลำดับสิ่งที่อาจทำให้ thesis หรือโครงสร้างราคาผิดทาง", summary: risk, ...common },
    },
  };
}

function cleanMode(raw, fallback) {
  const mode = raw && typeof raw === "object" ? raw : {};
  let summary = asArray(mode.summary).filter(x => typeof x === "string" && x.trim());
  if (summary.length < 5) summary = asArray(fallback.summary);
  summary = summary.slice(0, 10);
  return {
    ...fallback,
    ...mode,
    summary,
    actions: asArray(mode.actions),
    positive: asArray(mode.positive || fallback.positive),
    watch: asArray(mode.watch || fallback.watch),
    risk: asArray(mode.risk || fallback.risk),
  };
}

function normaliseNarrative(d) {
  const fallback = fallbackNarrative(d);
  const raw = d.narrative && typeof d.narrative === "object" ? d.narrative : {};
  const modes = {};
  for (const key of PULSE_MODES) modes[key] = cleanMode(raw.modes?.[key], fallback.modes[key]);
  return {
    ...fallback,
    ...raw,
    regime: raw.regime || fallback.regime,
    risk_level: raw.risk_level || fallback.risk_level,
    sources: asArray(raw.sources).length ? raw.sources : fallback.sources,
    modes,
  };
}

function loadSavedWatchlist() {
  try {
    const rows = JSON.parse(localStorage.getItem(WATCHLIST_KEY) || "[]");
    return Array.isArray(rows) ? [...new Set(rows.map(x => String(x || "").trim().toUpperCase()).filter(Boolean))] : [];
  } catch (_) {
    return [];
  }
}

function technicalAction(row) {
  const score = numeric(row.score) ?? 0;
  const rsi = numeric(row.rsi14 ?? row.rsi);
  const vs20 = numeric(row.pctVsEma20 ?? row.ema20Pct);
  const vs200 = numeric(row.pctVsEma200 ?? row.ema200Pct);
  const signal = String(row.signal || "").toUpperCase();
  if ((vs200 !== null && vs200 < 0) || /AVOID|WEAK|ERROR/.test(signal) || score < 40) return { tag: "TRIM RISK", kind: "trim", rank: 5, reason: `โครงสร้างอ่อน · Score ${Math.round(score)}` };
  if ((rsi !== null && rsi >= 70) || (vs20 !== null && vs20 >= 15) || /HOT|อย่าไล่/.test(signal)) return { tag: "AVOID CHASING", kind: "chase", rank: 4, reason: `ราคาเริ่มยืด · RSI ${rsi === null ? "—" : rsi.toFixed(0)}` };
  if (score >= 78 && (rsi === null || rsi < 68) && (vs20 === null || (vs20 >= -2 && vs20 <= 10))) return { tag: "POTENTIAL ADD", kind: "add", rank: 3, reason: `Score ${Math.round(score)} · ระยะจาก EMA20 ${fmt(vs20)}` };
  if (score >= 62) return { tag: "HOLD", kind: "hold", rank: 2, reason: `แนวโน้มยังสนับสนุน · Score ${Math.round(score)}` };
  return { tag: "WATCH", kind: "watch", rank: 1, reason: `รอสัญญาณยืนยัน · Score ${Math.round(score)}` };
}

function applyPortfolioNarrative() {
  if (!state.narrative || !state.technical) return;
  const rows = asArray(state.technical.rows);
  const watchlist = loadSavedWatchlist();
  const selected = watchlist.length ? rows.filter(r => watchlist.includes(String(r.symbol || r.ticker || "").toUpperCase())) : [];
  const base = state.narrative.modes.portfolio;
  if (!selected.length) {
    base.deck = watchlist.length ? "พบ Watchlist แต่ยังจับคู่กับ technical.json ไม่ได้ในรอบนี้" : "ยังไม่มี Watchlist ที่บันทึกใน Scanner บนอุปกรณ์นี้";
    base.summary = [
      watchlist.length ? `มี ${watchlist.length} ticker ใน Watchlist แต่ข้อมูล technical รอบนี้ยังไม่ตรงกัน.` : "เปิดหน้า Scanner และบันทึก Watchlist เพื่อสร้าง Portfolio Pulse เฉพาะอุปกรณ์นี้.",
      ...base.summary.filter(line => !/Portfolio mode|Watchlist ที่บันทึก/.test(line)).slice(0, 4),
    ].slice(0, 5);
    return;
  }
  const tagged = selected.map(row => ({ row, action: technicalAction(row) }));
  const byRank = [...tagged].sort((a, b) => b.action.rank - a.action.rank || (numeric(b.row.score) ?? 0) - (numeric(a.row.score) ?? 0));
  const names = kind => tagged.filter(x => x.action.kind === kind).sort((a, b) => (numeric(b.row.score) ?? 0) - (numeric(a.row.score) ?? 0)).map(x => x.row.symbol);
  const adds = names("add"), holds = names("hold"), watches = names("watch"), chase = names("chase"), trims = names("trim");
  const strongest = [...selected].sort((a, b) => (numeric(b.score) ?? 0) - (numeric(a.score) ?? 0)).slice(0, 3).map(r => r.symbol);
  const weakest = [...selected].sort((a, b) => (numeric(a.score) ?? 0) - (numeric(b.score) ?? 0)).slice(0, 3).map(r => r.symbol);
  base.headline = `Portfolio Pulse อ่าน ${selected.length} หุ้นจาก Watchlist ที่บันทึกใน Scanner`;
  base.deck = "คำนวณใน browser จาก technical.json และ localStorage; Watchlist ไม่ถูกส่งกลับไปยัง backend";
  base.summary = [
    `ระบบจับคู่ข้อมูลได้ ${selected.length}/${watchlist.length} ticker จาก Watchlist ปัจจุบัน.`,
    strongest.length ? `Relative strength เด่นสุดตาม scanner: ${strongest.join(", ")}.` : "ยังไม่มีหุ้นที่ได้คะแนนเด่นชัด.",
    adds.length ? `Potential Add ที่ผ่านเงื่อนไข trend และไม่ยืดเกินไป: ${adds.slice(0, 4).join(", ")}.` : "ยังไม่มีหุ้นที่เข้าเงื่อนไข Potential Add แบบครบถ้วน.",
    chase.length ? `หลีกเลี่ยงการไล่ราคาใน ${chase.slice(0, 4).join(", ")} เพราะ RSI หรือระยะจาก EMA20 สูง.` : "ไม่พบหุ้นที่เข้าข่ายยืดตัวรุนแรงในชุดที่จับคู่ได้.",
    trims.length ? `ตรวจสอบความเสี่ยงเชิงโครงสร้างใน ${trims.slice(0, 4).join(", ")}.` : `กลุ่มคะแนนต่ำสุดที่ควรติดตาม: ${weakest.join(", ") || "—"}.`,
    `Market backdrop ยังเป็น ${state.narrative.regime}; ใช้ action tag ร่วมกับข่าวและ thesis ก่อนตัดสินใจ.`,
  ];
  base.actions = byRank.slice(0, 6).map(x => ({ ticker: x.row.symbol, status: x.action.tag, kind: x.action.kind, reason: x.action.reason }));
  base.positive = [...adds, ...holds].slice(0, 3);
  base.watch = [...watches, ...chase].slice(0, 3);
  base.risk = trims.slice(0, 3);
  const actionMode = state.narrative.modes.action;
  actionMode.actions = base.actions;
  actionMode.positive = base.positive;
  actionMode.watch = base.watch;
  actionMode.risk = base.risk;
  actionMode.summary = [actionMode.summary[0], ...base.summary.slice(1, 5)].slice(0, 5);
}

function formatThaiDate(value) {
  const dt = value ? new Date(value) : null;
  if (!dt || Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleString("th-TH", { timeZone: "Asia/Bangkok", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function modeBucket(items, fallback = "—") {
  const names = asArray(items).map(x => typeof x === "string" ? x : x?.label || x?.ticker || x?.symbol).filter(Boolean).slice(0, 3);
  return { main: names[0] || fallback, detail: names.length > 1 ? names.slice(1).join(" · ") : "ไม่มีรายการเพิ่ม" };
}

function renderActions(actions) {
  const el = document.getElementById("pulseActionGrid");
  const rows = asArray(actions).slice(0, 6);
  el.hidden = !rows.length;
  el.innerHTML = rows.map(row => `<article class="action-card"><header><strong>${esc(row.ticker || row.label || "MARKET")}</strong><span class="action-tag ${esc(row.kind || "watch")}">${esc(row.status || "WATCH")}</span></header><p>${esc(row.reason || "ตรวจสอบข้อมูลประกอบเพิ่มเติม")}</p></article>`).join("");
}

function renderSignalGrid(mode) {
  const positive = modeBucket(mode.positive);
  const watch = modeBucket(mode.watch);
  const risk = modeBucket(mode.risk);
  document.getElementById("pulseSignalGrid").innerHTML = `
    <section class="signal-box positive-box"><span>POSITIVE</span><strong>${esc(positive.main)}</strong><small>${esc(positive.detail)}</small></section>
    <section class="signal-box watch-box"><span>WATCH</span><strong>${esc(watch.main)}</strong><small>${esc(watch.detail)}</small></section>
    <section class="signal-box risk-box"><span>RISK</span><strong>${esc(risk.main)}</strong><small>${esc(risk.detail)}</small></section>`;
}

function renderSources() {
  const sources = asArray(state.narrative.sources);
  const technicalNote = state.technical
    ? `<p><strong>Technical scanner:</strong> โหลด ${asArray(state.technical.rows).length} rows สำหรับ Portfolio mode</p>`
    : state.technicalError ? `<p><strong>Technical scanner:</strong> ${esc(state.technicalError)}</p>` : "";
  document.getElementById("pulseSourceList").innerHTML = sources.map(s => `<p><strong>${esc(s.label || s.name || "Source")}:</strong> ${esc(s.detail || s.description || "")}</p>`).join("") + technicalNote;
}

function renderBriefing() {
  if (!state.narrative) return;
  const mode = state.narrative.modes[state.mode] || state.narrative.modes.balanced;
  document.querySelectorAll("[data-pulse-mode]").forEach(button => {
    const active = button.dataset.pulseMode === state.mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.getElementById("pulseEdition").textContent = mode.edition || `${state.mode.toUpperCase()} · PULSE`;
  document.getElementById("pulseHeadline").textContent = mode.headline || state.narrative.headline || "Market Pulse";
  document.getElementById("pulseDeck").textContent = mode.deck || "สรุปข้อมูลตลาดล่าสุด";
  document.getElementById("pulseSummaryList").innerHTML = asArray(mode.summary).slice(0, 10).map(line => `<li>${esc(line)}</li>`).join("");
  renderActions(mode.actions);
  renderSignalGrid(mode);
  renderSources();

  const regime = state.narrative.regime || "mixed";
  const risk = state.narrative.risk_level || "moderate";
  const regimeBadge = document.getElementById("pulseRegimeBadge");
  const riskBadge = document.getElementById("pulseRiskBadge");
  regimeBadge.textContent = regime;
  regimeBadge.className = `status-badge ${regime === "risk-on" ? "positive" : regime === "risk-off" ? "negative" : "watch"}`;
  riskBadge.textContent = `Risk ${risk}`;
  riskBadge.className = `status-badge ${risk === "contained" ? "positive" : risk === "elevated" ? "negative" : "watch"}`;

  const generated = state.data?.generated_at ? new Date(state.data.generated_at) : null;
  const next = state.data?.next_refresh_at ? new Date(state.data.next_refresh_at) : generated && !Number.isNaN(generated.getTime()) ? new Date(generated.getTime() + 12 * 3600 * 1000) : null;
  document.getElementById("pulseUpdatedAt").textContent = formatThaiDate(generated);
  document.getElementById("pulseNextRefresh").textContent = formatThaiDate(next);
  const stale = generated && !Number.isNaN(generated.getTime()) ? Date.now() - generated.getTime() > 18 * 3600 * 1000 : true;
  document.getElementById("pulseStaleBadge").hidden = !stale;
  document.getElementById("marketBriefing").setAttribute("aria-busy", "false");
}

function renderSummary() {
  const d = state.data, b = d.breadth || {};
  document.getElementById("breadthDay").textContent = `${b.sectors_positive_day ?? 0}/${b.sector_count ?? 0}`;
  document.getElementById("breadthWeek").textContent = `${b.sectors_positive_week ?? 0}/${b.sector_count ?? 0}`;
  const s = d.us_sectors || [];
  const valid = s.filter(r => numeric(r.week_pct) !== null);
  const avg = valid.length ? valid.reduce((a, r) => a + Number(r.week_pct), 0) / valid.length : 0;
  document.getElementById("riskMode").textContent = valid.length ? (avg > 1 ? "Risk-on" : avg < -1 ? "Risk-off" : "Mixed") : "—";
  document.getElementById("riskNote").textContent = valid.length ? `ค่าเฉลี่ย sector 1W ${fmt(avg)}` : "รอข้อมูล sector";
  const leader = [...valid].sort((a, b) => Number(b.week_pct) - Number(a.week_pct))[0];
  document.getElementById("weeklyLeader").textContent = leader?.label || "—";
  document.getElementById("weeklyLeaderValue").textContent = leader ? `1W ${fmt(leader.week_pct)}` : "—";
}

function render() {
  const d = state.data;
  const dt = d.generated_at ? new Date(d.generated_at) : null;
  document.getElementById("freshness").textContent = dt && !Number.isNaN(dt.getTime()) ? formatThaiDate(dt) : "ไม่ทราบเวลา";
  document.getElementById("dataStatus").textContent = `สถานะ ${d.status || "unknown"} · สำเร็จ ${d.successful_symbols ?? "—"} · ล้มเหลว ${(d.failed_symbols || []).length}`;
  renderBriefing();
  renderSummary();
  renderPulse();
  renderRegions();
  renderRows("globalTable", d.global_markets, state.periods.globalTable);
  renderRows("usIndexTable", d.us_indices, state.periods.usIndexTable);
  renderRows("sectorTable", d.us_sectors, state.periods.sectorTable);
  renderRows("themeTable", d.themes, state.periods.themeTable);
}

async function loadJsonCandidates(candidates) {
  let lastError;
  for (const path of candidates) {
    try {
      const response = await fetch(`${path}?v=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("โหลด JSON ไม่สำเร็จ");
}

document.addEventListener("click", e => {
  const pulseMode = e.target.closest("[data-pulse-mode]");
  if (pulseMode) {
    state.mode = pulseMode.dataset.pulseMode;
    localStorage.setItem(PULSE_MODE_KEY, state.mode);
    renderBriefing();
    return;
  }
  const p = e.target.closest("[data-period]");
  if (p) {
    const tabs = p.closest(".tabs"), target = tabs.dataset.target;
    state.periods[target] = p.dataset.period;
    makeTabs();
    render();
    return;
  }
  const r = e.target.closest("[data-region]");
  if (r) {
    state.region = r.dataset.region;
    render();
  }
});

async function loadPulse() {
  try {
    const raw = await loadJsonCandidates(["data/market_pulse.json", "./data/market_pulse.json", "../data/market_pulse.json"]);
    state.data = normalise(raw);
    state.narrative = normaliseNarrative(state.data);
    render();
  } catch (error) {
    state.data = normalise({ status: "error", failed_symbols: [], generated_at: null });
    state.narrative = normaliseNarrative(state.data);
    state.narrative.modes.balanced.headline = "Market Pulse ยังโหลดข้อมูลหลักไม่สำเร็จ";
    state.narrative.modes.balanced.deck = error?.message || "ไม่พบ data/market_pulse.json";
    state.narrative.modes.balanced.summary = [
      "ตรวจสอบว่า workflow Refresh Market Pulse ทำงานสำเร็จ.",
      "ตรวจสอบว่า site/data/market_pulse.json ถูก commit และ deploy.",
      "หน้าเว็บยังคงแสดงโครงสร้างทั้งหมดโดยไม่ลบตารางหรือ navigation.",
      "ข้อมูล unavailable จะแสดงเป็นขีดแทนการสร้างตัวเลขขึ้นมาเอง.",
      "เมื่อ JSON กลับมาพร้อม ระบบจะ render ใหม่ในรอบโหลดถัดไป.",
    ];
    render();
  }
  try {
    state.technical = await loadJsonCandidates(["data/technical.json", "./data/technical.json", "../data/technical.json"]);
    applyPortfolioNarrative();
    renderBriefing();
  } catch (error) {
    state.technicalError = error?.message || "โหลด technical.json ไม่สำเร็จ";
    renderSources();
  }
}

makeTabs();
loadPulse();
