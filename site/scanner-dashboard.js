(() => {
  'use strict';
  const VERSION = '9.3.0';
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => [...r.querySelectorAll(s)];
  const clamp = (v,a,b) => Math.max(a,Math.min(b,v));
  const num = v => { const m=String(v??'').replace(/,/g,'').match(/-?\d+(?:\.\d+)?/); return m?Number(m[0]):null; };
  const esc = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function arrangeHeader(){
    const market=$('a[href$="market.html"]'); if(!market) return;
    const memo=$('a[href*="memo"],button[data-action="memo"],.memo-link');
    const action=memo?.parentElement || $('.header-actions,.top-nav,.nav-actions');
    if(action && market.parentElement!==action) action.insertBefore(market,memo?.nextSibling||null);
    market.classList.add('market-pulse-link');
  }

  function selectedListName(){
    const active=$('.portfolio-tab.active,.watchlist-tab.active,.tab.active,[aria-selected="true"]');
    return (active?.textContent||'Current List').replace(/\s+/g,' ').trim();
  }

  function rowCandidates(){
    return $$('[data-symbol],tr,.stock-row,.result-row,.stock-card').filter(el=>!el.closest('#sr-dashboard'));
  }

  function tickerFrom(el){
    const d=el.dataset?.symbol||el.getAttribute?.('data-ticker'); if(d) return d.trim().toUpperCase();
    const preferred=$('.symbol,.ticker,.stock-symbol,[class*="symbol"]',el)?.textContent||'';
    const text=(preferred||el.textContent||'').toUpperCase();
    const hits=text.match(/\b[A-Z][A-Z0-9.\-]{0,5}\b/g)||[];
    const ban=new Set(['EMA','SCORE','PRICE','TODAY','MEMO','PORT','DEFAULT','HIGH','QUALITY','BUY','SELL','STRONG','WEAK','THAI','NEW','USD']);
    return hits.find(x=>!ban.has(x))||'';
  }

  function parseRow(el){
    const symbol=tickerFrom(el); if(!symbol) return null;
    const text=(el.textContent||'').replace(/\s+/g,' ');
    const score=num(el.dataset?.score||$('.score,[class*="score"]',el)?.textContent);
    const emaEl=$('[data-ema-distance],.ema-distance,[class*="ema-distance"],[class*="distance"]',el);
    let ema=num(emaEl?.dataset?.emaDistance||emaEl?.textContent);
    if(ema==null){ const m=text.match(/(?:EMA[^+\-\d]{0,20})?([+\-]\d+(?:\.\d+)?)%/i); ema=m?Number(m[1]):null; }
    const company=$('.company,.company-name,.name,[class*="company"]',el)?.textContent?.trim()||'';
    const rs=num(el.dataset?.relativeStrength||$('.relative-strength,.rs,[class*="relative"]',el)?.textContent);
    return {symbol,company,rawScore:score,ema:ema??0,rs:rs??0};
  }

  function collectStocks(){
    const seen=new Set(), out=[];
    for(const el of rowCandidates()){
      const x=parseRow(el); if(!x||seen.has(x.symbol)) continue;
      if(!/^[A-Z][A-Z0-9.\-]{0,5}$/.test(x.symbol)) continue;
      seen.add(x.symbol); out.push(x);
    }
    return out.slice(0,150);
  }

  function enrich(stocks){
    if(!stocks.length) return [];
    const ema=[...stocks].sort((a,b)=>a.ema-b.ema);
    const rs=[...stocks].sort((a,b)=>a.rs-b.rs);
    const pct=(arr,x,key)=>arr.length<2?50:100*arr.findIndex(v=>v===x)/(arr.length-1);
    return stocks.map(s=>{
      const calculated=Math.round(.55*pct(ema,s,'ema')+.45*pct(rs,s,'rs'));
      const score=clamp(Number.isFinite(s.rawScore)?s.rawScore:calculated,0,100);
      const tone=score>=75?'good':score>=55?'mid':'weak';
      const trend=s.ema>3?'▁▂▃▅▆▇':s.ema>=0?'▃▂▄▃▅▄':'▆▅▄▃▂▁';
      const tag=score>=80?'List Leader':score>=65?'Improving':score>=50?'Neutral':'Weak vs List';
      return {...s,score,tone,trend,tag};
    }).sort((a,b)=>b.score-a.score).map((s,i)=>({...s,rank:i+1}));
  }

  function themeFor(symbol){
    const maps={Semiconductors:['NVDA','AMD','AVGO','TSM','MU','ARM','INTC'],Software:['MSFT','ORCL','NOW','PLTR','CRM','ADBE'],Space:['RKLB','ASTS','LUNR','RDW'],Fintech:['HOOD','SOFI','PYPL','COIN'],Uranium:['UUUU','CCJ','LEU','OKLO'],Biotech:['RXRX','BEAM','CRSP','TEM'],Defense:['LMT','RTX','NOC','KTOS']};
    return Object.entries(maps).find(([,xs])=>xs.includes(symbol))?.[0]||'Other';
  }
  function summaries(rows){
    const above=rows.filter(x=>x.ema>0).length,total=rows.length,breadth=total?Math.round(100*above/total):0;
    const groups={}; rows.forEach(x=>{const t=themeFor(x.symbol);(groups[t]??=[]).push(x.score)});
    const themes=Object.entries(groups).filter(([k])=>k!=='Other').map(([name,v])=>({name,score:Math.round(v.reduce((a,b)=>a+b,0)/v.length)})).sort((a,b)=>b.score-a.score);
    return {total,above,below:total-above,breadth,strong:rows.filter(x=>x.score>=75).length,themes};
  }

  function themeRows(themes){
    const defaultThemes=['Semiconductors','Software','Defense','Uranium','Biotech','Space','Fintech'];
    const map=new Map(themes.map(x=>[x.name,x.score]));
    return defaultThemes.map(name=>({name,score:map.get(name)??0})).map(x=>{
      const on=Math.round(x.score/12.5),tone=x.score>=75?'sr-positive':x.score>=50?'sr-warning':'sr-negative';
      const label=x.score>=80?'Very Strong':x.score>=65?'Strong':x.score>=45?'Moderate':x.score>0?'Weak':'No data';
      return `<div class="sr-theme-row"><span>${esc(x.name)}</span><span class="sr-segments ${tone}">${Array.from({length:8},(_,i)=>`<i class="${i<on?'on':''}"></i>`).join('')}</span><span class="sr-strength ${tone}">${label}</span></div>`;
    }).join('');
  }

  function tableRows(rows){return rows.slice(0,10).map(x=>`<tr><td><span class="sr-rank">${x.rank}</span></td><td><span class="sr-symbol">${esc(x.symbol)}</span><span class="sr-company">${esc(x.company||'')}</span></td><td><span class="sr-score ${x.tone}">${Math.round(x.score)}</span></td><td class="${x.ema>=0?'sr-positive':'sr-negative'}"><strong>${x.ema>=0?'+':''}${x.ema.toFixed(1)}%</strong><div class="sr-meter"><i style="width:${clamp(Math.abs(x.ema)*5,4,100)}%"></i></div></td><td class="${x.rs>=0?'sr-positive':'sr-negative'}"><strong>${x.rs>=0?'+':''}${x.rs.toFixed(2)}</strong></td><td><span class="sr-trend ${x.ema>=0?'sr-positive':'sr-negative'}">${x.trend}</span></td><td><span class="sr-tag ${x.tone==='weak'?'weak':x.tone==='mid'?'mid':''}">${x.tag}</span></td></tr>`).join('')}
  function mobileRows(rows){return rows.slice(0,10).map(x=>`<article class="sr-mobile-stock"><div><span class="sr-symbol">#${x.rank} ${esc(x.symbol)}</span><span class="sr-company">${esc(x.company||'Compared within this basket')}</span><div class="sr-mobile-metrics"><span>EMA ${x.ema>=0?'+':''}${x.ema.toFixed(1)}%</span><span>RS ${x.rs>=0?'+':''}${x.rs.toFixed(2)}</span><span>${x.tag}</span></div></div><span class="sr-score ${x.tone}">${Math.round(x.score)}</span></article>`).join('')}

  function render(){
    arrangeHeader();
    const stocks=enrich(collectStocks()), s=summaries(stocks), list=selectedListName();
    let root=$('#sr-dashboard'); if(!root){root=document.createElement('section');root.id='sr-dashboard'; const anchor=$('main,.main-content,#app-main,.content')||document.body.firstElementChild; anchor.parentNode.insertBefore(root,anchor); document.body.classList.add('sr-dashboard-mounted');}
    const empty=!stocks.length;
    root.innerHTML=`<div class="sr-dashboard-grid"><div class="sr-main"><section class="sr-card"><div class="sr-card-head"><div><div style="display:flex;gap:9px;align-items:center;flex-wrap:wrap"><h2 class="sr-card-title">Outstanding in Current List</h2><span class="sr-basket-badge">Compared within selected basket</span></div><p class="sr-card-subtitle">Top outliers in “${esc(list)}” ranked relative to the other names in this list.</p></div><div class="sr-sort">Sorted by Score ↓</div></div>${empty?`<div class="sr-empty"><strong>No scanner rows detected yet</strong>Run or open the list scanner; this dashboard will rank its visible results automatically.</div>`:`<div class="sr-table-wrap"><table class="sr-table"><thead><tr><th>#</th><th>Symbol</th><th>Score</th><th>Distance from EMA</th><th>Relative Strength</th><th>Trend</th><th>Notes / Tags</th></tr></thead><tbody>${tableRows(stocks)}</tbody></table></div><div class="sr-mobile-list">${mobileRows(stocks)}</div>`}<div class="sr-card-foot"><span>Scanned ${s.total} names in “${esc(list)}”</span><span>Ranks describe this list—not a standalone stock recommendation.</span></div></section><section class="sr-card"><div class="sr-card-head"><div><h3 class="sr-card-title">Why these names stand out</h3><p class="sr-card-subtitle">Signals are interpreted relative to the selected basket.</p></div></div><div class="sr-reasons"><div class="sr-reason"><div class="sr-reason-icon">⚡</div><h4>Stronger Momentum</h4><p>Positive price acceleration and stronger positioning versus the list median.</p></div><div class="sr-reason"><div class="sr-reason-icon">↗</div><h4>Improving Position</h4><p>Distance from EMA is improving while the price trend remains constructive.</p></div><div class="sr-reason"><div class="sr-reason-icon">◉</div><h4>Breadth Support</h4><p>${s.breadth}% of scanned names are above EMA, giving context to individual strength.</p></div><div class="sr-reason"><div class="sr-reason-icon">◎</div><h4>Relative Outliers</h4><p>High ranks identify unusual strength inside this basket, not across the whole market.</p></div></div></section></div><aside class="sr-sidebar"><section class="sr-card"><div class="sr-card-head"><h3 class="sr-card-title">Scan Summary</h3></div><div class="sr-summary"><div class="sr-stat"><div class="sr-stat-label">Stocks scanned</div><div class="sr-stat-value">${s.total}</div></div><div class="sr-stat"><div class="sr-stat-label">Above EMA</div><div class="sr-stat-value sr-positive">${s.above} <small>(${s.breadth}%)</small></div></div><div class="sr-stat"><div class="sr-stat-label">Outstanding zone</div><div class="sr-stat-value sr-positive">${s.strong}</div></div><div class="sr-stat"><div class="sr-stat-label">Below EMA</div><div class="sr-stat-value sr-negative">${s.below}</div></div></div><div class="sr-breadth"><div class="sr-breadth-row"><span>Breadth (Above EMA)</span><strong>${s.breadth}%</strong></div><div class="sr-breadth-track"><i class="sr-breadth-marker" style="left:${clamp(s.breadth,0,100)}%"></i></div></div></section><section class="sr-card"><div class="sr-card-head"><div><h3 class="sr-card-title">Cluster / Theme Strength</h3><p class="sr-card-subtitle">Average rank strength inside the current list.</p></div></div><div class="sr-theme-list">${themeRows(s.themes)}</div></section><section class="sr-card sr-market-card"><div class="sr-card-head"><div><h3 class="sr-card-title">Scanner Context</h3><p class="sr-card-subtitle">The dashboard remains list-first by design.</p></div></div><div class="sr-context"><div class="sr-context-item"><span class="sr-context-symbol">Breadth</span><span class="sr-context-change sr-positive">${s.breadth}%</span><div class="sr-context-line">▁▂▃▅▆▇</div></div><div class="sr-context-item"><span class="sr-context-symbol">Leaders</span><span class="sr-context-change sr-positive">${s.strong}</span><div class="sr-context-line">▂▃▄▆▇▇</div></div><div class="sr-context-item"><span class="sr-context-symbol">Median</span><span class="sr-context-change">50</span><div class="sr-context-line">▃▄▃▅▄▅</div></div><div class="sr-context-item"><span class="sr-context-symbol">Weak</span><span class="sr-context-change sr-negative">${s.below}</span><div class="sr-context-line sr-negative">▇▆▅▄▃▂</div></div></div></section></aside></div>`;
  }

  let timer; const schedule=()=>{clearTimeout(timer);timer=setTimeout(render,220)};
  document.addEventListener('DOMContentLoaded',()=>{render();new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class','aria-selected']});});
  window.addEventListener('load',schedule); document.addEventListener('click',e=>{if(e.target.closest('.portfolio-tab,.watchlist-tab,.tab'))setTimeout(render,120)});
  window.StockRadarDashboard={version:VERSION,refresh:render};
})();
