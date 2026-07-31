/* Technical data contract v2: summary index + lazy ticker shards. */
(() => {
  "use strict";

  if (typeof fetchStaticLayer !== "function" || typeof loadStaticData !== "function" || typeof currentQuoteFor !== "function") {
    console.warn("Technical v2 runtime loaded before app.js; keeping legacy data path");
    return;
  }

  const legacyFetchStaticLayer = fetchStaticLayer;
  const legacyLoadStaticData = loadStaticData;
  const legacyCurrentQuoteFor = currentQuoteFor;
  const shardRequests = new Map();

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
      const index = await fetchJsonNoStore("data/technical/index.json");
      if (!index || index.schema_version !== "2.0" || !Array.isArray(index.rows)) {
        throw new Error("Invalid technical index v2 contract");
      }
      return {
        ...index,
        quotes: {},
        watchlist: index.rows.map((row) => row.symbol || row.ticker).filter(Boolean),
        __technicalV2: true,
      };
    } catch (error) {
      console.warn("Technical index v2 unavailable; falling back to legacy technical.json", error);
      return legacyFetchStaticLayer(layer);
    }
  };

  currentQuoteFor = function currentQuoteForV2(symbol) {
    const ticker = safeTicker(symbol);
    const existing = legacyCurrentQuoteFor(ticker);
    if (ticker && state.staticMode && state.staticLoaded && !hasSeries(state.quotes[ticker])) {
      void loadTechnicalShard(ticker);
    }
    return existing;
  };

  loadStaticData = async function loadStaticDataV2(options = {}) {
    await legacyLoadStaticData(options);
    const technical = state.staticPayloads?.technical || {};
    if (technical.__technicalV2 && state.selected) await loadTechnicalShard(state.selected);
  };

  window.StockcheckTechnicalV2 = Object.freeze({
    loadTechnicalShard,
    hasSeries,
    isActive: () => Boolean(state.staticPayloads?.technical?.__technicalV2),
  });
})();
