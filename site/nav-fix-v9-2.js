/* v9.2.3 — attach Market Pulse to the same action group as Memo. */
(() => {
  const clean = (value) => (value || '').replace(/\s+/g, ' ').trim().toLowerCase();

  function findByHrefOrText(hrefPattern, textPattern) {
    const candidates = [...document.querySelectorAll('a, button')];
    return candidates.find((el) => {
      const href = clean(el.getAttribute('href'));
      const text = clean(el.textContent);
      return hrefPattern.test(href) || textPattern.test(text);
    });
  }

  function attachMarketPulse() {
    const market = findByHrefOrText(/(^|\/)market\.html(?:[?#].*)?$/, /market\s*pulse/);
    const memo = findByHrefOrText(/(^|\/)(memo|notes?)\.html(?:[?#].*)?$/, /(^|\s)memo(\s|$)/);

    if (!market || !memo || market === memo) return false;

    const actions = memo.parentElement;
    if (!actions) return false;

    actions.classList.add('stockradar-header-actions');
    market.classList.add('market-pulse-link', 'stockradar-market-pulse-link');

    /* Neutralize legacy floating styles, including inline declarations. */
    for (const property of [
      'position', 'top', 'right', 'bottom', 'left', 'inset',
      'transform', 'translate', 'float', 'z-index', 'margin'
    ]) {
      market.style.removeProperty(property);
    }

    /* Put Market Pulse immediately after Memo in the real DOM flow. */
    if (memo.nextElementSibling !== market || market.parentElement !== actions) {
      memo.insertAdjacentElement('afterend', market);
    }

    return true;
  }

  function boot() {
    if (attachMarketPulse()) return;

    /* Some pages build the header after initial load. Retry briefly. */
    const observer = new MutationObserver(() => {
      if (attachMarketPulse()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    window.setTimeout(() => observer.disconnect(), 6000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
