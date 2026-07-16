(() => {
  'use strict';
  const VERSION='9.3.1';
  const PANEL_SELECTOR='section,article,.card,.panel,[class*="card"],[class*="panel"]';
  const norm=s=>String(s||'').replace(/\s+/g,' ').trim().toLowerCase();

  function headingPanel(patterns){
    const nodes=[...document.querySelectorAll('h1,h2,h3,h4,h5,[class*="title"],[class*="heading"]')];
    const heading=nodes.find(n=>patterns.some(p=>norm(n.textContent).includes(p)) && !n.closest('#sr-v931-layout'));
    if(!heading) return null;
    let panel=heading.closest(PANEL_SELECTOR);
    if(!panel) panel=heading.parentElement;
    /* Avoid selecting a tiny title wrapper. */
    while(panel?.parentElement && panel.getBoundingClientRect().height<90){panel=panel.parentElement.closest(PANEL_SELECTOR)||panel.parentElement}
    return panel;
  }

  function arrangeHeader(){
    const market=document.querySelector('a[href$="market.html"]');
    const memo=document.querySelector('a[href*="memo"],button[data-action="memo"],.memo-link');
    const actions=memo?.parentElement||document.querySelector('.header-actions,.top-nav,.nav-actions');
    if(market&&actions&&market.parentElement!==actions) actions.insertBefore(market,memo?.nextSibling||null);
    market?.classList.add('market-pulse-link');
  }

  function cleanOldParents(parents){
    parents.forEach(p=>{
      if(!p||p.id==='sr-v931-layout'||p===document.body) return;
      const visible=[...p.children].filter(x=>!x.matches('script,style')&&!x.classList.contains('sr-v931-emptied'));
      const meaningful=visible.some(x=>x.textContent.trim()||x.children.length);
      if(!meaningful || p.children.length===0) p.classList.add('sr-v931-emptied');
    });
  }

  function mount(){
    arrangeHeader();
    if(document.getElementById('sr-v931-layout')) return;

    const watch=headingPanel(['watchlist']);
    const alert=headingPanel(['alert center']);
    const results=headingPanel(['scanner results']);
    const ai=headingPanel(['ai view']);
    if(!results) return;

    const panels=[watch,alert,results,ai].filter(Boolean);
    const oldParents=new Set(panels.map(x=>x.parentElement));
    const layout=document.createElement('section');
    layout.id='sr-v931-layout';
    layout.setAttribute('data-version',VERSION);
    layout.innerHTML='<div class="sr-v931-workbench"></div><div class="sr-v931-results"></div>';

    const first=panels.reduce((a,b)=>a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_PRECEDING?b:a,panels[0]);
    const insertionAnchor=first.closest('main,.main-content,#app-main,.content')||first;
    if(insertionAnchor===first) first.parentNode.insertBefore(layout,first);
    else insertionAnchor.parentNode.insertBefore(layout,insertionAnchor.nextSibling);

    const workbench=layout.querySelector('.sr-v931-workbench');
    const resultZone=layout.querySelector('.sr-v931-results');
    if(watch){watch.classList.add('sr-v931-watchlist');workbench.appendChild(watch)}
    if(alert){alert.classList.add('sr-v931-alert');workbench.appendChild(alert)}
    if(ai){ai.classList.add('sr-v931-ai');workbench.appendChild(ai)}
    results.classList.add('sr-v931-scanner-results');
    resultZone.appendChild(results);
    cleanOldParents(oldParents);
    document.body.classList.add('sr-v931-mounted');
  }

  let timer;
  const schedule=()=>{clearTimeout(timer);timer=setTimeout(mount,180)};
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',schedule); else schedule();
  window.addEventListener('load',schedule);
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true});
  window.StockRadarFullWidthLayout={version:VERSION,refresh:mount};
})();
