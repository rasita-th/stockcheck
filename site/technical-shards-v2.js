/* Canonical screener snapshot + lazy ticker-history contract. */
(() => {
  "use strict";

  if (typeof fetchStaticLayer !== "function" || typeof loadStaticData !== "function" || typeof currentQuoteFor !== "function") {
    console.warn("Technical v2 runtime loaded before app.js; keeping legacy data path");
    return;
  }

  const legacyFetchStaticLayer = fetchStaticLayer;
  const legacyLoadStaticData = loadStaticData;
  const legacyCurrentQuoteFor = currentQuoteFor;
  const legacyMapRow = typeof mapRow === "function" ? mapRow : null;
  const legacyBuildAlertItems = typeof buildAlertItems === "function" ? buildAlertItems : null;
  const shardRequests = new Map();
  let screenerSnapshot = null;

  async function fetchJsonNoStore(url) {
    const res = await fetch(`${url}${url.includes("?") ? "&" : "?"}v=${Date.now()}`, { cache: "no-store" });
    const text = await res.text();
    if (!res.ok) throw new Error(`Technical v2 HTTP ${res.status}: ${text.slice(0, 120)}`);
    if (text.trim().startsWith("<")) throw new Error("Technical v2 returned HTML instead of JSON");
    return JSON.parse(text);
  }

  function safeTicker(value) {
    const ticker = String(value || "").trim().toUpperCase();
    return /^[A-Z0-9._-]{1,32}$/.test(ticker) ? ticker : "";
  }

  function hasSeries(quote) {
    return Array.isArray(quote?.series) && quote.series.length > 0;
  }

  function parseTimestamp(value) {
    const raw = String(value || "").trim();
    if (!raw) return null;
    const normalized = raw.endsWith(" UTC") ? `${raw.slice(0, -4).replace(" ", "T")}Z` : raw;
    const millis = Date.parse(normalized);
    return Number.isFinite(millis) ? millis : null;
  }

  function snapshotAgeMinutes(snapshot = screenerSnapshot) {
    const stamp = parseTimestamp(snapshot?.generated_at || snapshot?.generatedAt);
    return stamp === null ? Infinity : Math.max(0, (Date.now() - stamp) / 60000);
  }

  function snapshotIsFresh(snapshot = screenerSnapshot) {
    if (!snapshot || snapshot.contract !== "canonical-screener-snapshot") return false;
    const ttl = Number(snapshot.stale_after_minutes || 30);
    return Number.isFinite(ttl) && snapshotAgeMinutes(snapshot) <= ttl;
  }

  function freshnessMessage() {
    if (!screenerSnapshot) return "ยังไม่ได้โหลด canonical screener snapshot";
    const age = snapshotAgeMinutes();
    const ttl = Number(screenerSnapshot.stale_after_minutes || 30);
    if (snapshotIsFresh()) {
      return `ข้อมูล Screener ล่าสุด ${Math.round(age)} นาที · ราคา/filters/alerts ใช้ snapshot เดียวกัน`;
    }
    return `ข้อมูลตลาดล่าช้า ${Math.round(age)} นาที (เกณฑ์ ${ttl} นาที) · ปิด technical alerts ชั่วคราว`;
  }

  function renderFreshnessNotice() {
    if (typeof document === "undefined") return;
    const host = document.querySelector(".content-area") || document.querySelector("main") || document.body;
    if (!host) return;
    let notice = document.getElementById("screenerDataFreshness");
    if (!notice) {
      notice = document.createElement("section");
      notice.id = "screenerDataFreshness";
      notice.setAttribute("role", "status");
      notice.style.cssText = "margin:0 0 12px;padding:10px 14px;border:1px solid rgba(88,166,255,.35);border-radius:12px;background:rgba(22,27,34,.92);font:600 13px/1.45 'DM Sans',sans-serif;color:#c9d1d9";
      host.prepend(notice);
    }
    const fresh = snapshotIsFresh();
    notice.textContent = freshnessMessage();
    notice.dataset.fresh = fresh ? "true" : "false";
    notice.style.borderColor = fresh ? "rgba(46,160,67,.55)" : "rgba(248,81,73,.65)";
    notice.style.color = fresh ? "#7ee787" : "#ff7b72";
    const subtitle = document.getElementById("alertSubtitle");
    if (subtitle && !fresh) subtitle.textContent = "Technical alerts paused: screener snapshot is stale";
  }

  async function loadTechnicalShard(symbol) {
    const ticker = safeTicker(symbol);
    if (!ticker || !state.staticMode) return null;

    const cached = state.quotes[ticker];
    if (hasSeries(cached)) return cached;
    if (shardRequests.has(ticker)) return shardRequests.get(ticker);

    const request = fetchJsonNoStore(`data/technical/symbols/${encodeURIComponent(ticker)}.json`)
      .then((payload) => {
        if (!payload || payload.schema_version !== "2.0" || safeTicker(payload.symbol) !== ticker) {
          throw new Error(`Invalid technical shard contract for ${ticker}`);
        }

        const existing = state.quotes[ticker] || {};
        state.quotes[ticker] = {
          ...existing,
          symbol: ticker,
          latest: { ...(existing.latest || {}), ...(payload.latest || {}) },
          fundamental: existing.fundamental || {},
          series: Array.isArray(payload.series) ? payload.series : [],
          meta: { ...(existing.meta || {}), ...(payload.meta || {}) },
          __technicalV2Loaded: true,
        };
        if (typeof renderAll === "function") renderAll();
        return state.quotes[ticker];
      })
      .catch((error) => {
        console.warn(`Technical shard unavailable for ${ticker}; detail remains summary-only`, error);
        return null;
      })
      .finally(() => shardRequests.delete(ticker));

    shardRequests.set(ticker, request);
    return request;
  }

  fetchStaticLayer = async function fetchStaticLayerV2(layer) {
    if (layer !== "technical") return legacyFetchStaticLayer(layer);
    try {
      const snapshot = await fetchJsonNoStore("data/screener_snapshot.json");
      if (
        !snapshot ||
        snapshot.schema_version !== "1.0" ||
        snapshot.contract !== "canonical-screener-snapshot" ||
        !Array.isArray(snapshot.rows) ||
        !snapshot.rows.length
      ) {
        throw new Error("Invalid canonical screener snapshot contract");
      }
      screenerSnapshot = snapshot;
      return {
        ...snapshot,
        quotes: {},
        watchlist: snapshot.rows.map((row) => row.symbol || row.ticker).filter(Boolean),
        __technicalV2: true,
        __screenerSnapshot: true,
        __screenerFresh: snapshotIsFresh(snapshot),
      };
    } catch (snapshotError) {
      console.warn("Canonical screener snapshot unavailable; falling back to technical index", snapshotError);
      try {
        const index = await fetchJsonNoStore("data/technical/index.json");
        if (!index || index.schema_version !== "2.0" || !Array.isArray(index.rows)) {
          throw new Error("Invalid technical index v2 contract");
        }
        screenerSnapshot = null;
        return {
          ...index,
          quotes: {},
          watchlist: index.rows.map((row) => row.symbol || row.ticker).filter(Boolean),
          __technicalV2: true,
          __screenerSnapshot: false,
          __screenerFresh: false,
        };
      } catch (error) {
        console.warn("Technical index v2 unavailable; falling back to legacy technical.json", error);
        screenerSnapshot = null;
        return legacyFetchStaticLayer(layer);
      }
    }
  };

  if (legacyMapRow) {
    mapRow = function mapCanonicalScreenerRow(row = {}) {
      const mapped = legacyMapRow(row);
      const livePrice = typeof toNum === "function"
        ? toNum(row.price ?? row.regularMarketPrice ?? row.close)
        : Number(row.price ?? row.regularMarketPrice ?? row.close);
      const liveDayPct = typeof toNum === "function"
        ? toNum(row.dayPct ?? row.day_change_pct)
        : Number(row.dayPct ?? row.day_change_pct);
      if (Number.isFinite(livePrice)) mapped.price = livePrice;
      if (Number.isFinite(liveDayPct)) mapped.dayPct = liveDayPct;
      mapped.screenerSnapshotFresh = snapshotIsFresh();
      mapped.screenerSnapshotStatus = row.snapshotStatus || "unknown";
      return mapped;
    };
  }

  if (legacyBuildAlertItems) {
    buildAlertItems = function buildCanonicalAlertItems() {
      if (state.staticMode && screenerSnapshot && !snapshotIsFresh()) return [];
      return legacyBuildAlertItems();
    };
  }

  currentQuoteFor = function currentQuoteForV2(symbol) {
    const ticker = safeTicker(symbol);
    const selectedTicker = safeTicker(state.selected);
    const existing = legacyCurrentQuoteFor(ticker);
    if (
      ticker &&
      ticker === selectedTicker &&
      state.staticMode &&
      state.staticLoaded &&
      !hasSeries(state.quotes[ticker])
    ) {
      void loadTechnicalShard(ticker);
    }
    return existing;
  };

  loadStaticData = async function loadStaticDataV2(options = {}) {
    await legacyLoadStaticData(options);
    const technical = state.staticPayloads?.technical || {};
    if (technical.__technicalV2 && state.selected) await loadTechnicalShard(state.selected);
    renderFreshnessNotice();
  };

  if (typeof setInterval === "function") {
    setInterval(renderFreshnessNotice, 60000);
  }

  window.StockcheckTechnicalV2 = Object.freeze({
    loadTechnicalShard,
    hasSeries,
    snapshotAgeMinutes,
    snapshotIsFresh,
    getSnapshot: () => screenerSnapshot,
    isActive: () => Boolean(state.staticPayloads?.technical?.__technicalV2),
  });
})();
