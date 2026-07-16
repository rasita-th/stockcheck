(() => {
  'use strict';
  const VERSION='9.3.6';
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const norm=v=>String(v||'').replace(/\s+/g,' ').trim().toLowerCase();
  function visible(el){if(!el||!el.isConnected)return false;const s=getComputedStyle(el);return s.display!=='none'&&s.visibility!=='hidden'}
  function page(){const p=(location.pathname.split('/').pop()||'index.html').toLowerCase();if(p.includes('market'))return'market';if(p.includes('today'))return'today';if(p.includes('memo'))return'memo';return'scanner'}
  function first(selectors,root=document){for(const s of selectors){const el=$(s,root);if(el)return el}return null}
  function sourceCandidates(){return $$('a,button,[role="button"]:not(.sr936-nav-action)')}
  function findSource(terms){
    return sourceCandidates().find(el=>!el.closest('.sr936-action-zone')&&terms.some(t=>norm(el.getAttribute('aria-label')||el.title||el.textContent).includes(t)));
  }
  function realBadge(source){if(!source)return null;const nodes=$$('[class*="badge"],[class*="count"],sup,.notification-count',source);const x=nodes.map(n=>n.textContent.trim()).find(v=>/^\d+$/.test(v));if(x!=null)return x;const m=(source.textContent||'').match(/(?:today|วันนี้|alerts?)\s*(\d+)/i);return m?.[1]||null}
  function header(){return $$('header,.app-header,.top-header,.site-header,.main-header,[class*="header"]')
    .filter(el=>visible(el)&&/stock timing radar/i.test(el.textContent||''))
    .sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0]||null}
  function inner(h){return first(['.header-inner','.header-row','.topbar-inner','.nav-inner','.container'],h)||h}
  function brand(i){return first(['.brand','.logo-wrap','.app-brand','.header-brand','a[href="index.html"]'],i)||$$('div,a',i).find(el=>/stock timing radar/i.test(el.textContent||''))}
  function search(i){const input=$('input[type="search"],input[placeholder*="Search" i],[role="searchbox"]',i);return input?.closest('form,.search-wrap,.search-container,.symbol-search,[class*="search"]')||input}
  function action({id,label,icon,active,count}){
    const el=document.createElement('button');
    el.type='button';el.className='sr936-nav-action';el.dataset.navId=id;el.setAttribute('aria-label',label);
    el.innerHTML=`<span aria-hidden="true">${icon}</span><span>${label}</span>`;
    if(active)el.setAttribute('aria-current','page');
    if(count!==null){const b=document.createElement('span');b.className='sr936-live-badge';b.textContent=count;b.dataset.realSource='true';el.appendChild(b)}
    return el;
  }
  function hideLegacy(sources,canonical){
    for(const src of sources){if(src&&src!==canonical&&!src.closest('.sr936-action-zone'))src.classList.add('sr936-legacy-action')}
    const parents=new Set(sources.filter(Boolean).map(x=>x.parentElement));
    queueMicrotask(()=>parents.forEach(p=>{if(!p||p.closest('.sr936-action-zone'))return;const meaningful=[...p.children].some(c=>!c.classList.contains('sr936-legacy-action')&&visible(c)&&(c.textContent.trim()||c.children.length));if(!meaningful)p.classList.add('sr936-empty-action-shell')}));
  }
  function normalizeHeader(){
    const h=header();if(!h)return false;const i=inner(h);h.classList.add('sr936-global-header');i.classList.add('sr936-header-inner');
    brand(i)?.classList.add('sr936-brand-zone');search(i)?.classList.add('sr936-search-zone');
    const scanner=findSource(['scanner']),today=findSource(['today','วันนี้']),memo=findSource(['memo','บันทึก']),market=findSource(['market pulse']);
    let zone=$('.sr936-action-zone',i);if(!zone){zone=document.createElement('nav');zone.className='sr936-action-zone';zone.setAttribute('aria-label','Main navigation');i.appendChild(zone)}
    zone.replaceChildren(
      action({id:'scanner',label:'Scanner',icon:'◎',active:page()==='scanner',count:null}),
      action({id:'today',label:'Today',icon:'📡',active:page()==='today',count:realBadge(today)}),
      action({id:'memo',label:'Memo',icon:'📝',active:page()==='memo',count:realBadge(memo)}),
      action({id:'market',label:'Market Pulse',icon:'🌍',active:page()==='market',count:null})
    );
    hideLegacy([scanner,today,memo,market],zone);return true;
  }
  function activateLegacy(id){
    const terms=id==='today'?['today','วันนี้']:['memo','บันทึก'];
    const src=findSource(terms);
    if(!src)return false;
    try{src.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return true}catch(_){try{src.click();return true}catch(__){return false}}
  }
  function navigate(id){
    if(id==='scanner'){location.assign('index.html');return}
    if(id==='market'){location.assign('market.html');return}
    if((id==='today'||id==='memo')&&page()==='scanner'){
      if(!activateLegacy(id)) location.hash=id;
      return;
    }
    location.assign(`index.html#${id}`);
  }
  document.addEventListener('click',e=>{
    const btn=e.target.closest('.sr936-nav-action');if(!btn)return;
    e.preventDefault();e.stopPropagation();navigate(btn.dataset.navId);
  },true);
  function tabs(){const c=$$('.portfolio-tabs,.watchlist-tabs,.tabs-row,.list-tabs,nav.tabs,.workspace-tabs,[role="tablist"]')
    .filter(el=>visible(el)&&/(default|momentum|dividend|port)/i.test(el.textContent||''));c[0]?.classList.add('sr936-tabs-balanced')}
  function openHash(){const hash=location.hash.toLowerCase();if(hash!=='#today'&&hash!=='#memo')return;setTimeout(()=>activateLegacy(hash.slice(1)),160)}
  function mount(){normalizeHeader();tabs();openHash()}
  let t;const schedule=()=>{clearTimeout(t);t=setTimeout(mount,140)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else schedule();
  addEventListener('load',schedule);addEventListener('hashchange',openHash);
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  window.StockRadarSharedShell={version:VERSION,refresh:mount,navigate};
})();
