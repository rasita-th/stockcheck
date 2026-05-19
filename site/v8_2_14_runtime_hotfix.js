/* Stock Timing Radar v8.2.14
   Hotfix:
   - Join memo cards with latest technical.json current price
   - Add daily change to mobile technical cards
   - Add scaled EMA distance bars so bar length reflects % distance
   Browser-safe: reads generated JSON only.
*/
(function stockcheckV8214RuntimeHotfix(){
  const VERSION = "8.2.14";
  const TECH_URL = "data/technical.json?v=" + Date.now();
  const EMA_KEYS = [
    ["EMA5", "ema5Pct"],
    ["EMA20", "ema20Pct"],
    ["EMA89", "ema89Pct"],
    ["EMA200", "ema200Pct"],
  ];

  let techMap = new Map();

  function toNum(v){
    if (v === null || v === undefined || v === "" || v === "—") return null;
    const n = Number(String(v).replace(/[$,%x,]/g, ""));
    return Number.isFinite(n) ? n : null;
  }

  function fmtMoney(v){
    const n = toNum(v);
    if (n === null) return "—";
    return "$" + n.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function fmtPct(v){
    const n = toNum(v);
    if (n === null) return "—";
    const sign = n > 0 ? "+" : "";
    return sign + n.toFixed(2) + "%";
  }

  function fmtAbs(v){
    const n = toNum(v);
    if (n === null) return "";
    const sign = n > 0 ? "+" : "";
    return sign + fmtMoney(n).replace("$", "$");
  }

  function rowTicker(row){
    return String(row?.ticker || row?.symbol || "").trim().toUpperCase();
  }

  function rowPrice(row){
    return toNum(row?.price ?? row?.regularMarketPrice ?? row?.currentPrice);
  }

  function rowDayPct(row){
    return toNum(row?.dayPct ?? row?.day_change_pct ?? row?.regularMarketChangePercent ?? row?.changePercent);
  }

  function rowDayAbs(row){
    return toNum(row?.dayChange ?? row?.regularMarketChange ?? row?.change);
  }

  function toneClass(n){
    const v = toNum(n);
    if (v === null || v === 0) return "neutral";
    return v > 0 ? "up" : "down";
  }

  function findTickerFromText(text){
    const raw = String(text || "").replace(/\s+/g, " ").trim();

    const tickerLine = raw.match(/Ticker:\s*([A-Z0-9.\-]+)(?=\s*(?:Source|Current|Price|$))/i);
    if (tickerLine) return tickerLine[1].toUpperCase();

    const market = raw.match(/\b([A-Z][A-Z0-9.\-]{1,9})\s+(?:NMS|NYSE|NASDAQ|NAS|USD|EQUITY)\b/);
    if (market) return market[1].toUpperCase();

    const header = raw.match(/^\s*([A-Z][A-Z0-9.\-]{1,9})\b/);
    if (header) return header[1].toUpperCase();

    return "";
  }

  function getTicker(el){
    if (!el) return "";
    const attr = el.getAttribute("data-ticker") || el.dataset?.ticker || "";
    if (attr) return attr.toUpperCase();
    return findTickerFromText(el.textContent || "");
  }

  async function loadTechnical(){
    try {
      const res = await fetch(TECH_URL, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const rows = Array.isArray(data.rows) ? data.rows : [];
      techMap = new Map(rows.map(r => [rowTicker(r), r]).filter(([t]) => t));
      document.documentElement.dataset.v8214TechRows = String(techMap.size);
      patchAll();
    } catch (err) {
      console.warn("[v8.2.14] failed to load technical.json", err);
    }
  }

  function ensureStyle(){
    if (document.getElementById("v8214-hotfix-style")) return;
    const style = document.createElement("style");
    style.id = "v8214-hotfix-style";
    style.textContent = `
      .v8214-live-strip,
      .v8214-day-strip,
      .v8214-ema-scale {
        margin: 10px 0;
        padding: 10px 12px;
        border: 1px solid rgba(88,166,255,.25);
        border-radius: 14px;
        background: rgba(13,17,23,.72);
        color: #e6edf3;
        font-family: "IBM Plex Mono", ui-monospace, monospace;
      }
      .v8214-live-strip {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 6px 12px;
        align-items: center;
      }
      .v8214-day-strip {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      .v8214-live-label,
      .v8214-day-label,
      .v8214-scale-title {
        color: #8b949e;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: .06em;
        font-weight: 700;
      }
      .v8214-live-price,
      .v8214-day-pct {
        font-weight: 800;
        font-size: 18px;
      }
      .v8214-up { color: #3fb950; }
      .v8214-down { color: #ff5f5f; }
      .v8214-neutral { color: #8b949e; }
      .v8214-ema-row {
        display: grid;
        grid-template-columns: 58px 1fr 76px;
        align-items: center;
        gap: 10px;
        margin-top: 8px;
      }
      .v8214-track {
        height: 10px;
        border-radius: 999px;
        background: rgba(139,148,158,.18);
        overflow: hidden;
      }
      .v8214-fill {
        display: block;
        height: 100%;
        min-width: 3px;
        border-radius: 999px;
        background: #58a6ff;
      }
      .v8214-fill.up.safe { background: #3fb950; }
      .v8214-fill.up.warm { background: #d29922; }
      .v8214-fill.up.hot { background: #f0883e; }
      .v8214-fill.down { background: #ff5f5f; }
    `;
    document.head.appendChild(style);
  }

  function patchTechnicalCards(){
    const cards = Array.from(document.querySelectorAll("#technicalMobileCards > *"));
    for (const card of cards){
      const ticker = getTicker(card);
      const row = techMap.get(ticker);
      if (!ticker || !row) continue;

      const price = rowPrice(row);
      const pct = rowDayPct(row);
      const abs = rowDayAbs(row);
      const tone = toneClass(pct);

      let day = card.querySelector(".v8214-day-strip");
      if (!day){
        day = document.createElement("div");
        day.className = "v8214-day-strip";
        const scoreNode = card.querySelector(".score, .card-score");
        if (scoreNode?.parentElement) {
          scoreNode.parentElement.insertAdjacentElement("afterend", day);
        } else {
          card.insertBefore(day, card.children[1] || null);
        }
      }

      day.innerHTML = `
        <span>
          <span class="v8214-day-label">Today</span><br>
          <b>${fmtMoney(price)}</b>
        </span>
        <span class="v8214-day-pct v8214-${tone}">
          ${fmtPct(pct)}
          ${abs !== null ? `<small> ${fmtAbs(abs)}</small>` : ""}
        </span>
      `;

      let scale = card.querySelector(".v8214-ema-scale");
      if (!scale){
        scale = document.createElement("div");
        scale.className = "v8214-ema-scale";
        card.appendChild(scale);
      }

      const bars = EMA_KEYS.map(([label, key]) => {
        const v = toNum(row[key]);
        const absPct = Math.abs(v ?? 0);
        const width = Math.max(3, Math.min(100, absPct / 35 * 100));
        const cls = v === null ? "neutral" : v < 0 ? "down" : v <= 5 ? "up safe" : v <= 15 ? "up warm" : "up hot";
        return `
          <div class="v8214-ema-row">
            <span>${label}</span>
            <span class="v8214-track"><span class="v8214-fill ${cls}" style="width:${width}%"></span></span>
            <b class="v8214-${toneClass(v)}">${fmtPct(v)}</b>
          </div>
        `;
      }).join("");

      scale.innerHTML = `<div class="v8214-scale-title">Scaled EMA distance</div>${bars}`;
    }
  }

  function replaceCurrentBox(card, row){
    const price = rowPrice(row);
    if (price === null) return;

    const leaves = Array.from(card.querySelectorAll("*")).filter(el => el.children.length === 0);
    const currentLabel = leaves.find(el => el.textContent.trim().toUpperCase() === "CURRENT");
    if (!currentLabel) return;

    const box = currentLabel.closest("div");
    if (!box) return;

    const moneyLeaf = Array.from(box.querySelectorAll("*")).find(el =>
      el.children.length === 0 && /^\$\s*[\d,]+(\.\d+)?/.test(el.textContent.trim())
    );

    if (moneyLeaf) moneyLeaf.textContent = fmtMoney(price);
  }

  function patchMemoCards(){
    const candidates = Array.from(document.querySelectorAll("article, section, .panel-card, .memo-card, .stock-memo-card"));
    for (const card of candidates){
      const text = card.textContent || "";
      if (!/CURRENT/i.test(text) || !/NOTE/i.test(text) || !/TARGET/i.test(text)) continue;

      const ticker = getTicker(card);
      const row = techMap.get(ticker);
      if (!ticker || !row) continue;

      replaceCurrentBox(card, row);

      const price = rowPrice(row);
      const pct = rowDayPct(row);
      const abs = rowDayAbs(row);
      const tone = toneClass(pct);

      let strip = card.querySelector(".v8214-live-strip");
      if (!strip){
        strip = document.createElement("div");
        strip.className = "v8214-live-strip";
        card.insertBefore(strip, card.children[1] || null);
      }

      strip.innerHTML = `
        <span>
          <span class="v8214-live-label">Live current from technical.json</span><br>
          <b class="v8214-live-price">${fmtMoney(price)}</b>
        </span>
        <span class="v8214-${tone}">
          ${fmtPct(pct)}
          ${abs !== null ? `<small>${fmtAbs(abs)}</small>` : ""}
        </span>
      `;
    }
  }

  function patchAll(){
    if (!techMap.size) return;
    ensureStyle();
    patchTechnicalCards();
    patchMemoCards();
  }

  let pending = false;
  function schedulePatch(){
    if (pending) return;
    pending = true;
    setTimeout(() => {
      pending = false;
      patchAll();
    }, 250);
  }

  document.addEventListener("DOMContentLoaded", loadTechnical);
  if (document.readyState !== "loading") loadTechnical();

  new MutationObserver(schedulePatch).observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  window.stockcheckV8214PatchAll = patchAll;
})();
