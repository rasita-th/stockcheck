const state={data:null,periods:{globalTable:"ytd_pct",usIndexTable:"week_pct",sectorTable:"week_pct",themeTable:"week_pct"},region:"All"};
const periods=[["day_pct","1D"],["week_pct","1W"],["month_pct","1M"],["ytd_pct","YTD"],["year_pct","1Y"]];
const fmt=v=>v==null||!Number.isFinite(Number(v))?"—":`${Number(v)>0?"+":""}${Number(v).toFixed(1)}%`;
const cls=v=>v==null||Number(v)===0?"neutral":Number(v)>0?"positive":"negative";
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const asArray=v=>Array.isArray(v)?v:[];

function normalise(raw){
  const d=raw&&typeof raw==="object"?raw:{};
  // Accept the current schema plus common names from the pre-v9.2 workflow.
  return {...d,
    global_markets:asArray(d.global_markets||d.markets||d.global_indices),
    us_indices:asArray(d.us_indices||d.us_markets||d.usa_indices),
    us_sectors:asArray(d.us_sectors||d.sectors||d.sector_rotation),
    themes:asArray(d.themes||d.investment_themes||d.theme_rotation),
    today_pulse:asArray(d.today_pulse||d.pulse),
    failed_symbols:asArray(d.failed_symbols)
  };
}
function makeTabs(){document.querySelectorAll(".tabs").forEach(t=>{const target=t.dataset.target;t.innerHTML=periods.map(([p,l])=>`<button type="button" class="${state.periods[target]===p?"active":""}" data-period="${p}">${l}</button>`).join("")})}
function card(r,period,max){const v=r[period];const width=v==null?0:Math.max(3,Math.min(100,Math.abs(v)/max*100));return `<article class="market-card"><div><div class="market-head"><span class="flag">${esc(r.flag||"•")}</span><span class="market-name"><strong>${esc(r.label||r.name||r.symbol||"Unknown")}</strong><small>${esc(r.country||r.category||r.sector||r.theme||"")} · ${esc(r.symbol||"")}</small></span></div><p class="market-desc">${esc(r.description||"")}</p></div><div class="market-value ${cls(v)}">${fmt(v)}<small>${esc(r.as_of||"unavailable")}</small></div><div class="spark"><span class="${Number(v)>=0?"positive-bg":"negative-bg"}" style="width:${width}%"></span></div></article>`}
function emptyMessage(id){
  const key={usIndexTable:"us_indices",sectorTable:"us_sectors",themeTable:"themes",globalTable:"global_markets"}[id];
  const schema=state.data?.schema_version||"ไม่ระบุ";
  return `<div class="empty"><strong>ยังไม่มีข้อมูลในหมวดนี้</strong><br>ไฟล์ market_pulse.json ที่โหลดสำเร็จไม่มีชุด <code>${key}</code> (schema ${esc(schema)}) — ให้รัน workflow v9.2.1 เพื่อสร้าง JSON ใหม่</div>`;
}
function renderRows(id,rows,period){const el=document.getElementById(id);if(!el)return;let filtered=rows;if(id==="globalTable"&&state.region!=="All")filtered=rows.filter(r=>r.region===state.region);const sorted=[...filtered].sort((a,b)=>(b[period]??-9999)-(a[period]??-9999));const max=Math.max(1,...sorted.map(r=>Math.abs(Number(r[period])||0)));el.innerHTML=sorted.length?sorted.map(r=>card(r,period,max)).join(""):emptyMessage(id)}
function renderPulse(){const el=document.getElementById("todayPulse");const rows=state.data.today_pulse||[];el.innerHTML=rows.length?rows.slice(0,8).map(r=>`<article class="pulse-card"><strong>${esc(r.label||r.symbol)}</strong><small>${esc(r.group)} · ${esc(r.direction)}</small><div class="pulse-number ${cls(r.week_pct)}">1D ${fmt(r.day_pct)} · 1W ${fmt(r.week_pct)}</div></article>`).join(""):`<div class="empty">ไม่มีข้อมูล pulse ที่ผ่านเกณฑ์ หรือ workflow ยังไม่ได้สร้างข้อมูลล่าสุด</div>`}
function renderRegions(){const regions=["All",...new Set((state.data.global_markets||[]).map(r=>r.region).filter(Boolean))];const el=document.getElementById("regionFilter");el.innerHTML=regions.map(r=>`<button type="button" class="${r===state.region?"active":""}" data-region="${esc(r)}">${esc(r)}</button>`).join("")}
function renderSummary(){const d=state.data,b=d.breadth||{};document.getElementById("breadthDay").textContent=`${b.sectors_positive_day??0}/${b.sector_count??0}`;document.getElementById("breadthWeek").textContent=`${b.sectors_positive_week??0}/${b.sector_count??0}`;const s=d.us_sectors||[];const valid=s.filter(r=>Number.isFinite(Number(r.week_pct)));const avg=valid.length?valid.reduce((a,r)=>a+Number(r.week_pct),0)/valid.length:0;document.getElementById("riskMode").textContent=valid.length?(avg>1?"Risk-on":avg<-1?"Risk-off":"Mixed"):"—";document.getElementById("riskNote").textContent=valid.length?`ค่าเฉลี่ย sector 1W ${fmt(avg)}`:"รอข้อมูล sector";const leader=[...valid].sort((a,b)=>Number(b.week_pct)-Number(a.week_pct))[0];document.getElementById("weeklyLeader").textContent=leader?.label||"—";document.getElementById("weeklyLeaderValue").textContent=leader?`1W ${fmt(leader.week_pct)}`:"—"}
function render(){const d=state.data;const dt=d.generated_at?new Date(d.generated_at):null;document.getElementById("freshness").textContent=dt&&!isNaN(dt)?dt.toLocaleString("th-TH"):"ไม่ทราบเวลา";document.getElementById("dataStatus").textContent=`สถานะ ${d.status||"unknown"} · สำเร็จ ${d.successful_symbols??"—"} · ล้มเหลว ${(d.failed_symbols||[]).length}`;renderSummary();renderPulse();renderRegions();renderRows("globalTable",d.global_markets,state.periods.globalTable);renderRows("usIndexTable",d.us_indices,state.periods.usIndexTable);renderRows("sectorTable",d.us_sectors,state.periods.sectorTable);renderRows("themeTable",d.themes,state.periods.themeTable)}
document.addEventListener("click",e=>{const p=e.target.closest("[data-period]");if(p){const tabs=p.closest(".tabs"),target=tabs.dataset.target;state.periods[target]=p.dataset.period;makeTabs();render();return}const r=e.target.closest("[data-region]");if(r){state.region=r.dataset.region;render();}});
async function loadPulse(){
  const candidates=["data/market_pulse.json","./data/market_pulse.json","../data/market_pulse.json"];
  let lastError;
  for(const path of candidates){
    try{const r=await fetch(`${path}?v=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);const d=normalise(await r.json());state.data=d;render();return}
    catch(err){lastError=err}
  }
  document.querySelector("main").innerHTML=`<section class="panel"><h2>Market Pulse ยังไม่มีข้อมูล</h2><p>${esc(lastError?.message||"โหลดข้อมูลไม่สำเร็จ")}</p><p>รัน GitHub Action “Refresh Market Pulse v9.2” หนึ่งครั้งหลัง merge และตรวจว่าไฟล์ data/market_pulse.json ถูก commit/deploy</p></section>`;
}
makeTabs();loadPulse();
