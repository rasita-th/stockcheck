(() => {
  'use strict';
  const VERSION='9.3.3';
  const TZ='Asia/Bangkok';
  const SELECTORS=[
    '[data-updated-at]','[data-deployed-at]','[data-last-checked]','[data-timestamp]',
    'time[datetime]','.last-updated','.updated-at','.last-checked','.deploy-time',
    '[class*="updated-at"]','[class*="last-update"]','[class*="last-checked"]'
  ].join(',');
  const fmt=new Intl.DateTimeFormat('th-TH',{timeZone:TZ,year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
  function parseValue(el){
    const raw=el.getAttribute('datetime')||el.dataset.updatedAt||el.dataset.deployedAt||el.dataset.lastChecked||el.dataset.timestamp;
    if(raw){const d=new Date(raw);if(!Number.isNaN(d.valueOf())) return d;}
    const text=el.textContent||'';
    const iso=text.match(/\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/);
    if(iso){let s=iso[0].replace(' ','T');if(!/(Z|[+-]\d{2}:?\d{2})$/.test(s))s+='Z';const d=new Date(s);if(!Number.isNaN(d.valueOf()))return d;}
    return null;
  }
  function apply(el){
    if(el.dataset.sr933ThaiTime==='1') return;
    const d=parseValue(el); if(!d) return;
    const original=el.textContent||''; const label=(original.match(/^[^:]{1,40}:/)||[''])[0];
    el.textContent=`${label?label+' ':''}${fmt.format(d)} น.`;
    const z=document.createElement('span');z.className='sr933-time-zone-label';z.textContent='เวลาไทย';el.appendChild(z);
    el.title=`${d.toISOString()} → ${TZ}`;el.dataset.sr933ThaiTime='1';
  }
  function mount(){document.querySelectorAll(SELECTORS).forEach(apply)}
  let t;const schedule=()=>{clearTimeout(t);t=setTimeout(mount,180)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else schedule();
  addEventListener('load',schedule);new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true});
  window.StockRadarThaiTime={version:VERSION,timeZone:TZ,format:value=>fmt.format(new Date(value))};
})();
