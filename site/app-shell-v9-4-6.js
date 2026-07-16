(() => {
  'use strict';
  const VERSION = '9.4.6';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  let recoveryAttempted = false;

  function isMarketPage(){ return /market\.html$/i.test(location.pathname); }

  function removeLegacyArtifacts(){
    for (const selector of ['#sr-dashboard','#sr-v932-layout','#sr-v937-workspace','.sr94-stable-nav','.sr945-primary-nav']) {
      $$(selector).forEach(el => el.remove());
    }
    document.body.classList.remove('sr-dashboard-mounted','sr932-mounted','sr937-mounted','sr936-stable-ui','sr94-stable-ui','sr945-ready');
    const legacy = $('.market-pulse-launch');
    if (legacy) legacy.hidden = true;
  }

  function makeButton(view, icon, label){
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'app-mode-btn';
    button.dataset.appView = view;
    button.innerHTML = `<span aria-hidden="true">${icon}</span><span>${label}</span>`;
    return button;
  }

  function makeMarketLink(){
    const link = document.createElement('a');
    link.className = 'app-mode-btn market-mode-btn';
    link.href = 'market.html';
    link.innerHTML = '<span aria-hidden="true">🌍</span><span>Market Pulse</span>';
    return link;
  }

  function ensureNativeNavigation(){
    if (isMarketPage()) return false;
    const header = $('header.topbar');
    if (!header) return false;
    let nav = $('.app-mode-nav', header) || $('.app-mode-nav');
    if (!nav) {
      nav = document.createElement('nav');
      nav.className = 'app-mode-nav';
      nav.setAttribute('aria-label','Primary navigation');
      header.appendChild(nav);
    }
    nav.classList.add('stable-primary-nav');

    let scanner = $('[data-app-view="scanner"]', nav);
    if (!scanner) scanner = makeButton('scanner','◎','Scanner');
    let today = $('[data-app-view="attention"]', nav);
    if (!today) today = makeButton('attention','📡','Today');
    today.classList.add('attention-mode-btn');
    if (!$('#attentionNavBadge', today)) {
      const badge = document.createElement('span');
      badge.className = 'attention-nav-badge';
      badge.id = 'attentionNavBadge';
      badge.hidden = true;
      badge.textContent = '0';
      today.appendChild(badge);
    }
    let memo = $('[data-app-view="memo"]', nav);
    if (!memo) memo = makeButton('memo','📝','Memo');
    let market = $('a.market-mode-btn', nav) || $('a[href$="market.html"]', nav);
    if (!market) market = makeMarketLink();
    market.classList.add('app-mode-btn','market-mode-btn');
    market.href = 'market.html';

    nav.replaceChildren(scanner,today,memo,market);
    return true;
  }

  function setActive(view){
    $$('.app-mode-nav [data-app-view]').forEach(btn => btn.classList.toggle('active', btn.dataset.appView === view));
    const market = $('.app-mode-nav .market-mode-btn');
    market?.classList.remove('active');
  }

  function activateView(view){
    if (isMarketPage()) {
      location.assign(`index.html#${view === 'attention' ? 'today' : view}`);
      return;
    }
    ensureNativeNavigation();
    const control = $(`[data-app-view="${view}"]`);
    if (!control) return false;
    control.click();
    setActive(view);
    return true;
  }

  function applyHash(){
    const hash = location.hash.toLowerCase();
    if (hash === '#today') activateView('attention');
    else if (hash === '#memo') activateView('memo');
    else if (hash === '#scanner') activateView('scanner');
  }

  function ensureStatus(){
    let status = $('#sr946Status');
    if (status) return status;
    status = document.createElement('div');
    status.id = 'sr946Status';
    status.setAttribute('role','status');
    const header = $('header.topbar');
    (header?.parentElement || document.body).insertBefore(status, header?.nextSibling || null);
    return status;
  }

  function showStatus(message, retry = false){
    const status = ensureStatus();
    status.classList.add('show');
    status.innerHTML = `<span>${message}</span>${retry ? '<button type="button" data-sr946-retry>Retry loading</button>' : ''}`;
  }

  function hideStatus(){ $('#sr946Status')?.classList.remove('show'); }

  function renderedDataCount(){
    return ($('#technicalTableBody')?.children.length || 0) + ($('#technicalMobileCards')?.children.length || 0) + ($('#fundamentalTableBody')?.children.length || 0);
  }

  async function verifyDataAndRecover(force = false){
    if (isMarketPage()) return;
    if (renderedDataCount() > 0) { hideStatus(); return; }
    if (recoveryAttempted && !force) return;
    recoveryAttempted = true;
    showStatus('กำลังตรวจสอบข้อมูลสแกนเนอร์…');
    try {
      const response = await fetch(`data/technical.json?v=${Date.now()}`, { cache:'no-store' });
      if (!response.ok) throw new Error(`technical.json HTTP ${response.status}`);
      const payload = await response.json();
      if (!Array.isArray(payload?.rows) || payload.rows.length === 0) throw new Error('technical.json has no rows');
      if (typeof window.loadStaticData === 'function') await window.loadStaticData({ message:'Reloading validated static data…' });
      else if (typeof window.scan === 'function') await window.scan(false);
      else $('#scanNowDesktop')?.click();
      if (typeof window.renderAll === 'function') window.renderAll();
      setTimeout(() => {
        if (renderedDataCount() > 0) hideStatus();
        else showStatus('ไฟล์ข้อมูลมีอยู่ แต่ UI ยัง render ไม่สำเร็จ กรุณากด Retry loading', true);
      }, 1200);
    } catch (error) {
      console.error('[v9.4.6] data recovery failed', error);
      showStatus(`โหลดข้อมูลไม่สำเร็จ: ${error.message || error}`, true);
    }
  }

  function boot(){
    removeLegacyArtifacts();
    ensureNativeNavigation();
    applyHash();
    setTimeout(ensureNativeNavigation, 100);
    setTimeout(ensureNativeNavigation, 700);
    setTimeout(() => verifyDataAndRecover(false), 4500);
  }

  document.addEventListener('click', event => {
    if (event.target.closest('[data-sr946-retry]')) {
      event.preventDefault();
      recoveryAttempted = false;
      verifyDataAndRecover(true);
    }
  });
  window.addEventListener('error', event => {
    const source = String(event.filename || '');
    if (source.includes('app.js') || source.includes('app-shell')) showStatus(`JavaScript error: ${event.message || 'unknown error'}`, true);
  });
  window.addEventListener('unhandledrejection', event => {
    console.error('[v9.4.6] unhandled rejection', event.reason);
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once:true });
  else boot();
  addEventListener('load', () => { ensureNativeNavigation(); applyHash(); }, { once:true });
  addEventListener('hashchange', applyHash);

  window.StockRadarShellV946 = { version:VERSION, boot, ensureNativeNavigation, verifyDataAndRecover, activateView };
})();
