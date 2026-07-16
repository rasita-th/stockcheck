(() => {
  'use strict';
  const VERSION = '9.4.5';
  const $ = (selector, root = document) => root.querySelector(selector);

  function isMarketPage() {
    return /market\.html$/i.test(location.pathname);
  }

  function readAlertCount() {
    const text = $('#alertCountPill')?.textContent || '';
    const match = text.match(/\d+/);
    return match ? match[0] : null;
  }

  function makeAction(id, label, icon, href) {
    const element = href ? document.createElement('a') : document.createElement('button');
    if (href) element.href = href;
    else element.type = 'button';
    element.className = 'sr945-nav-action';
    element.dataset.sr945Action = id;
    element.innerHTML = `<span aria-hidden="true">${icon}</span><span>${label}</span>`;
    if ((id === 'market' && isMarketPage()) || (id === 'scanner' && !isMarketPage())) {
      element.setAttribute('aria-current', 'page');
    }
    return element;
  }

  function buildNavigation() {
    const header = $('header.topbar') || $('header');
    if (!header) return false;

    document.body.classList.add('sr945-ready');
    $('.market-pulse-launch')?.classList.add('sr945-legacy-market-link');
    $('.sr94-stable-nav')?.remove();
    $('.app-mode-nav')?.remove();

    let nav = $('.sr945-primary-nav', header);
    if (!nav) {
      nav = document.createElement('nav');
      nav.className = 'sr945-primary-nav';
      nav.setAttribute('aria-label', 'Primary navigation');
      header.appendChild(nav);
    }

    nav.replaceChildren(
      makeAction('scanner', 'Scanner', '◎', isMarketPage() ? 'index.html#scanner' : null),
      makeAction('today', 'Today', '📡', isMarketPage() ? 'index.html#today' : null),
      makeAction('memo', 'Memo', '📝', isMarketPage() ? 'index.html#memo' : null),
      makeAction('market', 'Market Pulse', '🌍', isMarketPage() ? null : 'market.html')
    );

    updateBadge();
    return true;
  }

  function updateBadge() {
    const nav = $('.sr945-primary-nav');
    const today = nav && $('[data-sr945-action="today"]', nav);
    if (!today) return;
    const count = readAlertCount();
    let badge = $('.sr945-nav-badge', today);
    if (!count) {
      badge?.remove();
      return;
    }
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'sr945-nav-badge';
      today.appendChild(badge);
    }
    badge.textContent = count;
  }

  function clickNativeView(view) {
    const control = $(`[data-app-view="${view}"]`);
    if (!control) return false;
    control.click();
    return true;
  }

  function openScanner() {
    if (isMarketPage()) {
      location.assign('index.html#scanner');
      return;
    }
    if (!clickNativeView('scanner')) {
      ($('.scanner-panel') || $('#technicalScanner') || $('main'))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function openToday() {
    if (isMarketPage()) {
      location.assign('index.html#today');
      return;
    }
    if (!clickNativeView('attention')) {
      $('[data-alert-filter="all"]')?.click();
      $('#alertCenter')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function openMemo() {
    if (isMarketPage()) {
      location.assign('index.html#memo');
      return;
    }
    if (!clickNativeView('memo')) {
      $('[data-alert-filter="memo"]')?.click();
      $('#alertCenter')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function applyHash() {
    const hash = location.hash.toLowerCase();
    if (hash === '#today') openToday();
    else if (hash === '#memo') openMemo();
    else if (hash === '#scanner') openScanner();
  }

  document.addEventListener('click', event => {
    const control = event.target.closest('[data-sr945-action]');
    if (!control) return;
    const id = control.dataset.sr945Action;
    if (control.tagName === 'A' && control.getAttribute('href')) return;
    event.preventDefault();
    if (id === 'scanner') openScanner();
    else if (id === 'today') openToday();
    else if (id === 'memo') openMemo();
  });

  function mount() {
    buildNavigation();
    applyHash();
    setTimeout(updateBadge, 600);
    setTimeout(updateBadge, 1800);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();
  addEventListener('load', mount, { once: true });
  addEventListener('hashchange', applyHash);

  const observer = new MutationObserver(updateBadge);
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  window.StockRadarStableNavigation = { version: VERSION, mount, openScanner, openToday, openMemo };
})();
