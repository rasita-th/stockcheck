(() => {
  'use strict';
  const VERSION = '9.3.3';
  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => [...r.querySelectorAll(s)];
  const norm = v => String(v || '').replace(/\s+/g,' ').trim().toLowerCase();

  function isVisible(el){
    if(!el || !el.isConnected) return false;
    const s=getComputedStyle(el); return s.display!=='none' && s.visibility!=='hidden';
  }
  function labelOf(el){ return norm(el?.getAttribute?.('aria-label') || el?.title || el?.textContent); }
  function findByLabel(words, root=document){
    return $$('a,button,[role="button"]',root).find(el => isVisible(el) && words.some(w => labelOf(el).includes(w)));
  }
  function firstExisting(selectors, root=document){
    for(const s of selectors){ const el=$(s,root); if(el) return el; } return null;
  }
  function pageName(){
    const p=(location.pathname.split('/').pop()||'index.html').toLowerCase();
    if(p.includes('market')) return 'market';
    if(p.includes('today')) return 'today';
    if(p.includes('memo')) return 'memo';
    return 'scanner';
  }
  function localHref(file){
    const current=(location.pathname.split('/').pop()||'index.html');
    return current ? file : `./${file}`;
  }

  function extractRealBadge(source){
    if(!source) return null;
    const candidates=$$('[class*="badge"],[class*="count"],sup,.notification-count',source);
    const exact=candidates.map(x=>x.textContent.trim()).find(x=>/^\d+$/.test(x));
    if(exact!=null) return exact;
    const m=(source.textContent||'').match(/(?:today|วันนี้|alerts?)\s*(\d+)/i);
    return m?.[1] || null;
  }

  function copySemantics(target, source){
    if(!source) return;
    for(const name of ['data-action','data-tab','data-target','aria-controls']){
      const v=source.getAttribute?.(name); if(v) target.setAttribute(name,v);
    }
  }

  function createAction({id,label,icon,href,source,active}){
    let el;
    const sourceHref=source?.tagName==='A' ? source.getAttribute('href') : null;
    if(sourceHref && sourceHref!=='#' && !sourceHref.startsWith('javascript:')) href=sourceHref;

    if(source && source.tagName==='BUTTON' && pageName()==='scanner'){
      el=document.createElement('button'); el.type='button';
      copySemantics(el,source);
      el.addEventListener('click',()=>source.click());
    }else{
      el=document.createElement('a'); el.href=href;
    }
    el.className='sr933-nav-action'; el.dataset.navId=id;
    el.innerHTML=`<span aria-hidden="true">${icon}</span><span>${label}</span>`;
    el.setAttribute('aria-label',label);
    if(active) el.setAttribute('aria-current','page');
    const badge=extractRealBadge(source);
    if(badge!==null){
      const b=document.createElement('span'); b.className='sr933-live-badge'; b.textContent=badge; b.dataset.realSource='true'; el.appendChild(b);
    }
    return el;
  }

  function identifyHeader(){
    const candidates=$$('header,.app-header,.top-header,.site-header,.main-header,[class*="header"]')
      .filter(el=>isVisible(el) && /stock timing radar/i.test(el.textContent||''));
    return candidates.sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0] || null;
  }
  function identifyInner(header){
    return firstExisting(['.header-inner','.header-row','.topbar-inner','.nav-inner','.container'],header) || header;
  }
  function identifyBrand(inner){
    return firstExisting(['.brand','.logo-wrap','.app-brand','.header-brand','a[href="index.html"]'],inner)
      || $$('div,a',inner).find(el=>/stock timing radar/i.test(el.textContent||''));
  }
  function identifySearch(inner){
    const input=$('input[type="search"],input[placeholder*="Search" i],[role="searchbox"]',inner);
    return input?.closest('form,.search-wrap,.search-container,.symbol-search,[class*="search"]') || input;
  }
  function identifyActionContainer(inner){
    return firstExisting(['.header-actions','.top-nav','.nav-actions','.actions','.header-nav'],inner)
      || findByLabel(['scanner'],inner)?.parentElement;
  }

  function normalizeHeader(){
    const header=identifyHeader(); if(!header) return false;
    const inner=identifyInner(header); header.classList.add('sr933-global-header'); inner.classList.add('sr933-header-inner');
    const brand=identifyBrand(inner); const search=identifySearch(inner); const oldActions=identifyActionContainer(inner);
    brand?.classList.add('sr933-brand-zone'); search?.classList.add('sr933-search-zone');

    const scannerSource=findByLabel(['scanner'],header);
    const todaySource=findByLabel(['today','วันนี้'],header) || findByLabel(['today','วันนี้']);
    const memoSource=findByLabel(['memo','บันทึก'],header) || findByLabel(['memo','บันทึก']);
    const marketSource=$('a[href$="market.html"]',header) || findByLabel(['market pulse'],header) || $('a[href$="market.html"]');

    let actions=$('.sr933-action-zone',inner);
    if(!actions){ actions=document.createElement('nav'); actions.className='sr933-action-zone'; actions.setAttribute('aria-label','Main navigation'); inner.appendChild(actions); }
    actions.replaceChildren(
      createAction({id:'scanner',label:'Scanner',icon:'◎',href:localHref('index.html'),source:scannerSource,active:pageName()==='scanner'}),
      createAction({id:'today',label:'Today',icon:'📡',href:localHref('index.html#today'),source:todaySource,active:pageName()==='today'}),
      createAction({id:'memo',label:'Memo',icon:'📝',href:localHref('index.html#memo'),source:memoSource,active:pageName()==='memo'}),
      createAction({id:'market',label:'Market Pulse',icon:'🌍',href:localHref('market.html'),source:marketSource,active:pageName()==='market'})
    );
    if(oldActions && oldActions!==actions) oldActions.hidden=true;
    return true;
  }

  function normalizeTabs(){
    const candidates=$$('.portfolio-tabs,.watchlist-tabs,.tabs-row,.list-tabs,nav.tabs,.workspace-tabs,[role="tablist"]')
      .filter(el=>isVisible(el) && /(default|momentum|dividend|port)/i.test(el.textContent||''));
    candidates[0]?.classList.add('sr933-tabs-balanced');
  }

  function openHashAction(){
    const hash=location.hash.toLowerCase(); if(hash!=='#today' && hash!=='#memo') return;
    const terms=hash==='#today'?['today','วันนี้']:['memo','บันทึก'];
    const source=findByLabel(terms);
    if(source && !source.closest('.sr933-action-zone')) setTimeout(()=>source.click(),120);
  }

  function refreshBadges(){
    const todaySource=$$('a,button,[role="button"]').find(el=>!el.closest('.sr933-action-zone') && ['today','วันนี้'].some(x=>labelOf(el).includes(x)));
    const nav=$('.sr933-action-zone [data-nav-id="today"]'); if(!nav) return;
    const value=extractRealBadge(todaySource); let badge=$('.sr933-live-badge',nav);
    if(value===null){ badge?.remove(); return; }
    if(!badge){ badge=document.createElement('span'); badge.className='sr933-live-badge'; nav.appendChild(badge); }
    badge.textContent=value;
  }

  function mount(){ normalizeHeader(); normalizeTabs(); openHashAction(); refreshBadges(); }
  let timer; const schedule=()=>{clearTimeout(timer);timer=setTimeout(mount,160)};
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',schedule); else schedule();
  addEventListener('load',schedule); addEventListener('hashchange',openHashAction);
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  window.StockRadarSharedShell={version:VERSION,refresh:mount};
})();
