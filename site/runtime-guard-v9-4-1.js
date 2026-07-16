(() => {
  'use strict';
  const VERSION = '9.4.6';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  function recoverNativeUi(){
    for (const selector of ['#sr-dashboard','#sr-v932-layout','#sr-v937-workspace','.sr94-stable-nav','.sr945-primary-nav']) {
      $$(selector).forEach(el => el.remove());
    }
    document.body.classList.remove('sr-dashboard-mounted','sr932-mounted','sr937-mounted','sr936-stable-ui','sr94-stable-ui','sr945-ready');
    for (const selector of ['.app-shell','.topbar','.portfolio-tabs','.workspace','#watchlistPanel','.content-area','#alertCenter','.scanner-panel','#detailPanel','.lower-grid','#memoPage','#attentionPage']) {
      $$(selector).forEach(el => {
        el.classList.remove('sr937-empty-shell','sr936-empty-action-shell','sr936-legacy-action');
        for (const property of ['display','visibility','opacity','width','height','position','inset','transform']) el.style.removeProperty(property);
      });
    }
    window.StockRadarShellV946?.ensureNativeNavigation?.();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', recoverNativeUi, { once:true });
  else recoverNativeUi();
  addEventListener('load', recoverNativeUi, { once:true });
  window.StockRadarRuntimeGuard = { version:VERSION, recover:recoverNativeUi };
})();
