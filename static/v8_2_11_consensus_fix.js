/* Stock Timing Radar v8.2.11
   Analyst Consensus ticker parser fix + safe Finnhub cache renderer.
   Browser-safe: reads generated JSON only. No API key in frontend. */
(function stockcheckV8211ConsensusFix(){
  const VERSION = "8.2.11";
  const DATA_URL = "data/recommendation_trends.json";
  const state = { data:null, loading:null };
  const esc = (v) => String(v ?? "").replace(/[&<>\"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#039;"}[c]));
  const norm = (v) => String(v ?? "").replace(/\s+/g, " ").trim();

  function injectStyles(){
    if (document.getElementById("stockcheckV8211ConsensusStyles")) return;
    const s = document.createElement("style");
    s.id = "stockcheckV8211ConsensusStyles";
    s.textContent = `
      .v8211-rec-section{margin:16px 0 18px;padding:16px;border:1px solid rgba(88,166,255,.42);border-radius:16px;background:linear-gradient(135deg,rgba(13,48,89,.28),rgba(13,17,23,.72));box-shadow:0 10px 30px rgba(0,0,0,.18)}
      .v8211-rec-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}.v8211-rec-head strong{font-size:16px;color:#E6EDF3}.v8211-rec-head span{font-size:12px;color:#8B949E;text-align:right}.v8211-rec-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:13px}.v8211-rec-metric{border:1px solid rgba(48,54,61,.8);border-radius:12px;background:rgba(13,17,23,.5);padding:10px}.v8211-rec-metric small{display:block;color:#8B949E;font-size:11px;margin-bottom:4px}.v8211-rec-metric b{color:#E6EDF3;font:900 16px/1.2 'IBM Plex Mono',monospace}.v8211-rec-metric.good b{color:#3FB950}.v8211-rec-metric.warn b{color:#D29922}.v8211-rec-metric.bad b{color:#F85149}.v8211-rec-chart{display:grid;gap:10px}.v8211-rec-row{display:grid;grid-template-columns:70px minmax(0,1fr) 36px;gap:10px;align-items:center}.v8211-rec-period,.v8211-rec-total{font:800 11px/1.1 'IBM Plex Mono',monospace;color:#8B949E}.v8211-rec-total{text-align:right}.v8211-rec-track{height:28px;border:1px solid rgba(48,54,61,.8);border-radius:10px;overflow:hidden;display:flex;background:#0D1117}.v8211-rec-seg{height:100%;display:flex;align-items:center;justify-content:center;color:#fff;font:900 10px/1 'IBM Plex Mono',monospace;text-shadow:0 1px 2px rgba(0,0,0,.4)}.v8211-rec-seg.zero{display:none}.v8211-rec-seg.strong-buy{background:#1a7f37}.v8211-rec-seg.buy{background:#3FB950}.v8211-rec-seg.hold{background:#D29922}.v8211-rec-seg.sell{background:#F85149}.v8211-rec-seg.strong-sell{background:#8b0000}.v8211-rec-legend{display:flex;flex-wrap:wrap;gap:7px 12px;margin-top:12px;color:#8B949E;font-size:12px}.v8211-rec-dot{display:inline-block;width:9px;height:9px;border-radius:999px;margin-right:5px}.v8211-rec-dot.strong-buy{background:#1a7f37}.v8211-rec-dot.buy{background:#3FB950}.v8211-rec-dot.hold{background:#D29922}.v8211-rec-dot.sell{background:#F85149}.v8211-rec-dot.strong-sell{background:#8b0000}.v8211-rec-empty{padding:15px;border:1px dashed rgba(139,148,158,.35);border-radius:12px;background:rgba(22,27,34,.45);color:#8B949E;line-height:1.45}.v8211-rec-note{margin-top:10px;color:#8B949E;font-size:12px;line-height:1.4}.v8211-rec-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.v8211-rec-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:8px 12px;border-radius:10px;border:1px solid rgba(88,166,255,.55);color:#58A6FF;text-decoration:none;font-weight:800;background:rgba(13,48,89,.35)}
      @media(max-width:767px){.v8211-rec-section{padding:13px;margin:14px 0 18px}.v8211-rec-head{display:block}.v8211-rec-head span{display:block;text-align:left;margin-top:4px}.v8211-rec-summary{grid-template-columns:1fr}.v8211-rec-row{grid-template-columns:58px minmax(0,1fr) 30px;gap:7px}.v8211-rec-track{height:28px}.v8211-rec-actions a{min-height:44px;flex:1 1 150px}}
    `;
    document.head.appendChild(s);
  }

  function loadData(){
    if (state.data) return Promise.resolve(state.data);
    if (!state.loading) {
      state.loading = fetch(`${DATA_URL}?v=${Date.now()}`, { cache:"no-store" })
        .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
        .then(d => (state.data = d))
        .catch(err => {
          console.warn(`[Stockcheck ${VERSION}] recommendation_trends load failed`, err);
          state.data = { _error:String(err), trends:{} };
          return state.data;
        });
    }
    return state.loading;
  }

  function normalizeTicker(raw){
    let t = String(raw || "").toUpperCase().trim();
    // Fix the old DOM text-join bug: "Ticker: NVDA" + "Source" became NVDASOURCE.
    t = t.replace(/SOURCE$/i, "");
    t = t.replace(/[^A-Z0-9.\-]/g, "");
    return t;
  }

  function getTicker(card){
    const text = norm(card?.textContent || "");
    const after = text.split(/Ticker:\s*/i)[1];
    if (after) {
      const beforeSource = after.replace(/Source\s*:.*/i, "").replace(/Source.*/i, "");
      const m = beforeSource.match(/([A-Z0-9.\-]{1,12})/i);
      const ticker = normalizeTicker(m && m[1]);
      if (ticker) return ticker;
    }
    let m = text.match(/Ticker:\s*([A-Z0-9.\-]{1,12})(?=\s*(?:Source|$))/i);
    if (m) {
      const ticker = normalizeTicker(m[1]);
      if (ticker) return ticker;
    }
    const scope = card?.closest?.(".fundamental-dashboard,.detail-panel,.detail-drawer,.stock-detail,body") || document.body;
    const scoped = norm(scope.textContent || "");
    m = scoped.match(/\b([A-Z0-9.\-]{1,12})\s+dashboard\b/i);
    if (m) {
      const ticker = normalizeTicker(m[1]);
      if (ticker) return ticker;
    }
    m = norm(document.querySelector(".detail-identity h2,[data-detail-title],h1,h2")?.textContent || "").match(/^([A-Z0-9.\-]{1,12})\b/);
    return normalizeTicker(m && m[1]);
  }

  function findCards(){
    const cards = [];
    document.querySelectorAll("section,article,div").forEach(el => {
      if (el.dataset?.v8211RecPatched === "1") return;
      if (el.closest(".v8211-rec-section")) return;
      const text = norm(el.textContent || "");
      if (!/Yahoo Finance Analysis/i.test(text)) return;
      if (!/Ticker:\s*[A-Z]/i.test(text)) return;
      if (text.length > 4200) return;
      cards.push(el);
    });
    return cards.sort((a,b) => (a.textContent || "").length - (b.textContent || "").length).slice(0, 4);
  }

  const CATS = [["strongBuy","Strong Buy","strong-buy"],["buy","Buy","buy"],["hold","Hold","hold"],["sell","Sell","sell"],["strongSell","Strong Sell","strong-sell"]];
  function periodLabel(value){
    const raw = String(value || "").slice(0, 7);
    const [y,m] = raw.split("-");
    if (!y || !m) return raw || "—";
    const d = new Date(Number(y), Number(m)-1, 1);
    return Number.isNaN(d.getTime()) ? raw : d.toLocaleString("en-US", { month:"short", year:"numeric" });
  }
  function rowTotal(row){ return CATS.reduce((s,[k]) => s + (Number(row?.[k]) || 0), 0); }
  function scoreRow(row){
    const total = rowTotal(row);
    if (!total) return null;
    return ((Number(row.strongBuy)||0)*5 + (Number(row.buy)||0)*4 + (Number(row.hold)||0)*3 + (Number(row.sell)||0)*2 + (Number(row.strongSell)||0)*1) / total;
  }
  function consensusLabel(score){
    if (score == null) return { label:"—", tone:"neutral" };
    if (score >= 4.25) return { label:"Strong Buy", tone:"good" };
    if (score >= 3.55) return { label:"Buy", tone:"good" };
    if (score >= 2.75) return { label:"Hold", tone:"warn" };
    if (score >= 2.0) return { label:"Sell", tone:"bad" };
    return { label:"Strong Sell", tone:"bad" };
  }
  function normalizeRows(payload, ticker){
    const t = String(ticker || "").toUpperCase();
    const direct = payload?.trends?.[t] || payload?.data?.[t] || payload?.recommendations?.[t];
    const arr = Array.isArray(direct) ? direct : [];
    return arr.slice().sort((a,b) => String(a.period || "").localeCompare(String(b.period || ""))).slice(-6);
  }
  function renderRows(rows){
    return rows.map(row => {
      const total = Math.max(1, rowTotal(row));
      const segs = CATS.map(([key,label,cls]) => {
        const value = Number(row[key]) || 0;
        const width = value / total * 100;
        return `<span class="v8211-rec-seg ${cls} ${value ? "" : "zero"}" style="width:${width}%" title="${esc(label)}: ${value}">${value && width >= 9 ? value : ""}</span>`;
      }).join("");
      return `<div class="v8211-rec-row"><span class="v8211-rec-period">${esc(periodLabel(row.period))}</span><div class="v8211-rec-track">${segs}</div><span class="v8211-rec-total">${total}</span></div>`;
    }).join("");
  }
  function renderPanel(ticker, payload){
    const rows = normalizeRows(payload, ticker);
    const generated = payload?.generated_at || payload?.generatedAt || payload?.updated_at;
    const latest = rows[rows.length - 1];
    const score = latest ? scoreRow(latest) : null;
    const consensus = consensusLabel(score);
    const bullish = latest ? ((Number(latest.strongBuy)||0) + (Number(latest.buy)||0)) : null;
    const total = latest ? rowTotal(latest) : null;
    const summary = rows.length ? `<div class="v8211-rec-summary"><div class="v8211-rec-metric ${consensus.tone}"><small>Consensus</small><b>${esc(consensus.label)}</b></div><div class="v8211-rec-metric"><small>Rating Score</small><b>${score == null ? "—" : score.toFixed(2)}</b></div><div class="v8211-rec-metric good"><small>Bullish Analysts</small><b>${bullish ?? "—"}/${total ?? "—"}</b></div></div>` : "";
    const legend = CATS.map(([,label,cls]) => `<span><i class="v8211-rec-dot ${cls}"></i>${esc(label)}</span>`).join("");
    const body = rows.length
      ? `${summary}<div class="v8211-rec-chart">${renderRows(rows)}</div><div class="v8211-rec-legend">${legend}</div>`
      : `<div class="v8211-rec-empty">No Finnhub recommendation trend found for ${esc(ticker)} in the generated cache. This usually means the ticker was skipped, outside US common-stock coverage, or the cache has not refreshed yet.</div>`;
    const yahoo = `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}/analysis`;
    return `<section class="v8211-rec-section" data-v8211-rec-section="1"><div class="v8211-rec-head"><strong>${esc(ticker)} Analyst Consensus</strong><span>Finnhub recommendation trends · ${esc(generated ? new Date(generated).toLocaleString() : "cache")}</span></div>${body}<div class="v8211-rec-note">Cache policy: one unified Finnhub budget across fundamentals, EPS surprise, and recommendation trends. Browser never sees the API key.</div><div class="v8211-rec-actions"><a href="${yahoo}" target="_blank" rel="noopener noreferrer">Open Yahoo Analysis ↗</a></div></section>`;
  }
  function patch(){
    injectStyles();
    loadData().then(payload => {
      findCards().forEach(card => {
        // Remove previous buggy panels, including the NVDASOURCE renderer.
        card.querySelectorAll(".v8210-rec-section,.v8211-rec-section,[data-v8210-rec-section],[data-v8211-rec-section]").forEach(el => el.remove());
        const ticker = getTicker(card);
        if (!ticker) return;
        card.dataset.v8211RecPatched = "1";
        const panel = document.createElement("div");
        panel.innerHTML = renderPanel(ticker, payload);
        const actions = Array.from(card.querySelectorAll("a,button")).find(el => /Yahoo/i.test(el.textContent || ""));
        const section = panel.firstElementChild;
        if (actions && actions.parentElement && actions.parentElement !== card) actions.parentElement.before(section);
        else card.appendChild(section);
      });
    });
  }
  function start(){
    patch();
    let timer = null;
    const observer = new MutationObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        document.querySelectorAll("[data-v8211-rec-patched='1']").forEach(el => { if (!document.body.contains(el)) return; });
        patch();
      }, 200);
    });
    observer.observe(document.body, { childList:true, subtree:true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once:true }); else start();
})();
