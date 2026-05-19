/* Stock Timing Radar v8.2.13 runtime
 * - Single Analyst Consensus renderer (fixes NVDASOURCE parser bug)
 * - Live technical day-change strip for mobile/desktop cards
 * - Memo cards join current price from technical.json instead of stale memo snapshot
 * - Freshness hints for static data
 * Browser never sees FINNHUB_API_KEY; it only reads generated JSON.
 */
(function(){
  "use strict";
  const VERSION = "v8.2.13";
  const DATA = {
    technical: "data/technical.json",
    recommendations: "data/recommendation_trends.json",
    eps: "data/eps_surprises.json",
    attention: "data/attention_today.json"
  };
  const state = { technical:null, rec:null, eps:null, attention:null, tickers:new Set(), patched:false };
  const OLD_SELECTORS = [
    ".v8210-rec-section", ".v8211-rec-section", ".v8212-rec-section",
    "[data-v8210-rec-section]", "[data-v8211-rec-section]", "[data-v8212-rec-section]",
    ".stockcheck-rec-section", ".recommendation-trends-card"
  ].join(",");

  function esc(x){ return String(x ?? "").replace(/[&<>\"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
  function norm(x){ return String(x || "").replace(/\s+/g," ").trim(); }
  function money(x){ const n=Number(x); return Number.isFinite(n) ? "$" + n.toLocaleString(undefined,{maximumFractionDigits:n>=1000?2:2,minimumFractionDigits:n<1?4:2}) : "—"; }
  function pct(x){ const n=Number(x); return Number.isFinite(n) ? (n>0?"+":"") + n.toFixed(2) + "%" : "—"; }
  function tone(x){ const n=Number(x); if(!Number.isFinite(n)) return "neutral"; return n>0 ? "good" : n<0 ? "bad" : "neutral"; }
  function upperTicker(x){ return String(x || "").toUpperCase().replace(/[^A-Z0-9.\-]/g,""); }
  function isProbablyTicker(x){ return /^[A-Z0-9]{1,6}([.\-][A-Z0-9]{1,4})?$/.test(upperTicker(x)); }

  function injectStyles(){
    if(document.getElementById("v8212-runtime-style")) return;
    const s=document.createElement("style");
    s.id="v8212-runtime-style";
    s.textContent=`
      .v8212-rec-section{margin:16px 0;padding:18px;border:1px solid rgba(88,166,255,.55);border-radius:18px;background:linear-gradient(135deg,rgba(13,48,89,.38),rgba(13,17,23,.74));box-shadow:0 12px 38px rgba(0,0,0,.22)}
      .v8212-rec-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}.v8212-rec-head strong{font-size:18px;color:#E6EDF3}.v8212-rec-head span{color:#8B949E;font-size:13px;text-align:right}.v8212-rec-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0}.v8212-rec-metric{padding:10px;border-radius:12px;background:rgba(13,17,23,.55);border:1px solid rgba(139,148,158,.22)}.v8212-rec-metric small{display:block;color:#8B949E}.v8212-rec-metric b{display:block;margin-top:4px;font-size:18px}.v8212-rec-metric.good b{color:#3FB950}.v8212-rec-metric.warn b{color:#D29922}.v8212-rec-metric.bad b{color:#F85149}.v8212-rec-chart{display:grid;gap:8px;margin-top:12px}.v8212-rec-row{display:grid;grid-template-columns:72px minmax(0,1fr) 36px;align-items:center;gap:10px;color:#8B949E;font-size:12px}.v8212-rec-track{height:24px;overflow:hidden;border:1px solid rgba(139,148,158,.25);border-radius:999px;display:flex;background:#0D1117}.v8212-rec-seg{height:100%;display:flex;align-items:center;justify-content:center;color:#fff;font:900 10px/1 'IBM Plex Mono',monospace;text-shadow:0 1px 2px rgba(0,0,0,.4)}.v8212-rec-seg.zero{display:none}.v8212-rec-seg.strong-buy{background:#1a7f37}.v8212-rec-seg.buy{background:#3FB950}.v8212-rec-seg.hold{background:#D29922}.v8212-rec-seg.sell{background:#F85149}.v8212-rec-seg.strong-sell{background:#8b0000}.v8212-rec-legend{display:flex;flex-wrap:wrap;gap:7px 12px;margin-top:12px;color:#8B949E;font-size:12px}.v8212-rec-dot{display:inline-block;width:9px;height:9px;border-radius:999px;margin-right:5px}.v8212-rec-dot.strong-buy{background:#1a7f37}.v8212-rec-dot.buy{background:#3FB950}.v8212-rec-dot.hold{background:#D29922}.v8212-rec-dot.sell{background:#F85149}.v8212-rec-dot.strong-sell{background:#8b0000}.v8212-rec-empty{padding:15px;border:1px dashed rgba(139,148,158,.35);border-radius:12px;background:rgba(22,27,34,.45);color:#8B949E;line-height:1.45}.v8212-rec-note{margin-top:10px;color:#8B949E;font-size:12px;line-height:1.4}.v8212-rec-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.v8212-rec-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:8px 12px;border-radius:10px;border:1px solid rgba(88,166,255,.55);color:#58A6FF;text-decoration:none;font-weight:800;background:rgba(13,48,89,.35)}
      .v8212-live-strip{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0 10px;font:800 13px/1.25 'IBM Plex Mono',monospace;color:#8B949E}.v8212-live-strip .price{color:#E6EDF3}.v8212-live-strip .good{color:#3FB950}.v8212-live-strip .bad{color:#F85149}.v8212-live-strip .neutral{color:#8B949E}.v8212-live-pill{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(139,148,158,.25);border-radius:999px;padding:5px 9px;background:rgba(13,17,23,.45)}.v8212-freshness{margin:10px 0;padding:9px 12px;border-radius:12px;border:1px solid rgba(88,166,255,.28);background:rgba(13,48,89,.18);color:#8B949E;font-size:12px}.v8212-freshness.warn{border-color:rgba(210,153,34,.5);background:rgba(210,153,34,.1);color:#D29922}.v8212-memo-live{margin:10px 0;padding:10px 12px;border-radius:14px;border:1px solid rgba(88,166,255,.28);background:rgba(13,48,89,.18);font-size:13px}.v8212-memo-live b{color:#E6EDF3}.v8212-memo-live .good{color:#3FB950}.v8212-memo-live .bad{color:#F85149}.v8212-memo-live .neutral{color:#8B949E}
      @media(max-width:767px){.v8212-rec-section{padding:13px;margin:14px 0 18px}.v8212-rec-head{display:block}.v8212-rec-head span{display:block;text-align:left;margin-top:4px}.v8212-rec-summary{grid-template-columns:1fr}.v8212-rec-row{grid-template-columns:58px minmax(0,1fr) 30px;gap:7px}.v8212-rec-track{height:28px}.v8212-rec-actions a{min-height:44px;flex:1 1 150px}.v8212-live-strip{font-size:12px}}
    `;
    document.head.appendChild(s);
  }
  function loadJSON(url){ return fetch(`${url}?v=${Date.now()}`,{cache:"no-store"}).then(r=>r.ok?r.json():null).catch(()=>null); }
  function loadAll(){
    return Promise.all([loadJSON(DATA.technical), loadJSON(DATA.recommendations), loadJSON(DATA.eps), loadJSON(DATA.attention)]).then(([technical,rec,eps,attention])=>{
      state.technical=technical||{}; state.rec=rec||{}; state.eps=eps||{}; state.attention=attention||{};
      const rows=Array.isArray(state.technical.rows)?state.technical.rows:[];
      rows.forEach(r=>{const t=upperTicker(r.ticker||r.symbol); if(t) state.tickers.add(t);});
      return state;
    });
  }
  function techRow(ticker){
    const t=upperTicker(ticker); const rows=Array.isArray(state.technical?.rows)?state.technical.rows:[];
    return rows.find(r=>upperTicker(r.ticker||r.symbol)===t) || null;
  }
  function rowPrice(r){ return Number(r?.price ?? r?.regularMarketPrice ?? r?.last ?? r?.close); }
  function rowDayPct(r){ return Number(r?.dayPct ?? r?.day_change_pct ?? r?.changePercent ?? r?.regularMarketChangePercent); }
  function rowDayAbs(r){ return Number(r?.dayChange ?? r?.regularMarketChange ?? r?.change); }

  function findKnownTickerIn(raw){
    const s=upperTicker(raw);
    if(!s) return "";
    const sorted=Array.from(state.tickers).sort((a,b)=>b.length-a.length);
    for(const t of sorted){ if(s===t || s.startsWith(t+"SOURCE") || s.startsWith(t+" ") || s.startsWith(t)) return t; }
    return isProbablyTicker(s.replace(/SOURCE$/,"")) ? s.replace(/SOURCE$/,'') : "";
  }
  function tickerFromContext(card){
    const input=document.querySelector('input[value], input[placeholder*="ticker" i], input[placeholder*="symbol" i]');
    if(input && input.value){ const t=findKnownTickerIn(input.value); if(t) return t; }
    const title=norm(document.querySelector('.detail-title,.detail-header,h1,h2,[data-detail-title]')?.textContent||'');
    let m=title.match(/^([A-Z0-9.\-]{1,10})\b/); if(m){ const t=findKnownTickerIn(m[1]); if(t) return t; }
    const text=card?.innerText || card?.textContent || "";
    m=text.match(/Ticker:\s*([^\n\r•]+)/i); if(m){ const t=findKnownTickerIn(m[1]); if(t) return t; }
    const scoped=card?.closest?.('.fundamental-dashboard,.detail-panel,.detail-drawer,.stock-detail,body') || document.body;
    m=norm(scoped.textContent||'').match(/\b([A-Z0-9.\-]{1,10})\s+dashboard\b/i); if(m){ const t=findKnownTickerIn(m[1]); if(t) return t; }
    // Last fallback: if card text contains exactly one known ticker, use it.
    const body=upperTicker(norm(scoped.textContent||''));
    const hits=Array.from(state.tickers).filter(t=>body.includes(t));
    return hits.length===1?hits[0]:"";
  }

  const CATS=[["strongBuy","Strong Buy","strong-buy"],["buy","Buy","buy"],["hold","Hold","hold"],["sell","Sell","sell"],["strongSell","Strong Sell","strong-sell"]];
  function periodLabel(value){ const raw=String(value||"").slice(0,7); const [y,m]=raw.split('-'); if(!y||!m)return raw||'—'; const d=new Date(Number(y),Number(m)-1,1); return Number.isNaN(d.getTime())?raw:d.toLocaleString('en-US',{month:'short',year:'numeric'}); }
  function rowTotal(row){ return CATS.reduce((s,[k])=>s+(Number(row?.[k])||0),0); }
  function scoreRow(row){ const total=rowTotal(row); if(!total)return null; return ((Number(row.strongBuy)||0)*5+(Number(row.buy)||0)*4+(Number(row.hold)||0)*3+(Number(row.sell)||0)*2+(Number(row.strongSell)||0)*1)/total; }
  function consensusLabel(score){ if(score==null)return{label:'—',tone:'neutral'}; if(score>=4.25)return{label:'Strong Buy',tone:'good'}; if(score>=3.55)return{label:'Buy',tone:'good'}; if(score>=2.75)return{label:'Hold',tone:'warn'}; if(score>=2.0)return{label:'Sell',tone:'bad'}; return{label:'Strong Sell',tone:'bad'}; }
  function recRows(ticker){ const t=upperTicker(ticker); const d=state.rec||{}; const direct=d.trends?.[t]||d.data?.[t]||d.recommendations?.[t]||[]; return Array.isArray(direct)?direct.slice().sort((a,b)=>String(a.period||'').localeCompare(String(b.period||''))).slice(-6):[]; }
  function renderBars(rows){ return rows.map(row=>{ const total=Math.max(1,rowTotal(row)); const segs=CATS.map(([key,label,cls])=>{ const value=Number(row[key])||0; const width=value/total*100; return `<span class="v8212-rec-seg ${cls} ${value?'':'zero'}" style="width:${width}%" title="${esc(label)}: ${value}">${value&&width>=9?value:''}</span>`; }).join(''); return `<div class="v8212-rec-row"><span>${esc(periodLabel(row.period))}</span><div class="v8212-rec-track">${segs}</div><span>${total}</span></div>`; }).join(''); }
  function renderRecPanel(ticker){
    const rows=recRows(ticker); const generated=state.rec?.generated_at||state.rec?.generatedAt||state.rec?.updated_at; const latest=rows[rows.length-1]; const score=latest?scoreRow(latest):null; const c=consensusLabel(score); const bullish=latest?((Number(latest.strongBuy)||0)+(Number(latest.buy)||0)):null; const total=latest?rowTotal(latest):null;
    const summary=rows.length?`<div class="v8212-rec-summary"><div class="v8212-rec-metric ${c.tone}"><small>Consensus</small><b>${esc(c.label)}</b></div><div class="v8212-rec-metric"><small>Rating Score</small><b>${score==null?'—':score.toFixed(2)}</b></div><div class="v8212-rec-metric good"><small>Bullish Analysts</small><b>${bullish??'—'}/${total??'—'}</b></div></div>`:'';
    const legend=CATS.map(([,label,cls])=>`<span><i class="v8212-rec-dot ${cls}"></i>${esc(label)}</span>`).join('');
    const body=rows.length?`${summary}<div class="v8212-rec-chart">${renderBars(rows)}</div><div class="v8212-rec-legend">${legend}</div>`:`<div class="v8212-rec-empty">No Finnhub recommendation trend found for ${esc(ticker)} in the generated cache. This can mean the ticker has no Finnhub coverage yet, was skipped by the US/common-stock filter, or is waiting for the slow Finnhub cache refresh.</div>`;
    const meta=state.rec?._meta||{}; const policy=meta.policy||'Unified Finnhub budget; browser never sees FINNHUB_API_KEY.'; const yahoo=`https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}/analysis`;
    return `<section class="v8212-rec-section" data-v8212-rec-section="1"><div class="v8212-rec-head"><strong>${esc(ticker)} Analyst Consensus</strong><span>Finnhub recommendation trends · ${esc(generated?new Date(generated).toLocaleString():'cache')}</span></div>${body}<div class="v8212-rec-note">${esc(policy)}</div><div class="v8212-rec-actions"><a href="${yahoo}" target="_blank" rel="noopener noreferrer">Open Yahoo Analysis ↗</a></div></section>`;
  }
  function patchConsensus(){
    document.querySelectorAll(OLD_SELECTORS).forEach(el=>el.remove());
    const candidates=[];
    document.querySelectorAll('section,article,div').forEach(el=>{
      if(el.dataset.v8212ConsensusPatched==='1') return;
      if(el.closest('.v8212-rec-section')) return;
      const text=norm(el.textContent||'');
      if(!/Yahoo Finance Analysis/i.test(text)) return;
      if(!/Ticker:\s*[A-Z]/i.test(text)) return;
      if(text.length>5000) return;
      candidates.push(el);
    });
    candidates.sort((a,b)=>(a.textContent||'').length-(b.textContent||'').length).slice(0,3).forEach(card=>{
      const ticker=tickerFromContext(card); if(!ticker) return;
      card.dataset.v8212ConsensusPatched='1';
      card.querySelectorAll(OLD_SELECTORS).forEach(el=>el.remove());
      const wrap=document.createElement('div'); wrap.innerHTML=renderRecPanel(ticker); const panel=wrap.firstElementChild;
      const yahooAction=Array.from(card.querySelectorAll('a,button')).find(el=>/Yahoo/i.test(el.textContent||''));
      if(yahooAction && yahooAction.parentElement && yahooAction.parentElement!==card) yahooAction.parentElement.before(panel); else card.appendChild(panel);
    });
  }

  function patchTechnicalCards(){
    const rows=Array.isArray(state.technical?.rows)?state.technical.rows:[]; if(!rows.length) return;
    document.querySelectorAll('section,article,div').forEach(el=>{
      if(el.dataset.v8212TechPatched==='1') return;
      const text=norm(el.textContent||'');
      if(!/EMA5/i.test(text) || !/RSI/i.test(text)) return;
      if(text.length>2500) return;
      let ticker='';
      for(const t of state.tickers){ if(new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}\\b`).test(text)){ ticker=t; break; } }
      if(!ticker) return;
      const r=techRow(ticker); if(!r) return;
      const price=rowPrice(r), dp=rowDayPct(r), da=rowDayAbs(r); if(!Number.isFinite(price)) return;
      const strip=document.createElement('div'); strip.className='v8212-live-strip';
      strip.innerHTML=`<span class="v8212-live-pill"><span>${esc(ticker)}</span><span class="price">${money(price)}</span></span><span class="v8212-live-pill ${tone(dp)}">Today ${pct(dp)}</span>${Number.isFinite(da)?`<span class="v8212-live-pill ${tone(da)}">Day ${money(da)}</span>`:''}`;
      const target=Array.from(el.children).find(c=>/RSI/i.test(c.textContent||'')) || el.firstElementChild;
      if(target) target.after(strip); else el.prepend(strip);
      el.dataset.v8212TechPatched='1';
    });
  }

  function patchMemoCards(){
    document.querySelectorAll('section,article,div').forEach(el=>{
      if(el.dataset.v8212MemoPatched==='1') return;
      const text=norm(el.textContent||'');
      if(!/ACTION PLAN|Action Plan/i.test(text) || !/CURRENT/i.test(text) || !/NOTE/i.test(text)) return;
      if(text.length>4000) return;
      let ticker=''; for(const t of state.tickers){ if(new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}\\b`).test(text)){ ticker=t; break; } }
      if(!ticker) return;
      const r=techRow(ticker); if(!r) return;
      const price=rowPrice(r), dp=rowDayPct(r); if(!Number.isFinite(price)) return;
      const box=document.createElement('div'); box.className='v8212-memo-live';
      box.innerHTML=`Live price: <b>${money(price)}</b> <span class="${tone(dp)}">${pct(dp)} today</span><br><small>Current price is joined from latest technical.json; note price stays as memo snapshot.</small>`;
      const anchor=Array.from(el.children).find(c=>/CURRENT/i.test(c.textContent||'')) || el.firstElementChild;
      if(anchor) anchor.before(box); else el.prepend(box);
      el.dataset.v8212MemoPatched='1';
    });
  }
  function patchFreshness(){
    const updated=state.technical?.generatedAt||state.technical?.generated_at||state.technical?.updated_at;
    if(!updated || document.querySelector('.v8212-freshness')) return;
    const d=new Date(updated); const age=(Date.now()-d.getTime())/60000;
    const cls=Number.isFinite(age)&&age>30?'v8212-freshness warn':'v8212-freshness';
    const el=document.createElement('div'); el.className=cls; el.textContent=`Price data updated: ${Number.isNaN(d.getTime())?updated:d.toLocaleString()}${Number.isFinite(age)?` · ${Math.max(0,Math.round(age))} min ago`:''}`;
    const target=document.querySelector('main,#app,.app-shell,.scanner-results') || document.body;
    target.prepend(el);
  }
  function patchAll(){ injectStyles(); patchConsensus(); patchTechnicalCards(); patchMemoCards(); patchFreshness(); }
  function start(){
    loadAll().then(()=>{ patchAll(); let timer=null; const obs=new MutationObserver(()=>{ clearTimeout(timer); timer=setTimeout(patchAll,250); }); obs.observe(document.body,{childList:true,subtree:true}); console.info(`[Stockcheck ${VERSION}] runtime loaded`); });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();
