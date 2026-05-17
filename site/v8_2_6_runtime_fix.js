/* Stock Timing Radar v8.2.6
   Fundamental Freshness Resolver UI + EPS surprise + Recommendation Trends.
   Static-site safe: reads generated JSON only. No API key in browser. */
(function stockcheckV826Runtime(){
  const VERSION = "8.2.6";
  const state = { fundamental: null, rec: null, loadingFundamental: null, loadingRec: null };

  const esc = (value) => String(value ?? "").replace(/[&<>\"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#039;"}[c]));
  const norm = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
  const num = (value) => { const n = Number(value); return Number.isFinite(n) ? n : null; };
  const money = (value) => {
    const n0 = num(value); if (n0 === null) return "—";
    const sign = n0 < 0 ? "-" : ""; const n = Math.abs(n0);
    if (n >= 1e9) return `${sign}$${(n/1e9).toFixed(2)}B`;
    if (n >= 1e6) return `${sign}$${(n/1e6).toFixed(2)}M`;
    if (n >= 1e3) return `${sign}$${(n/1e3).toFixed(2)}K`;
    return `${sign}$${n.toFixed(2)}`;
  };
  const pct = (value) => { const n = num(value); return n === null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`; };

  function injectStyles(){
    if (document.getElementById("stockcheckV826Styles")) return;
    const style = document.createElement("style");
    style.id = "stockcheckV826Styles";
    style.textContent = `
      .v826-ai-card{margin-top:16px;padding:18px;border:1px solid rgba(88,166,255,.55);border-radius:18px;background:linear-gradient(135deg,rgba(31,75,122,.42),rgba(13,17,23,.78));box-shadow:0 14px 40px rgba(0,0,0,.18)}
      .v826-ai-layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:16px;align-items:start}.v826-ai-title{font-size:21px;font-weight:900;color:#E6EDF3;margin-bottom:10px}.v826-source-pill{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(88,166,255,.65);border-radius:999px;padding:6px 10px;background:rgba(13,48,89,.72);color:#79C0FF;font-weight:800;font-size:13px}.v826-source-label{margin-top:10px;color:#8B949E;font-size:13px;line-height:1.45}.v826-warning{margin-bottom:12px;padding:10px 12px;border:1px solid rgba(210,153,34,.45);border-radius:12px;background:rgba(210,153,34,.11);color:#FFD166;font-weight:800}.v826-facts{display:grid;gap:10px}.v826-fact{display:grid;grid-template-columns:18px minmax(0,1fr);gap:10px;align-items:start;padding:12px 13px;border:1px solid rgba(48,54,61,.9);border-radius:14px;background:rgba(13,17,23,.56)}.v826-dot{width:12px;height:12px;border-radius:99px;margin-top:5px;background:#8B949E}.v826-fact.good .v826-dot{background:#3FB950}.v826-fact.bad .v826-dot{background:#F85149}.v826-fact.warn .v826-dot{background:#D29922}.v826-fact.neutral .v826-dot{background:#8B949E}.v826-fact strong{color:#E6EDF3}.v826-fact .v826-good{color:#3FB950;font-weight:900}.v826-fact .v826-bad{color:#F85149;font-weight:900}.v826-fact .v826-warn{color:#D29922;font-weight:900}.v826-fact-source{display:none;margin-top:6px;color:#8B949E;font-size:12px}.v826-ai-card.show-sources .v826-fact-source{display:block}.v826-source-toggle{appearance:none;border:1px solid rgba(88,166,255,.75);background:rgba(13,48,89,.7);border-radius:999px;color:#79C0FF;font-weight:800;padding:6px 10px;min-height:34px;cursor:pointer}.v826-source-toggle:hover{filter:brightness(1.1)}
      .v826-rec-section{margin:14px 0 16px;padding:16px;border:1px solid #30363D;border-radius:16px;background:rgba(13,17,23,.42)}.v826-rec-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}.v826-rec-head strong{font-size:16px;color:#E6EDF3}.v826-rec-head span{font-size:12px;color:#8B949E;text-align:right}.v826-rec-chart{display:grid;gap:10px;margin-top:10px}.v826-rec-row{display:grid;grid-template-columns:74px minmax(0,1fr) 42px;gap:10px;align-items:center}.v826-rec-period{font:700 12px/1.1 'IBM Plex Mono',monospace;color:#8B949E}.v826-rec-total{font:700 12px/1 'IBM Plex Mono',monospace;color:#8B949E;text-align:right}.v826-rec-track{display:flex;height:30px;overflow:hidden;border-radius:10px;background:#0D1117;border:1px solid rgba(48,54,61,.7)}.v826-rec-seg{height:100%;display:flex;align-items:center;justify-content:center;font:800 11px/1 'IBM Plex Mono',monospace;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.35)}.v826-rec-seg.zero{display:none}.v826-rec-seg.strong-buy{background:#1a7f37}.v826-rec-seg.buy{background:#3FB950}.v826-rec-seg.hold{background:#D29922}.v826-rec-seg.sell{background:#F85149}.v826-rec-seg.strong-sell{background:#8b0000}.v826-rec-legend{display:flex;flex-wrap:wrap;gap:8px 12px;margin:12px 0 0;color:#8B949E;font-size:12px}.v826-rec-dot{width:10px;height:10px;border-radius:99px;display:inline-block}.v826-rec-dot.strong-buy{background:#1a7f37}.v826-rec-dot.buy{background:#3FB950}.v826-rec-dot.hold{background:#D29922}.v826-rec-dot.sell{background:#F85149}.v826-rec-dot.strong-sell{background:#8b0000}.v826-rec-empty{padding:18px;border:1px dashed #30363D;border-radius:12px;color:#8B949E;text-align:center;background:rgba(22,27,34,.45)}
      @media(max-width:767px){.v826-ai-card{padding:14px;margin-top:14px}.v826-ai-layout{grid-template-columns:150px minmax(0,1fr);gap:10px}.v826-ai-title{font-size:20px;line-height:1.15}.v826-fact{padding:11px 12px}.v826-rec-section{padding:13px;margin-bottom:18px}.v826-rec-head{display:block}.v826-rec-head span{display:block;text-align:left;margin-top:4px}.v826-rec-row{grid-template-columns:58px minmax(0,1fr) 34px;gap:7px}.v826-rec-track{height:28px}}
    `;
    document.head.appendChild(style);
  }

  function loadJson(url, cacheKey){
    if (state[cacheKey]) return Promise.resolve(state[cacheKey]);
    const loadingKey = `loading${cacheKey[0].toUpperCase()}${cacheKey.slice(1)}`;
    if (!state[loadingKey]) {
      state[loadingKey] = fetch(`${url}?v=${Date.now()}`, { cache: "no-store" })
        .then(res => { if (!res.ok) throw new Error(`${url} HTTP ${res.status}`); return res.json(); })
        .then(data => (state[cacheKey] = data))
        .catch(err => (state[cacheKey] = { _error: err.message }));
    }
    return state[loadingKey];
  }
  const loadFundamental = () => loadJson("data/fundamental.json", "fundamental");
  const loadRec = () => loadJson("data/recommendation_trends.json", "rec");

  function getTickerFromContext(el){
    const cardText = norm(el?.textContent || "");
    let m = cardText.match(/Ticker:\s*([A-Z0-9.\-]+)(?=\s*(?:Source|Current|$))/i);
    if (m) return m[1].toUpperCase();
    const dash = el?.closest?.(".fundamental-dashboard, .detail-panel, body");
    const dashText = norm(dash?.textContent || "");
    m = dashText.match(/\b([A-Z0-9.\-]{1,10})\s+dashboard\b/i);
    if (m) return m[1].toUpperCase();
    const h = document.querySelector(".detail-identity h2, [data-detail-title], h1, h2")?.textContent;
    m = norm(h || "").match(/^([A-Z0-9.\-]{1,10})\b/);
    return m ? m[1].toUpperCase() : "";
  }

  function rowForTicker(data, ticker){
    const t = String(ticker || "").toUpperCase();
    if (!t || !data || data._error) return null;
    const rows = Array.isArray(data.rows) ? data.rows : [];
    return rows.find(r => String(r.ticker || r.symbol || "").toUpperCase() === t)
      || data.fundamentals?.[t]?.fundamental || data.fundamentals?.[t]?.latest || null;
  }

  function toneClass(tone){ return ["good","bad","warn","neutral"].includes(tone) ? tone : "neutral"; }
  function colorize(text, tone){
    const cls = tone === "good" ? "v826-good" : tone === "bad" ? "v826-bad" : tone === "warn" ? "v826-warn" : "";
    if (!cls) return esc(text);
    return esc(text).replace(/([+\-]\d+(?:\.\d+)?%|\$-?\d+(?:\.\d+)?[KMB]?|-?\d+(?:\.\d+)?x)/g, `<span class="${cls}">$1</span>`);
  }

  function fallbackFacts(row){
    const facts = [];
    if (row?.epsSurprise) {
      const s = row.epsSurprise;
      facts.push({ label:"EPS surprise", tone:s.tone || "neutral", source:"Finnhub company_earnings", text:`EPS surprise ${s.period || "latest"}: actual ${s.actual ?? "—"} vs estimate ${s.estimate ?? "—"}; ${s.surprisePercent == null ? (s.descriptor || "—") : pct(s.surprisePercent)}` });
    }
    facts.push({ label:"Revenue", tone: num(row?.revenueQoQ) > 0 ? "good" : num(row?.revenueQoQ) < 0 ? "bad" : "neutral", source:row?.fundamentalSource, text:`Revenue ${row?.latestQuarter || "latest"}: ${money(row?.revenue)}; QoQ ${pct(row?.revenueQoQ)}, YoY ${pct(row?.revenueYoY)}` });
    facts.push({ label:"Net income", tone: num(row?.profitQoQ) > 0 ? "good" : num(row?.profitQoQ) < 0 ? "bad" : "neutral", source:row?.fundamentalSource, text:`Net income ${row?.latestQuarter || "latest"}: ${money(row?.netIncome)}; QoQ ${pct(row?.profitQoQ)}, YoY ${pct(row?.profitYoY)}` });
    facts.push({ label:"EPS", tone: num(row?.epsQoQ) > 0 ? "good" : num(row?.epsQoQ) < 0 ? "bad" : "neutral", source:row?.fundamentalSource, text:`EPS ${row?.latestQuarter || "latest"}: ${row?.eps ?? "—"}; QoQ ${pct(row?.epsQoQ)}, YoY ${pct(row?.epsYoY)}` });
    facts.push({ label:"FCF", tone: num(row?.freeCashFlow) > 0 ? "good" : num(row?.freeCashFlow) < 0 ? "bad" : "neutral", source:row?.fundamentalSource, text:`Free cash flow ${money(row?.freeCashFlow)}` });
    facts.push({ label:"Margins", tone: num(row?.netMargin) > 0 ? "good" : num(row?.netMargin) < 0 ? "bad" : "neutral", source:row?.fundamentalSource, text:`Margin profile: gross ${pct(row?.grossMargin)}, operating ${pct(row?.operatingMargin)}, net ${pct(row?.netMargin)}` });
    facts.push({ label:"Debt/Equity", tone: num(row?.debtToEquity) <= 0.5 ? "good" : num(row?.debtToEquity) > 1.5 ? "bad" : "warn", source:row?.fundamentalSource, text:`Debt/Equity ${row?.debtToEquity == null ? "—" : Number(row.debtToEquity).toFixed(2)}x` });
    return facts;
  }

  function renderAi(row){
    if (!row) return "";
    const source = row.selectedFundamentalSource || row.fundamentalSource || "Fundamental data";
    const facts = Array.isArray(row.aiViewFacts) && row.aiViewFacts.length ? row.aiViewFacts : fallbackFacts(row);
    const warnings = [];
    if (row.isSamplePlaceholder || /placeholder|sample/i.test(String(row.fundamentalSource || ""))) warnings.push("⚠️ Fundamental data source is sample/static placeholder; rerun the live fundamental workflow before relying on this.");
    if (row.selectedFundamentalReason) warnings.push(`Source selected: ${row.selectedFundamentalSource || "—"} · ${row.selectedFundamentalReason}`);
    const cards = facts.slice(0, 8).map(f => {
      const tone = toneClass(f.tone);
      return `<div class="v826-fact ${tone}"><i class="v826-dot"></i><div><strong>${esc(f.label || "Insight")}</strong> ${colorize(f.text || "—", tone)}<div class="v826-fact-source">ที่มา: ${esc(f.source || source)}</div></div></div>`;
    }).join("");
    return `<section class="v826-ai-card" data-v826-ai-card><div class="v826-ai-layout"><aside><div class="v826-ai-title">AI<br>view</div><button type="button" class="v826-source-toggle" data-v826-source-toggle>แสดงที่มา</button><div class="v826-source-label">${esc(source)}</div></aside><main>${warnings.map(w => `<div class="v826-warning">${esc(w)}</div>`).join("")}<div class="v826-facts">${cards}</div></main></div></section>`;
  }

  function findAiContainers(){
    const candidates = [];
    document.querySelectorAll("section, div, article").forEach(el => {
      if (el.dataset?.v826AiPatched === "1") return;
      if (el.closest("[data-v826-ai-card], .v826-ai-card")) return;
      const text = norm(el.textContent || "");
      if (/\bAI\s*view\b/i.test(text) && /(SEC EDGAR|companyfacts|revenue|net income|EPS|Free cash flow|Debt\/Equity)/i.test(text)) {
        const small = text.length < 5000;
        if (small) candidates.push(el);
      }
    });
    // Prefer the deepest/smallest containers to avoid replacing the whole dashboard.
    return candidates.sort((a,b) => (a.textContent || "").length - (b.textContent || "").length).slice(0, 2);
  }

  function patchAi(){
    loadFundamental().then(data => {
      findAiContainers().forEach(container => {
        const ticker = getTickerFromContext(container);
        const row = rowForTicker(data, ticker);
        if (!row) return;
        container.dataset.v826AiPatched = "1";
        container.innerHTML = renderAi(row);
      });
    });
  }

  const REC_CATS = [["strongBuy","Strong Buy","strong-buy"],["buy","Buy","buy"],["hold","Hold","hold"],["sell","Sell","sell"],["strongSell","Strong Sell","strong-sell"]];
  function periodLabel(period){
    const raw = String(period || "").slice(0,7); const [y,m] = raw.split("-");
    if (!y || !m) return raw || "—";
    const d = new Date(Number(y), Number(m)-1, 1);
    return Number.isNaN(d.getTime()) ? raw : d.toLocaleString("en-US", { month:"short", year:"numeric" });
  }
  function renderRecRows(rows){
    return rows.map(row => {
      const total = Math.max(1, Number(row.total) || REC_CATS.reduce((s,[k]) => s + (Number(row[k]) || 0), 0));
      const segs = REC_CATS.map(([key,label,cls]) => {
        const value = Number(row[key]) || 0; const width = value / total * 100;
        return `<span class="v826-rec-seg ${cls} ${value ? "" : "zero"}" style="width:${width}%" title="${esc(label)}: ${value}">${value > 0 && width >= 8 ? value : ""}</span>`;
      }).join("");
      return `<div class="v826-rec-row"><span class="v826-rec-period">${esc(periodLabel(row.period))}</span><div class="v826-rec-track">${segs}</div><span class="v826-rec-total">${total}</span></div>`;
    }).join("");
  }
  function renderRec(ticker, payload){
    const rows = ((payload?.trends || {})[ticker] || []).slice(-6);
    const generated = payload?.generated_at ? new Date(payload.generated_at).toLocaleString() : "not generated";
    if (!rows.length) return `<section class="v826-rec-section"><div class="v826-rec-head"><strong>${esc(ticker)} Recommendation Trends</strong><span>Finnhub · ${esc(generated)}</span></div><div class="v826-rec-empty">No analyst recommendation data available for this ticker.</div></section>`;
    const legend = REC_CATS.map(([,label,cls]) => `<span><i class="v826-rec-dot ${cls}"></i>${esc(label)}</span>`).join("");
    return `<section class="v826-rec-section"><div class="v826-rec-head"><strong>${esc(ticker)} Recommendation Trends</strong><span>Finnhub · ${esc(generated)} · last 6 periods</span></div><div class="v826-rec-chart">${renderRecRows(rows)}</div><div class="v826-rec-legend">${legend}</div></section>`;
  }
  function findYahooCards(){
    const out = [];
    document.querySelectorAll("section, div, article").forEach(el => {
      if (el.dataset?.v826RecPatched === "1") return;
      if (el.closest(".v826-rec-section")) return;
      const text = norm(el.textContent || "");
      if (/Yahoo Finance Analysis/i.test(text) && /Ticker:\s*[A-Z]/i.test(text) && text.length < 3000) out.push(el);
    });
    return out.sort((a,b) => (a.textContent || "").length - (b.textContent || "").length).slice(0, 3);
  }
  function patchRec(){
    loadRec().then(payload => {
      findYahooCards().forEach(card => {
        const ticker = getTickerFromContext(card);
        if (!ticker) return;
        card.dataset.v826RecPatched = "1";
        const mount = document.createElement("div");
        mount.className = "v826-rec-mount";
        mount.innerHTML = renderRec(ticker, payload || {});
        const firstButton = Array.from(card.querySelectorAll("a,button")).find(x => /Yahoo/i.test(x.textContent || ""));
        const linkRow = firstButton?.parentElement?.parentElement || firstButton?.parentElement;
        card.insertBefore(mount, linkRow || card.lastChild);
      });
    });
  }

  function init(){
    injectStyles();
    const run = () => { patchAi(); patchRec(); };
    run();
    let timer = null;
    const observer = new MutationObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(run, 120);
    });
    observer.observe(document.body, { childList:true, subtree:true });
    document.addEventListener("click", e => {
      const btn = e.target.closest?.("[data-v826-source-toggle]");
      if (!btn) return;
      const card = btn.closest(".v826-ai-card");
      const show = !card.classList.contains("show-sources");
      card.classList.toggle("show-sources", show);
      btn.textContent = show ? "ซ่อนที่มา" : "แสดงที่มา";
    }, true);
    window.__stockcheckV826Refresh = () => { state.fundamental = null; state.rec = null; document.querySelectorAll("[data-v826-ai-patched], [data-v826-rec-patched]").forEach(el => { delete el.dataset.v826AiPatched; delete el.dataset.v826RecPatched; }); run(); };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
