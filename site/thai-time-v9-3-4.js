(() => {
  'use strict';
  const VERSION='9.3.4',TZ='Asia/Bangkok';
  const SELECTORS=['[data-updated-at]','[data-deployed-at]','[data-last-checked]','[data-timestamp]','time[datetime]','.last-updated','.updated-at','.last-checked','.deploy-time','[class*="updated-at"]','[class*="last-update"]','[class*="last-checked"]'].join(',');
  const fmt=new Intl.DateTimeFormat('th-TH',{timeZone:TZ,year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
  function parse(el){const raw=el.getAttribute('datetime')||el.dataset.updatedAt||el.dataset.deployedAt||el.dataset.lastChecked||el.dataset.timestamp;if(raw){const d=new Date(raw);if(!Number.isNaN(d.valueOf()))return d}const m=(el.textContent||'').match(/\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/);if(!m)return null;let s=m[0].replace(' ','T');if(!/(Z|[+-]\d{2}:?\d{2})$/.test(s))s+='Z';const d=new Date(s);return Number.isNaN(d.valueOf())?null:d}
  function apply(el){const d=parse(el);if(!d)return;const iso=d.toISOString();if(el.dataset.sr934SourceIso===iso)return;const original=el.dataset.sr934Original||el.textContent||'';el.dataset.sr934Original=original;const label=(original.match(/^[^:]{1,40}:/)||[''])[0];el.textContent=`${label?label+' ':''}${fmt.format(d)} น.`;const z=document.createElement('span');z.className='sr934-time-zone-label';z.textContent='เวลาไทย';el.appendChild(z);el.title=`${iso} → ${TZ}`;el.dataset.sr934SourceIso=iso}
  function mount(){document.querySelectorAll(SELECTORS).forEach(apply)}let t;const schedule=()=>{clearTimeout(t);t=setTimeout(mount,160)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else schedule();addEventListener('load',schedule);new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  window.StockRadarThaiTime={version:VERSION,timeZone:TZ,format:v=>fmt.format(new Date(v))};
})();
