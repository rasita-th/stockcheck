(() => {
  'use strict';
  const VERSION='9.3.7';
  const PANEL='section,article,.card,.panel,[class*="card"],[class*="panel"],[class*="widget"],[class*="box"]';
  const norm=v=>String(v||'').replace(/\s+/g,' ').trim().toLowerCase();
  const visible=el=>{if(!el||!el.isConnected)return false;const s=getComputedStyle(el);return s.display!=='none'&&s.visibility!=='hidden'};

  function panelFrom(node){
    if(!node)return null;
    let p=node.closest(PANEL)||node.parentElement;
    while(p?.parentElement&&p.getBoundingClientRect().height<72){p=p.parentElement.closest(PANEL)||p.parentElement}
    return p;
  }
  function byHeading(terms,reject=[]){
    const nodes=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6,[class*="title"],[class*="heading"],legend')];
    const n=nodes.find(el=>{
      if(!visible(el)||el.closest('#sr-dashboard,#sr-v937-workspace'))return false;
      const t=norm(el.textContent);
      return terms.some(x=>t===x||t.startsWith(x)||t.includes(x))&&!reject.some(x=>t.includes(x));
    });
    return panelFrom(n);
  }
  function allByHeading(terms,reject=[]){
    const out=[];
    for(const el of document.querySelectorAll('h1,h2,h3,h4,h5,h6,[class*="title"],[class*="heading"],legend')){
      if(!visible(el)||el.closest('#sr-dashboard,#sr-v937-workspace'))continue;
      const t=norm(el.textContent);
      if(terms.some(x=>t===x||t.startsWith(x)||t.includes(x))&&!reject.some(x=>t.includes(x))){const p=panelFrom(el);if(p&&!out.includes(p))out.push(p)}
    }
    return out;
  }
  function unique(xs){return [...new Set(xs.filter(Boolean))]}
  function move(el,to,cls){if(!el||!to||el.closest('#sr-v937-workspace'))return;el.classList.add(cls);to.appendChild(el)}
  function meaningful(parent){
    return [...parent.children].some(c=>!c.matches('script,style,#sr-v937-workspace')&&visible(c)&&(c.textContent.trim()||c.children.length));
  }
  function clean(parents){
    for(const p of parents){
      if(!p||p===document.body||p.id==='sr-v937-workspace')continue;
      if(!meaningful(p))p.classList.add('sr937-empty-shell');
      let q=p.parentElement;
      if(q&&q!==document.body&&!meaningful(q))q.classList.add('sr937-empty-shell');
    }
  }

  function mount(){
    if(document.getElementById('sr-v937-workspace'))return;
    const watch=byHeading(['watchlist']);
    const filters=byHeading(['scan filters']);
    const alerts=byHeading(['alert center']);
    const results=byHeading(['scanner results']);
    if(!results)return;

    const detail=unique(allByHeading(['price / ema','price/ema','rsi(14)','rsi','vol(5,10)','volume','setup'],['scanner results']));
    const analysis=unique(allByHeading(['fundamental snapshot','what stood out','ai view','fundamentals'],['fundamental playbook','scanner results']));
    const panels=unique([watch,filters,alerts,results,...detail,...analysis]);
    const oldParents=new Set(panels.map(x=>x.parentElement));

    const layout=document.createElement('main');
    layout.id='sr-v937-workspace';
    layout.dataset.version=VERSION;
    layout.innerHTML=`
      <section class="sr937-zone sr937-control-zone">
        <div class="sr937-left-stack"></div>
        <div class="sr937-center-stack"></div>
      </section>
      <section class="sr937-zone sr937-results-zone"></section>
      <section class="sr937-zone sr937-detail-zone"></section>
      <section class="sr937-zone sr937-analysis-zone"></section>`;

    const dashboard=document.getElementById('sr-dashboard');
    if(dashboard?.parentNode)dashboard.parentNode.insertBefore(layout,dashboard.nextSibling);
    else document.body.appendChild(layout);

    const left=layout.querySelector('.sr937-left-stack');
    const center=layout.querySelector('.sr937-center-stack');
    const rz=layout.querySelector('.sr937-results-zone');
    const dz=layout.querySelector('.sr937-detail-zone');
    const az=layout.querySelector('.sr937-analysis-zone');
    move(watch,left,'sr937-watchlist');
    move(filters,left,'sr937-filters');
    move(alerts,center,'sr937-alerts');
    move(results,rz,'sr937-results');
    detail.forEach(x=>move(x,dz,'sr937-detail-card'));
    analysis.forEach(x=>move(x,az,'sr937-analysis-card'));

    if(!left.children.length&&!center.children.length)layout.querySelector('.sr937-control-zone').remove();
    else{if(!left.children.length)left.remove();if(!center.children.length)center.remove()}
    if(!rz.children.length)rz.remove();
    if(!dz.children.length)dz.remove();
    if(!az.children.length)az.remove();
    clean(oldParents);
    document.body.classList.add('sr937-mounted');
  }
  let timer;const schedule=()=>{clearTimeout(timer);timer=setTimeout(mount,260)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else schedule();
  window.addEventListener('load',schedule);
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true});
  window.StockRadarBalancedLayout={version:VERSION,refresh:mount};
})();
