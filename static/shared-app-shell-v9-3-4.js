(() => {
  'use strict';
  const VERSION='9.3.4';
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const norm=v=>String(v||'').replace(/\s+/g,' ').trim().toLowerCase();
  const exactAction=(el,terms)=>terms.some(t=>norm(el?.getAttribute?.('aria-label')||el?.title||el?.textContent)===t);
  function visible(el){if(!el||!el.isConnected)return false;const s=getComputedStyle(el);return s.display!=='none'&&s.visibility!=='hidden'}
  function page(){const p=(location.pathname.split('/').pop()||'index.html').toLowerCase();if(p.includes('market'))return'market';if(p.includes('today'))return'today';if(p.includes('memo'))return'memo';return'scanner'}
  function first(selectors,root=document){for(const s of selectors){const el=$(s,root);if(el)return el}return null}
  function findSource(terms,exclude){return $$('a,button,[role="button"]')
    .find(el=>el!==exclude&&!el.closest('.sr934-action-zone')&&visible(el)&&terms.some(t=>norm(el.getAttribute('aria-label')||el.title||el.textContent).includes(t)))}
  function realBadge(source){if(!source)return null;const nodes=$$('[class*="badge"],[class*="count"],sup,.notification-count',source);const x=nodes.map(n=>n.textContent.trim()).find(v=>/^\d+$/.test(v));if(x!=null)return x;const m=(source.textContent||'').match(/(?:today|วันนี้|alerts?)\s*(\d+)/i);return m?.[1]||null}
  function header(){return $$('header,.app-header,.top-header,.site-header,.main-header,[class*="header"]')
    .filter(el=>visible(el)&&/stock timing radar/i.test(el.textContent||''))
    .sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0]||null}
  function inner(h){return first(['.header-inner','.header-row','.topbar-inner','.nav-inner','.container'],h)||h}
  function brand(i){return first(['.brand','.logo-wrap','.app-brand','.header-brand','a[href="index.html"]'],i)||$$('div,a',i).find(el=>/stock timing radar/i.test(el.textContent||''))}
  function search(i){const input=$('input[type="search"],input[placeholder*="Search" i],[role="searchbox"]',i);return input?.closest('form,.search-wrap,.search-container,.symbol-search,[class*="search"]')||input}
  function href(file){return file}
  function action({id,label,icon,route,source,active}){
    let el;
    const sourceHref=source?.tagName==='A'?source.getAttribute('href'):null;
    if(sourceHref&&sourceHref!=='#'&&!sourceHref.startsWith('javascript:'))route=sourceHref;
    if(source&&source.tagName==='BUTTON'&&page()==='scanner'&&(id==='today'||id==='memo')){
      el=document.createElement('button');el.type='button';el.addEventListener('click',()=>source.click());
    }else{el=document.createElement('a');el.href=route}
    el.className='sr934-nav-action';el.dataset.navId=id;el.setAttribute('aria-label',label);
    el.innerHTML=`<span aria-hidden="true">${icon}</span><span>${label}</span>`;
    if(active)el.setAttribute('aria-current','page');
    const count=realBadge(source);if(count!==null){const b=document.createElement('span');b.className='sr934-live-badge';b.textContent=count;b.dataset.realSource='true';el.appendChild(b)}
    return el;
  }
  function hideLegacy(sources,canonical){
    for(const src of sources){if(src&&src!==canonical&&!src.closest('.sr934-action-zone'))src.classList.add('sr934-legacy-action')}
    const parents=new Set(sources.filter(Boolean).map(x=>x.parentElement));
    queueMicrotask(()=>parents.forEach(p=>{if(!p||p.closest('.sr934-action-zone'))return;const meaningful=[...p.children].some(c=>!c.classList.contains('sr934-legacy-action')&&visible(c)&&(c.textContent.trim()||c.children.length));if(!meaningful)p.classList.add('sr934-empty-action-shell')}));
  }
  function normalizeHeader(){
    const h=header();if(!h)return false;const i=inner(h);h.classList.add('sr934-global-header');i.classList.add('sr934-header-inner');
    brand(i)?.classList.add('sr934-brand-zone');search(i)?.classList.add('sr934-search-zone');
    const existing=$('.sr934-action-zone',i);
    const scanner=findSource(['scanner'],existing),today=findSource(['today','วันนี้'],existing),memo=findSource(['memo','บันทึก'],existing),market=$$('a[href$="market.html"],button').find(el=>!el.closest('.sr934-action-zone')&&visible(el)&&norm(el.textContent).includes('market pulse'));
    let zone=existing;if(!zone){zone=document.createElement('nav');zone.className='sr934-action-zone';zone.setAttribute('aria-label','Main navigation');i.appendChild(zone)}
    zone.replaceChildren(
      action({id:'scanner',label:'Scanner',icon:'◎',route:href('index.html'),source:scanner,active:page()==='scanner'}),
      action({id:'today',label:'Today',icon:'📡',route:href('index.html#today'),source:today,active:page()==='today'}),
      action({id:'memo',label:'Memo',icon:'📝',route:href('index.html#memo'),source:memo,active:page()==='memo'}),
      action({id:'market',label:'Market Pulse',icon:'🌍',route:href('market.html'),source:market,active:page()==='market'})
    );
    hideLegacy([scanner,today,memo,market],zone);return true;
  }
  function tabs(){const c=$$('.portfolio-tabs,.watchlist-tabs,.tabs-row,.list-tabs,nav.tabs,.workspace-tabs,[role="tablist"]')
    .filter(el=>visible(el)&&/(default|momentum|dividend|port)/i.test(el.textContent||''));c[0]?.classList.add('sr934-tabs-balanced')}
  function openHash(){const hash=location.hash.toLowerCase();if(hash!=='#today'&&hash!=='#memo')return;const terms=hash==='#today'?['today','วันนี้']:['memo','บันทึก'];const src=findSource(terms);if(src)setTimeout(()=>src.click(),120)}
  function mount(){normalizeHeader();tabs();openHash()}
  let t;const schedule=()=>{clearTimeout(t);t=setTimeout(mount,140)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else schedule();
  addEventListener('load',schedule);addEventListener('hashchange',openHash);
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  window.StockRadarSharedShell={version:VERSION,refresh:mount};
})();
