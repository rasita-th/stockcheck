(() => {
  'use strict';
  const VERSION = '9.4.2';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  function removeLegacyRuntime() {
    $('#sr-dashboard')?.remove();
    $('#sr-v932-layout')?.remove();
    $('#sr-v937-workspace')?.remove();
    document.body.classList.remove('sr-dashboard-mounted','sr932-mounted','sr937-mounted','sr936-stable-ui','sr94-stable-ui');
  }

  function revealNativeUi() {
    const selectors = ['.app-shell','.topbar','.portfolio-tabs','.workspace','#watchlistPanel','.content-area','#alertCenter','.scanner-panel','#detailPanel','.lower-grid','#memoPage','#attentionPage'];
    for (const selector of selectors) {
      for (const el of $$(selector)) {
        el.classList.remove('sr937-empty-shell','sr936-empty-action-shell','sr936-legacy-action');
        for (const property of ['display','visibility','opacity','width','height','position','inset','transform']) el.style.removeProperty(property);
      }
    }
  }

  function mountMarketPulseInNativeNav() {
    const nav = $('.app-mode-nav');
    const link = $('.market-pulse-launch');
    if (!nav || !link) return false;
    link.classList.add('app-mode-btn','market-mode-btn');
    link.removeAttribute('style');
    link.innerHTML = '<span aria-hidden="true">🌍</span><span>Market Pulse</span>';
    if (link.parentElement !== nav) nav.appendChild(link);
    return true;
  }

  function activateNativeView(view) {
    const button = $(`[data-app-view="${view}"]`);
    if (!button) return false;
    button.click();
    return true;
  }

  function applyHash() {
    const hash = location.hash.toLowerCase();
    if (hash === '#memo') activateNativeView('memo');
    if (hash === '#today') activateNativeView('attention');
    if (hash === '#scanner') activateNativeView('scanner');
  }

  function verifyDataUi() {
    const rows = $('#technicalTableBody');
    const scanner = $('.scanner-panel');
    if (!scanner || !rows) return;
    setTimeout(() => {
      if (!rows.children.length && !$('#v941DataRecoveryNote')) {
        const note = document.createElement('div');
        note.id = 'v941DataRecoveryNote';
        note.className = 'v80-render-error';
        note.innerHTML = '<b>กำลังโหลดข้อมูลสแกนเนอร์</b><br>ถ้ายังว่าง ให้กด Scan Now หนึ่งครั้ง ระบบจะใช้ข้อมูล static ล่าสุดที่ผ่าน validation';
        scanner.prepend(note);
      }
    }, 5000);
  }

  function recover() {
    removeLegacyRuntime();
    revealNativeUi();
    mountMarketPulseInNativeNav();
    applyHash();
    verifyDataUi();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      recover();
      setTimeout(recover, 150);
      setTimeout(recover, 600);
      setTimeout(recover, 1400);
    }, { once: true });
  } else recover();

  addEventListener('load', recover, { once: true });
  addEventListener('hashchange', applyHash);
  const observer = new MutationObserver(() => mountMarketPulseInNativeNav());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.StockRadarRuntimeGuard = { version: VERSION, recover, activateNativeView, mountMarketPulseInNativeNav };
})();
