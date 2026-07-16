(() => {
  'use strict';
  const VERSION='9.4.1';
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  function removeLegacyRuntime(){ $('#sr-dashboard')?.remove(); $('#sr-v932-layout')?.remove(); $('#sr-v937-workspace')?.remove(); document.body.classList.remove('sr-dashboard-mounted','sr932-mounted','sr937-mounted','sr936-stable-ui','sr94-stable-ui'); }
  function revealNativeUi(){ for(const selector of ['.app-shell','.topbar','.portfolio-tabs','.workspace','#watchlistPanel','.content-area','#alertCenter','.scanner-panel','#detailPanel','.lower-grid','#memoPage','#attentionPage']){ for(const el of $$(selector)){ el.classList.remove('sr937-empty-shell','sr936-empty-action-shell','sr936-legacy-action'); for(const property of ['display','visibility','opacity','width','height','position','inset','transform']) el.style.removeProperty(property); } } }
  function activateNativeView(view){ const button=$(`[data-app-view="${view}"]`); if(!button)return false; button.click(); return true; }
  function applyHash(){ const hash=location.hash.toLowerCase(); if(hash==='#memo')activateNativeView('memo'); if(hash==='#today')activateNativeView('attention'); if(hash==='#scanner')activateNativeView('scanner'); }
  function recover(){ removeLegacyRuntime(); revealNativeUi(); applyHash(); }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{recover();setTimeout(recover,250);setTimeout(recover,1200)},{once:true});else recover();
  addEventListener('load',recover,{once:true}); addEventListener('hashchange',applyHash); window.StockRadarRuntimeGuard={version:VERSION,recover,activateNativeView};
})();
