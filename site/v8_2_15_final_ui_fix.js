/* Stock Timing Radar v8.2.15 Final UI/Data Sync Fix
   - Memo current price joins latest data/technical.json
   - Mobile technical cards show daily change
   - Adds scaled EMA bars using real % distance
   No API key. Browser reads generated static JSON only.
*/
(function(){
  const TECH_URL = "data/technical.json?v=" + Date.now();
  const EMA_KEYS = [
    ["EMA5", "ema5Pct"],
    ["EMA20", "ema20Pct"],
    ["EMA89", "ema89Pct"],
    ["EMA200", "ema200Pct"],
  ];

  let techMap = new Map();

  function num(v){
    if (v === null || v === undefined || v === "" || v === "—") return null;
    const n = Number(String(v).replace(/[$,%x,]/g, ""));
    return Number.isFinite(n) ? n : null;
  }

  function money(v){
    const n = num(v);
    if (n === null) return "—";
    return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function pct(v){
    const n = num(v);
    if (n === null) return "—";
    return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
  }

  function tickerOfRow(r){
    return String(r?.ticker || r?.symbol || "").trim().toUpperCase();
  }

  function priceOf(r){
    return num(r?.price ?? r?.regularMarketPrice ?? r?.currentPrice);
  }

  function dayPctOf(r){
    return num(r?.dayPct ?? r?.day_change_pct ?? r?.regularMarketChangePercent ?? r?.changePercent);
  }

  function dayAbsOf(r){
    return num(r?.dayChange ?? r?.regularMarketChange ?? r?.change);
  }

  function tone(v){
    const n = num(v);
    if (n === null || n === 0) return "neutral";
    return n > 0 ? "up" : "down";
  }

  function tickerFrom(el){
    const attr = el?.getAttribute?.("data-ticker") || el?.dataset?.ticker;
    if (attr) return attr.toUpperCase();

    const text = String(el?.textContent || "").replace(/\s+/g, " ").trim();

    const exactTicker = text.match(/\bTicker:\s*([A-Z0-9.\-]+)(?=\s*(?:Source|Current|Price|$))/i);
    if (exactTicker) return exactTicker[1].toUpperCase();

    const marketTicker = text.match(/\b([A-Z][A-Z0-9.\-]{1,9})\s+(?:NMS|NYSE|NASDAQ|NAS|USD|EQUITY)\b/);
    if (marketTicker) return marketTicker[1].toUpperCase();

    const startTicker = text.match(/^\s*([A-Z][A-Z0-9.\-]{1,9})\b/);
    if (startTicker) return startTicker[1].toUpperCase();

    return "";
  }

  function css(){
    if (document.getElementById("v8215-final-ui-style")) return;
    const style = document.createElement("style");
    style.id = "v8215-final-ui-style";
    style.textContent = `
      .v8215-live,.v8215-day,.v8215-ema{
        border:1px solid rgba(88,166,255,.25);
        background:rgba(13,17,23,.76);
        border-radius:16px;
        padding:10px 12px;
        margin:10px 0;
        font-family:"IBM Plex Mono",ui-monospace,monospace;
        color:#e6edf3;
      }
      .v8215-live,.v8215-day{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
      }
      .v8215-label,.v8215-title{
        color:#8b949e;
        font-size:12px;
        font-weight:800;
        letter-spacing:.06em;
        text-transform:uppercase;
      }
      .v8215-price{font-size:19px;font-weight:900}
      .v8215-up{color:#3fb950}
      .v8215-down{color:#ff5f5f}
      .v8215-neutral{color:#8b949e}
      .v8215-row{
        display:grid;
        grid-template-columns:58px 1fr 78px;
        align-items:center;
        gap:10px;
        margin-top:8px;
      }
      .v8215-track{
        height:10px;
        border-radius:999px;
        background:rgba(139,148,158,.18);
        overflow:hidden;
      }
      .v8215-fill{
        display:block;
        height:100%;
        min-width:3px;
        border-radius:999px;
      }
      .v8215-fill.down{background:#ff5f5f}
      .v8215-fill.safe{background:#3fb950}
      .v8215-fill.warm{background:#d29922}
      .v8215-fill.hot{background:#f0883e}
    `;
    document.head.appendChild(style);
  }

  async function loadTech(){
    try{
      const res = await fetch(TECH_URL, { cache:"no-store" });
      const data = await res.json();
      const rows = Array.isArray(data.rows) ? data.rows : [];
      techMap = new Map(rows.map(r => [tickerOfRow(r), r]).filter(([t]) => t));
      document.documentElement.dataset.v8215TechRows = String(techMap.size);
      patchAll();
    }catch(e){
      console.warn("[v8.2.15] cannot load technical.json", e);
    }
  }

  function patchMemoCurrent(){
    const cards = Array.from(document.querySelectorAll("article, section, .panel-card, .memo-card, .stock-memo-card"));
    for (const card of cards){
      const txt = card.textContent || "";
      if (!/CURRENT/i.test(txt) || !/NOTE/i.test(txt) || !/TARGET/i.test(txt)) continue;

      const ticker = tickerFrom(card);
      const row = techMap.get(ticker);
      if (!ticker || !row) continue;

      const price = priceOf(row);
      const dp = dayPctOf(row);
      const da = dayAbsOf(row);
      const t = tone(dp);

      card.querySelectorAll(".v8215-live").forEach(x => x.remove());

      const strip = document.createElement("div");
      strip.className = "v8215-live";
      strip.innerHTML = `
        <span>
          <span class="v8215-label">Live current</span><br>
          <b class="v8215-price">${money(price)}</b>
        </span>
        <span class="v8215-${t}">
          <b>${pct(dp)}</b>${da !== null ? `<br><small>${money(da).replace("$-", "-$").replace("$", da > 0 ? "+$" : "$")}</small>` : ""}
        </span>
      `;
      card.insertBefore(strip, card.children[1] || null);

      const leaves = Array.from(card.querySelectorAll("*")).filter(x => x.children.length === 0);
      const currentLabel = leaves.find(x => x.textContent.trim().toUpperCase() === "CURRENT");
      const box = currentLabel?.closest("div");
      if (box && price !== null){
        const moneyLeaf = Array.from(box.querySelectorAll("*")).find(x =>
          x.children.length === 0 && /^\$\s*[\d,]+(\.\d+)?/.test(x.textContent.trim())
        );
        if (moneyLeaf) moneyLeaf.textContent = money(price);
      }
    }
  }

  function patchTechnicalCards(){
    const cards = Array.from(document.querySelectorAll("#technicalMobileCards > *"));
    for (const card of cards){
      const ticker = tickerFrom(card);
      const row = techMap.get(ticker);
      if (!ticker || !row) continue;

      card.querySelectorAll(".v8215-day,.v8215-ema").forEach(x => x.remove());

      const price = priceOf(row);
      const dp = dayPctOf(row);
      const da = dayAbsOf(row);
      const t = tone(dp);

      const day = document.createElement("div");
      day.className = "v8215-day";
      day.innerHTML = `
        <span>
          <span class="v8215-label">Today</span><br>
          <b class="v8215-price">${money(price)}</b>
        </span>
        <span class="v8215-${t}">
          <b>${pct(dp)}</b>${da !== null ? `<br><small>${money(da).replace("$-", "-$").replace("$", da > 0 ? "+$" : "$")}</small>` : ""}
        </span>
      `;
      card.insertBefore(day, card.children[2] || null);

      const ema = document.createElement("div");
      ema.className = "v8215-ema";
      ema.innerHTML = `<div class="v8215-title">Scaled EMA distance</div>` + EMA_KEYS.map(([label,key]) => {
        const v = num(row[key]);
        const av = Math.abs(v ?? 0);
        const width = Math.max(3, Math.min(100, av / 35 * 100));
        const fill = v === null ? "safe" : v < 0 ? "down" : v <= 5 ? "safe" : v <= 15 ? "warm" : "hot";
        return `
          <div class="v8215-row">
            <span>${label}</span>
            <span class="v8215-track"><span class="v8215-fill ${fill}" style="width:${width}%"></span></span>
            <b class="v8215-${tone(v)}">${pct(v)}</b>
          </div>
        `;
      }).join("");
      card.appendChild(ema);
    }
  }

  function patchAll(){
    if (!techMap.size) return;
    css();
    patchMemoCurrent();
    patchTechnicalCards();
  }

  let pending = false;
  function schedule(){
    if (pending) return;
    pending = true;
    setTimeout(() => {
      pending = false;
      patchAll();
    }, 250);
  }

  document.addEventListener("DOMContentLoaded", loadTech);
  if (document.readyState !== "loading") loadTech();

  new MutationObserver(schedule).observe(document.documentElement, { childList:true, subtree:true });
  window.stockcheckV8215PatchAll = patchAll;
})();
