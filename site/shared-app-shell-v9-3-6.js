(() => {
  'use strict';
  const VERSION = '9.4.0-stable';
  const $ = (selector, root = document) => root.querySelector(selector);

  function isMarketPage() {
    return /market\.html$/i.test(location.pathname);
  }

  function badgeValue() {
    const text = $('#alertCountPill')?.textContent || '';
    const match = text.match(/\d+/);
    return match ? match[0] : null;
  }

  function action(id, label, icon, href) {
    const element = href ? document.createElement('a') : document.createElement('button');
    if (href) element.href = href;
    else element.type = 'button';
    element.className = 'sr94-nav-action';
    element.dataset.sr94Action = id;
    element.innerHTML = `<span aria-hidden="true">${icon}</span><span>${label}</span>`;
    if ((id === 'market' && isMarketPage()) || (id === 'scanner' && !isMarketPage())) {
      element.setAttribute('aria-current', 'page');
    }
    return element;
  }

  function buildNavigation() {
    const header = $('header.topbar') || $('header');
    if (!header) return;

    document.body.classList.add('sr94-stable-ui');
    $('.market-pulse-launch')?.classList.add('sr94-legacy-market-link');

    let nav = $('.sr94-stable-nav', header);
    if (!nav) {
      nav = document.createElement('nav');
      nav.className = 'sr94-stable-nav';
      nav.setAttribute('aria-label', 'Primary navigation');
      header.appendChild(nav);
    }

    nav.replaceChildren(
      action('scanner', 'Scanner', '◎', isMarketPage() ? 'index.html' : null),
      action('today', 'Today', '📡', null),
      action('memo', 'Memo', '📝', null),
      action('market', 'Market Pulse', '🌍', isMarketPage() ? null : 'market.html')
    );

    const count = badgeValue();
    const today = $('[data-sr94-action="today"]', nav);
    if (today && count) {
      const badge = document.createElement('span');
      badge.className = 'sr94-nav-badge';
      badge.textContent = count;
      today.appendChild(badge);
    }
  }

  function openScanner() {
    if (isMarketPage()) {
      location.assign('index.html');
      return;
    }
    ($('.scanner-panel') || $('#technicalScanner') || $('main'))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function openAlerts(filter) {
    if (isMarketPage()) {
      location.assign(`index.html#${filter}`);
      return;
    }
    const button = $(`[data-alert-filter="${filter}"]`);
    if (button) button.click();
    $('#alertCenter')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function handleAction(id) {
    if (id === 'scanner') openScanner();
    if (id === 'today') openAlerts('all');
    if (id === 'memo') openAlerts('memo');
  }

  function openHash() {
    const hash = location.hash.toLowerCase();
    if (hash === '#today') openAlerts('all');
    if (hash === '#memo') openAlerts('memo');
  }

  document.addEventListener('click', event => {
    const control = event.target.closest('[data-sr94-action]');
    if (!control) return;
    const id = control.dataset.sr94Action;
    if (control.tagName === 'A' && control.getAttribute('href')) return;
    event.preventDefault();
    handleAction(id);
  });

  function mount() {
    buildNavigation();
    openHash();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();
  window.addEventListener('load', buildNavigation, { once: true });
  window.addEventListener('hashchange', openHash);

  const observer = new MutationObserver(() => {
    const nav = $('.sr94-stable-nav');
    const today = nav && $('[data-sr94-action="today"]', nav);
    const count = badgeValue();
    const badge = today && $('.sr94-nav-badge', today);
    if (today && count && !badge) {
      const next = document.createElement('span');
      next.className = 'sr94-nav-badge';
      next.textContent = count;
      today.appendChild(next);
    } else if (badge && count) {
      badge.textContent = count;
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  window.StockRadarStableNavigation = { version: VERSION, mount };
})();
