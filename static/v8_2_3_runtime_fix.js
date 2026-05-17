/* Stock Timing Radar v8.2.3 Runtime Fix
   - Recommendation Trends: robust ticker parsing + chart injection
   - AI view: rebuilds detailed AI bullets from generated fundamental.json
   Static-site safe: no API key is exposed in the browser. */
(function stockcheckV823RuntimeFix(){
  const FUND_URL = 'data/fundamental.json';
  const REC_URL = 'data/recommendation_trends.json';
  const REC_CATEGORIES = [
    ['strongBuy', 'Strong Buy', 'strong-buy'],
    ['buy', 'Buy', 'buy'],
    ['hold', 'Hold', 'hold'],
    ['sell', 'Sell', 'sell'],
    ['strongSell', 'Strong Sell', 'strong-sell'],
  ];
  let fundPayload = null;
  let fundLoading = null;
  let recPayload = null;
  let recLoading = null;
  let observer = null;
  let scheduled = false;

  const esc = (value) => String(value ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[c]));
  const norm = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();
  const num = (value) => { const n = Number(value); return Number.isFinite(n) ? n : 0; };
  const has = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const pct = (value) => has(value) ? `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(2)}%` : 'N/A';
  const eps = (value) => has(value) ? Number(value).toFixed(3) : 'N/A';
  const money = (value) => {
    if (!has(value)) return 'N/A';
    const n = Number(value);
    const abs = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    const a = Math.abs(n);
    if (abs >= 1e12) return `${sign}$${(a / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `${sign}$${(a / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${sign}$${(a / 1e6).toFixed(2)}M`;
    return `${sign}$${a.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  };
  const cleanTicker = (raw) => String(raw || '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9.\-].*$/, '')
    .replace(/SOURCE$/, '')
    .replace(/YAHOO$/, '')
    .slice(0, 12);

  function injectStyles(){
    if (document.getElementById('stockcheckV823RuntimeStyles')) return;
    const style = document.createElement('style');
    style.id = 'stockcheckV823RuntimeStyles';
    style.textContent = `
      .v823-ai-card{border:1px solid rgba(88,166,255,.42)!important;background:linear-gradient(135deg,rgba(31,111,235,.16),rgba(13,17,23,.92))!important;border-radius:16px!important;padding:16px 18px!important;margin-top:16px!important;color:#E6EDF3!important}
      .v823-ai-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}.v823-ai-head strong{font-size:18px}.v823-ai-head span{font-size:12px;color:#8B949E;text-align:right}.v823-ai-card ul{margin:0;padding-left:20px;display:grid;gap:9px}.v823-ai-card li{line-height:1.45}.v823-ai-warn{color:#D29922;font-weight:800}
      .recommendation-section{margin:14px 0 16px;padding:16px;border:1px solid #30363D;border-radius:16px;background:rgba(13,17,23,.42)}
      .rec-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}.rec-head strong{font-size:16px;color:#E6EDF3}.rec-head span{font-size:12px;color:#8B949E;text-align:right}
      .rec-chart{display:grid;gap:10px;margin-top:10px}.rec-row{display:grid;grid-template-columns:74px minmax(0,1fr) 42px;gap:10px;align-items:center}.rec-period{font:700 12px/1.1 'IBM Plex Mono',monospace;color:#8B949E}.rec-total{font:700 12px/1 'IBM Plex Mono',monospace;color:#8B949E;text-align:right}
      .rec-track{display:flex;height:30px;overflow:hidden;border-radius:10px;background:#0D1117;border:1px solid rgba(48,54,61,.7)}.rec-seg{min-width:0;height:100%;display:flex;align-items:center;justify-content:center;font:800 11px/1 'IBM Plex Mono',monospace;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.35)}.rec-seg.zero{display:none}
      .rec-seg.strong-buy{background:#1a7f37}.rec-seg.buy{background:#3FB950}.rec-seg.hold{background:#D29922}.rec-seg.sell{background:#F85149}.rec-seg.strong-sell{background:#8b0000}
      .rec-legend{display:flex;flex-wrap:wrap;gap:8px 12px;margin:12px 0 0;color:#8B949E;font-size:12px}.rec-legend span{display:inline-flex;align-items:center;gap:6px}.rec-dot{width:10px;height:10px;border-radius:99px;display:inline-block}.rec-dot.strong-buy{background:#1a7f37}.rec-dot.buy{background:#3FB950}.rec-dot.hold{background:#D29922}.rec-dot.sell{background:#F85149}.rec-dot.strong-sell{background:#8b0000}
      .rec-summary-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}.rec-summary-item{padding:10px;border:1px solid rgba(48,54,61,.8);border-radius:12px;background:#161B22}.rec-summary-item .label{display:block;font-size:11px;color:#8B949E;margin-bottom:4px}.rec-summary-item .value{display:block;font:800 14px/1.2 'IBM Plex Mono',monospace;color:#E6EDF3}.rec-summary-item .value.green{color:#3FB950}.rec-summary-item .value.muted{color:#8B949E}
      .rec-empty,.rec-error,.rec-loading{padding:18px;border:1px dashed #30363D;border-radius:12px;color:#8B949E;text-align:center;background:rgba(22,27,34,.45)}.rec-error{color:#ffaaa5;border-color:rgba(248,81,73,.45)}.rec-loading{background:linear-gradient(90deg,#161B22 25%,#1c2230 50%,#161B22 75%);background-size:200% 100%;animation:recShimmer 1.5s infinite}@keyframes recShimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
      @media(max-width:767px){.v823-ai-card{padding:14px!important}.v823-ai-head{display:block}.v823-ai-head span{display:block;text-align:left;margin-top:4px}.recommendation-section{padding:13px;margin-bottom:18px}.rec-head{display:block}.rec-head span{display:block;text-align:left;margin-top:4px}.rec-row{grid-template-columns:58px minmax(0,1fr) 34px;gap:7px}.rec-track{height:28px}.rec-summary-row{grid-template-columns:repeat(2,minmax(0,1fr))}}
    `;
    document.head.appendChild(style);
  }

  function loadFundData(){
    if (fundPayload) return Promise.resolve(fundPayload);
    if (!fundLoading) {
      fundLoading = fetch(`${FUND_URL}?v=${Date.now()}`, { cache: 'no-store' })
        .then(r => r.ok ? r.json() : Promise.reject(new Error(`fundamental.json HTTP ${r.status}`)))
        .then(data => (fundPayload = data))
        .catch(err => (fundPayload = { rows: [], fundamentals: {}, _error: err.message }));
    }
    return fundLoading;
  }

  function loadRecData(){
    if (recPayload) return Promise.resolve(recPayload);
    if (!recLoading) {
      recLoading = fetch(`${REC_URL}?v=${Date.now()}`, { cache: 'no-store' })
        .then(r => r.ok ? r.json() : Promise.reject(new Error(`recommendation_trends.json HTTP ${r.status}`)))
        .then(data => (recPayload = data))
        .catch(err => (recPayload = { generated_at: null, trends: {}, errors: { _load: err.message }, api_key_present: false }));
    }
    return recLoading;
  }

  function rowsFromFund(data){
    const rows = Array.isArray(data?.rows) ? data.rows : [];
    if (rows.length) return rows;
    const funds = data?.fundamentals || {};
    return Object.values(funds).map(x => x?.latest || x?.fundamental || x).filter(Boolean);
  }

  function getTickerFromContext(root){
    const dashboard = root?.closest?.('.fundamental-dashboard') || document.querySelector('.fundamental-dashboard');
    const note = dashboard?.querySelector?.('.note')?.textContent || dashboard?.textContent || '';
    let m = note.match(/\b([A-Z0-9.\-]{1,8})\s+dashboard\b/i);
    if (m) return cleanTicker(m[1]);

    const detailTicker = document.querySelector('.detail-identity h2')?.textContent?.trim();
    if (detailTicker) return cleanTicker(detailTicker);

    const text = norm(root?.textContent || '');
    m = text.match(/Ticker\s*:\s*([A-Z0-9.\-]+)/i);
    if (m) return cleanTicker(m[1]);
    m = text.match(/^\s*([A-Z0-9.\-]{1,8})\b/);
    if (m) return cleanTicker(m[1]);
    return '';
  }

  function findFundRow(data, ticker){
    ticker = cleanTicker(ticker);
    if (!ticker) return null;
    const rows = rowsFromFund(data);
    return rows.find(r => cleanTicker(r.ticker || r.symbol) === ticker) || null;
  }

  function buildAiReasons(row, data){
    row = row || {};
    const original = Array.isArray(row.fundamentalReasons) ? row.fundamentalReasons.filter(Boolean) : [];
    const source = String(row.fundamentalSource || data?.source || 'SEC EDGAR companyfacts + submissions');
    const isSample = /sample|placeholder|static preview/i.test(source) || original.some(x => /sample|placeholder|static preview/i.test(String(x)));
    const src = isSample ? 'Static/sample placeholder detected in fundamental.json — rerun the fundamental data workflow for live SEC EDGAR data' : source;
    const period = row.latestQuarter || row.periodEnd || row.period || 'latest period';
    const reasons = [];

    if (isSample) reasons.push(`<span class="v823-ai-warn">⚠️ Fundamental data source is sample/static placeholder; this is a preview, not live SEC data.</span>`);
    if (has(row.revenue)) {
      const prev = has(row.revenuePrevQuarter) ? ` จาก ${money(row.revenuePrevQuarter)} เป็น ${money(row.revenue)}` : ` อยู่ที่ ${money(row.revenue)}`;
      reasons.push(`Revenue ${period}${prev}; QoQ ${pct(row.revenueQoQ)}, YoY ${pct(row.revenueYoY)} — ที่มา: ${src}`);
    } else if (has(row.revenueQoQ) || has(row.revenueYoY)) {
      reasons.push(`Revenue trend: QoQ ${pct(row.revenueQoQ)}, YoY ${pct(row.revenueYoY)} — ที่มา: ${src}`);
    }
    if (has(row.netIncome)) {
      const prev = has(row.netIncomePrevQuarter) ? ` จาก ${money(row.netIncomePrevQuarter)} เป็น ${money(row.netIncome)}` : ` อยู่ที่ ${money(row.netIncome)}`;
      reasons.push(`Net income ${period}${prev}; QoQ ${pct(row.profitQoQ)}, YoY ${pct(row.profitYoY)} — ที่มา: ${src}`);
    }
    if (has(row.eps)) {
      const prev = has(row.epsPrevQuarter) ? ` จาก ${eps(row.epsPrevQuarter)} เป็น ${eps(row.eps)}` : ` อยู่ที่ ${eps(row.eps)}`;
      reasons.push(`EPS ${period}${prev}; QoQ ${pct(row.epsQoQ)}, YoY ${pct(row.epsYoY)} — ที่มา: ${src}`);
    }
    if (has(row.freeCashFlow)) reasons.push(`Free cash flow ${money(row.freeCashFlow)} — ที่มา: ${src}`);
    const margins = [];
    if (has(row.grossMargin)) margins.push(`gross margin ${pct(row.grossMargin)}`);
    if (has(row.operatingMargin)) margins.push(`operating margin ${pct(row.operatingMargin)}`);
    if (has(row.netMargin)) margins.push(`net margin ${pct(row.netMargin)}`);
    if (margins.length) reasons.push(`Margin profile: ${margins.join(', ')} — ที่มา: ${src}`);
    if (has(row.debtToEquity)) reasons.push(`Debt/Equity ${Number(row.debtToEquity).toFixed(2)}x — ที่มา: ${src}`);
    if (has(row.priorCompanyGuidanceRevenue) || has(row.nextCompanyGuidanceRevenue)) {
      const parts = [];
      if (has(row.priorCompanyGuidanceRevenue)) parts.push(`prior guide ${money(row.priorCompanyGuidanceRevenue)} (${row.priorCompanyGuidanceRevenuePeriod || 'N/A'})`);
      if (has(row.nextCompanyGuidanceRevenue)) parts.push(`next guide ${money(row.nextCompanyGuidanceRevenue)} (${row.nextCompanyGuidanceRevenuePeriod || 'N/A'})`);
      reasons.push(`Company guidance context: ${parts.join('; ')} — ที่มา: ${src}`);
    }
    const cleanOriginal = original.filter(x => !/sample bundled|static preview|placeholder/i.test(String(x)));
    if (reasons.length < 3 && cleanOriginal.length) reasons.push(...cleanOriginal.map(esc));
    return reasons.length ? reasons : ['ยังไม่มี fundamental detail เพียงพอจาก data layer ปัจจุบัน'];
  }

  function findAiCards(){
    const cards = new Set();
    const candidates = Array.from(document.querySelectorAll('h1,h2,h3,h4,strong,b,span,div'));
    candidates.forEach(h => {
      if (norm(h.textContent).toLowerCase() !== 'ai view') return;
      let el = h.parentElement;
      for (let i = 0; el && i < 8 && el !== document.body; i++, el = el.parentElement) {
        const text = norm(el.textContent);
        if (!text.includes('AI view')) continue;
        if (text.includes('FUNDAMENTAL DASHBOARD')) continue;
        if (text.length > 2600) continue;
        if (/(SEC|revenue|sample|placeholder|ที่มา|YoY|QoQ)/i.test(text)) {
          cards.add(el);
          break;
        }
      }
    });
    return Array.from(cards);
  }

  function enhanceAiViews(){
    const cards = findAiCards();
    if (!cards.length) return;
    loadFundData().then(data => {
      cards.forEach(card => {
        const ticker = getTickerFromContext(card);
        const row = findFundRow(data, ticker);
        if (!ticker || !row) return;
        if (card.dataset.v823AiTicker === ticker) return;
        const source = esc(row.fundamentalSource || data?.source || 'SEC EDGAR companyfacts + submissions');
        const reasons = buildAiReasons(row, data);
        card.classList.add('v823-ai-card');
        card.dataset.v823AiTicker = ticker;
        card.innerHTML = `<div class="v823-ai-head"><strong>AI view</strong><span>${source}</span></div><ul>${reasons.map(r => `<li>${r}</li>`).join('')}</ul>`;
      });
    });
  }

  function periodLabel(period){
    const raw = String(period || '').slice(0, 7);
    const [year, month] = raw.split('-');
    if (!year || !month) return raw || '—';
    const d = new Date(Number(year), Number(month) - 1, 1);
    if (Number.isNaN(d.getTime())) return raw;
    return d.toLocaleString('en-US', { month: 'short', year: 'numeric' });
  }

  function latestSummary(rows){
    const d = rows[rows.length - 1] || {};
    const total = REC_CATEGORIES.reduce((sum, [key]) => sum + num(d[key]), 0);
    if (!total) return { label: '—', score: '—', bullish: '—', period: periodLabel(d.period) };
    const bullish = num(d.strongBuy) + num(d.buy);
    const scoreNum = ((num(d.strongBuy) * 2 + num(d.buy) - num(d.sell) - num(d.strongSell) * 2) / total);
    const label = scoreNum > 1.5 ? 'Strong Buy' : scoreNum > 0.5 ? 'Buy' : scoreNum > -0.5 ? 'Hold' : scoreNum > -1.5 ? 'Sell' : 'Strong Sell';
    return { label, score: `${scoreNum.toFixed(2)} / 2.00`, bullish: `${bullish} / ${total} (${Math.round((bullish / total) * 100)}%)`, period: periodLabel(d.period) };
  }

  function renderRecRows(rows){
    return rows.map(row => {
      const total = Math.max(1, num(row.total) || REC_CATEGORIES.reduce((s, [key]) => s + num(row[key]), 0));
      const segs = REC_CATEGORIES.map(([key, label, cls]) => {
        const value = num(row[key]);
        const width = (value / total) * 100;
        return `<span class="rec-seg ${cls} ${value ? '' : 'zero'}" style="width:${width}%" title="${esc(label)}: ${value}">${value > 0 && width >= 8 ? value : ''}</span>`;
      }).join('');
      return `<div class="rec-row"><span class="rec-period">${esc(periodLabel(row.period))}</span><div class="rec-track">${segs}</div><span class="rec-total">${total}</span></div>`;
    }).join('');
  }

  function renderRecSection(ticker, data){
    const rows = ((data.trends || {})[ticker] || []).slice(-6);
    const generated = data.generated_at ? new Date(data.generated_at).toLocaleString() : 'not generated';
    if (!rows.length) {
      const reason = data.api_key_present === false ? 'Finnhub API key is missing. Add FINNHUB_API_KEY secret and rerun Generate Attention List.' : (data.errors?.[ticker] || data.errors?._load || 'No analyst recommendation data available for this ticker.');
      return `<section class="recommendation-section"><div class="rec-head"><strong>${esc(ticker)} Recommendation Trends</strong><span>Finnhub · ${esc(generated)}</span></div><div class="rec-empty">${esc(reason)}</div></section>`;
    }
    const summary = latestSummary(rows);
    const legend = REC_CATEGORIES.map(([, label, cls]) => `<span><i class="rec-dot ${cls}"></i>${esc(label)}</span>`).join('');
    return `<section class="recommendation-section"><div class="rec-head"><strong>${esc(ticker)} Recommendation Trends</strong><span>Finnhub · ${esc(generated)} · last 6 periods</span></div><div class="rec-chart">${renderRecRows(rows)}</div><div class="rec-legend">${legend}</div><div class="rec-summary-row"><div class="rec-summary-item"><span class="label">Consensus</span><span class="value green">${esc(summary.label)}</span></div><div class="rec-summary-item"><span class="label">Rating Score</span><span class="value">${esc(summary.score)}</span></div><div class="rec-summary-item"><span class="label">Bullish Analysts</span><span class="value green">${esc(summary.bullish)}</span></div><div class="rec-summary-item"><span class="label">Period</span><span class="value muted">${esc(summary.period)}</span></div></div></section>`;
  }

  function isYahooAnalysisBlock(el){
    if (!el || el.dataset?.v823RecScanned === '1') return false;
    const txt = norm(el.textContent);
    return /Yahoo Finance Analysis/i.test(txt) && /Open Yahoo Analysis/i.test(txt) && /Ticker\s*:/i.test(txt) && !txt.includes('Recommendation Trends');
  }

  function findYahooCards(){
    const direct = Array.from(document.querySelectorAll('.yahoo-analysis-card'));
    const fallback = Array.from(document.querySelectorAll('.target-section, .insight-card, section, article, div')).filter(isYahooAnalysisBlock);
    return [...new Set([...direct, ...fallback])];
  }

  function patchRecommendationCards(){
    const cards = findYahooCards();
    if (!cards.length) return;
    cards.forEach(card => { card.dataset.v823RecScanned = '1'; });
    loadRecData().then(data => {
      cards.forEach(card => {
        if (card.dataset.v823RecPatched === '1') return;
        const ticker = getTickerFromContext(card);
        if (!ticker) return;
        card.dataset.v823RecPatched = '1';
        const mount = document.createElement('div');
        mount.className = 'recommendation-mount';
        mount.innerHTML = renderRecSection(ticker, data || {});
        const linkRow = card.querySelector('.link-row');
        card.insertBefore(mount, linkRow || card.firstChild);
      });
    });
  }

  function run(){
    scheduled = false;
    injectStyles();
    enhanceAiViews();
    patchRecommendationCards();
  }

  function schedule(){
    if (scheduled) return;
    scheduled = true;
    setTimeout(run, 80);
  }

  function init(){
    run();
    observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    window.__stockcheckV823Refresh = function(){
      fundPayload = null; fundLoading = null; recPayload = null; recLoading = null;
      document.querySelectorAll('.recommendation-mount').forEach(x => x.remove());
      document.querySelectorAll('[data-v823-rec-patched], [data-v823-rec-scanned]').forEach(card => {
        card.dataset.v823RecPatched = '';
        card.dataset.v823RecScanned = '';
      });
      document.querySelectorAll('[data-v823-ai-ticker]').forEach(card => { card.dataset.v823AiTicker = ''; });
      run();
    };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
