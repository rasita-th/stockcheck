(() => {
  'use strict';
  const VERSION = '9.3.5';
  const PANEL = 'section,article,.card,.panel,[class*="card"],[class*="panel"],[class*="widget"],[class*="box"]';
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();

  function visible(el) {
    if (!el || !el.isConnected) return false;
    const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden';
  }

  function panelFromNode(node) {
    if (!node) return null;
    let panel = node.closest(PANEL) || node.parentElement;
    while (panel?.parentElement && panel.getBoundingClientRect().height < 85) {
      panel = panel.parentElement.closest(PANEL) || panel.parentElement;
    }
    return panel;
  }

  function panelByText(terms, reject = []) {
    const nodes = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,[class*="title"],[class*="heading"],button,legend')];
    const node = nodes.find(el => {
      if (!visible(el) || el.closest('#sr-v932-layout')) return false;
      const text = norm(el.textContent);
      return terms.some(term => text.includes(term)) && !reject.some(term => text.includes(term));
    });
    return panelFromNode(node);
  }

  function detailPanel() {
    const exactPanel = panelByText(['price / ema','price/ema','selected stock detail','selected stock','price and ema'], ['scanner results']);
    if (exactPanel) return exactPanel;

    const tab = [...document.querySelectorAll('button,a,[role="tab"]')].find(el => {
      if (!visible(el) || el.closest('#sr-v932-layout')) return false;
      const text = norm(el.textContent);
      if (!(text === 'technical' || text.includes('fundamental') || text.includes('playbook') || text.includes('candles') || text.includes('line'))) return false;
      const panel = panelFromNode(el);
      if (!panel) return false;
      const panelText = norm(panel.textContent);
      return !panelText.includes('scanner results');
    });
    let panel = panelFromNode(tab);
    if (panel && panel.getBoundingClientRect().width < 280) panel = panel.parentElement;
    return panel;
  }

  function arrangeHeader() {
    const market = document.querySelector('a[href$="market.html"]');
    const memo = document.querySelector('a[href*="memo"],button[data-action="memo"],.memo-link');
    const actions = memo?.parentElement || document.querySelector('.header-actions,.top-nav,.nav-actions');
    if (market && actions && market.parentElement !== actions) actions.insertBefore(market, memo?.nextSibling || null);
    market?.classList.add('market-pulse-link');
  }

  function unique(items) {
    return [...new Set(items.filter(Boolean))];
  }

  function cleanShells(parents) {
    parents.forEach(parent => {
      if (!parent || parent === document.body || parent.id === 'sr-v932-layout') return;
      const meaningful = [...parent.children].some(child => {
        if (child.matches('script,style,#sr-v932-layout')) return false;
        return visible(child) && (child.textContent.trim() || child.children.length);
      });
      if (!meaningful) parent.classList.add('sr-v932-empty-shell');
    });
  }

  function move(panel, zone, className) {
    if (!panel || !zone || panel.closest('#sr-v932-layout')) return;
    panel.classList.add(className);
    zone.appendChild(panel);
  }

  function mount() {
    arrangeHeader();
    if (document.getElementById('sr-v932-layout')) return;

    const filters = panelByText(['scan filters']);
    const detail = detailPanel();
    const watch = panelByText(['watchlist']);
    const alerts = panelByText(['alert center']);
    const results = panelByText(['scanner results']);
    const ai = panelByText(['ai view']);
    const fundamentals = panelByText(['fundamental snapshot','fundamentals'], ['fundamental playbook']);

    if (!results && !alerts && !detail) return;

    const panels = unique([filters, detail, watch, alerts, results, ai, fundamentals]);
    const oldParents = new Set(panels.map(panel => panel.parentElement));

    const layout = document.createElement('main');
    layout.id = 'sr-v932-layout';
    layout.dataset.version = VERSION;
    layout.innerHTML = `
      <section class="sr-v932-scan-zone"></section>
      <section class="sr-v932-monitor-zone"></section>
      <section class="sr-v932-results-zone"></section>
      <section class="sr-v932-analysis-zone"></section>`;

    const first = panels[0];
    const root = first?.closest('main,.main-content,#app-main,.content,.app-content') || first;
    if (!root) return;
    root.parentNode.insertBefore(layout, root.nextSibling);

    const scanZone = layout.querySelector('.sr-v932-scan-zone');
    const monitorZone = layout.querySelector('.sr-v932-monitor-zone');
    const resultsZone = layout.querySelector('.sr-v932-results-zone');
    const analysisZone = layout.querySelector('.sr-v932-analysis-zone');

    move(filters, scanZone, 'sr-v932-filters');
    move(detail, scanZone, 'sr-v932-detail');
    move(watch, monitorZone, 'sr-v932-watchlist');
    move(alerts, monitorZone, 'sr-v932-alerts');
    move(results, resultsZone, 'sr-v932-results');
    move(fundamentals, analysisZone, 'sr-v932-fundamentals');
    move(ai, analysisZone, 'sr-v932-ai');

    if (!scanZone.children.length) scanZone.remove();
    if (!monitorZone.children.length) monitorZone.remove();
    if (!resultsZone.children.length) resultsZone.remove();
    if (!analysisZone.children.length) analysisZone.remove();

    cleanShells(oldParents);
    document.body.classList.add('sr-v932-mounted');
  }

  let timer;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(mount, 220);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule);
  else schedule();
  window.addEventListener('load', schedule);
  new MutationObserver(schedule).observe(document.documentElement, {childList:true, subtree:true});
  window.StockRadarNoDeadSpace = {version: VERSION, refresh: mount};
})();
