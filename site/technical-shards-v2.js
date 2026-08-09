/* Canonical screener snapshot + lazy ticker-history contract. */
(() => {
  "use strict";

  if (typeof fetchStaticLayer !== "function" || typeof loadStaticData !== "function" || typeof currentQuoteFor !== "function") {
    console.warn("Technical v2 runtime loaded before app.js; keeping legacy data path");
    return;
  }

  const SCREENER_SNAPSHOT_SCHEMA = "1.1";
  const legacyFetchStaticLayer = fetchStaticLayer;
  const legacyLoadStaticData = loadStaticData;
  const legacyCurrentQuoteFor = currentQuoteFor;
  const legacyMapRow = typeof mapRow === "function" ? mapRow : null;
  const legacyBuildAlertItems = typeof buildAlertItems === "function" ? buildAlertItems : null;
  const shardRequests = new Map();
  const rowModels = new Map();
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

  function snapshotRowFor(symbol) {
    const ticker = safeTicker(symbol);
    const rows = Array.isArray(screenerSnapshot?.rows) ? screenerSnapshot.rows : [];
    return rows.find((row) => safeTicker(row?.symbol || row?.ticker) === ticker) || null;
  }

  function normalizeDrawdown(row = {}) {
    const nested = row?.drawdown && typeof row.drawdown === "object" ? row.drawdown : {};
    const value = (preferred, fallback) => preferred ?? fallback ?? null;
    return {
      ...nested,
      schemaVersion: value(nested.schemaVersion, row.drawdownSchemaVersion),
      status: value(nested.status, row.drawdownStatus),
      currentPct: value(nested.currentPct, row.drawdownCurrentPct),
      maxPct: value(nested.maxPct, row.drawdownMaxPct),
      daysSincePeak: value(nested.daysSincePeak, row.drawdownDaysSincePeak),
      asOf: value(nested.asOf, row.drawdownAsOf),
    };
  }

  function drawdownFor(symbol) {
    return rowModels.get(safeTicker(symbol))?.drawdown || null;
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

  function newYorkSessionState(now = new Date()) {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(now);
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    const weekday = values.weekday || "";
    const minutes = Number(values.hour || 0) * 60 + Number(values.minute || 0);
    const businessDay = !["Sat", "Sun"].includes(weekday);
    const marketOpen = businessDay && minutes >= 9 * 60 + 25 && minutes <= 16 * 60 + 20;
    return { businessDay, marketOpen };
  }

  function snapshotCanDriveAlerts(snapshot = screenerSnapshot) {
    if (snapshotIsFresh(snapshot)) return true;
    if (!snapshot || snapshot.contract !== "canonical-screener-snapshot") return false;
    const session = newYorkSessionState();
    if (session.marketOpen) return false;
    const retentionMinutes = session.businessDay ? 18 * 60 : 72 * 60;
    return snapshotAgeMinutes(snapshot) <= retentionMinutes;
  }

  function freshnessMessage() {
    if (!screenerSnapshot) return "ยังไม่ได้โหลด canonical screener snapshot · ปิด technical alerts ชั่วคราว";
    const age = snapshotAgeMinutes();
    const ttl = Number(screenerSnapshot.stale_after_minutes || 30);
    if (snapshotIsFresh()) {
      return `ข้อมูล Screener ล่าสุด ${Math.round(age)} นาที · ราคา/filters/alerts ใช้ snapshot เดียวกัน`;
    }
    if (snapshotCanDriveAlerts()) {
      return `ตลาดปิด · คง alerts จาก session ล่าสุด (${Math.round(age)} นาที) จนกว่าจะมี snapshot รอบตลาดถัดไป`;
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
    const usableForAlerts = snapshotCanDriveAlerts();
    notice.textContent = freshnessMessage();
    notice.dataset.fresh = fresh ? "true" : "false";
    notice.dataset.alertsUsable = usableForAlerts ? "true" : "false";
    notice.style.borderColor = fresh ? "rgba(46,160,67,.55)" : usableForAlerts ? "rgba(210,153,34,.55)" : "rgba(248,81,73,.65)";
    notice.style.color = fresh ? "#7ee787" : usableForAlerts ? "#e3b341" : "#ff7b72";
    const subtitle = document.getElementById("alertSubtitle");
    if (subtitle) {
      if (!usableForAlerts) subtitle.textContent = "Technical alerts paused: canonical screener data is unavailable or stale";
      else if (!fresh) subtitle.textContent = "Latest completed market session · alerts remain available until the next session refresh";
    }
  }

  function projectSeriesToSnapshot(payload, summary) {
    const series = Array.isArray(payload?.series)
      ? payload.series.map((point) => ({ ...(point || {}) }))
      : [];
    const livePrice = Number(summary?.price ?? summary?.regularMarketPrice ?? summary?.close);
    if (series.length && Number.isFinite(livePrice) && summary?.snapshotStatus === "live_quote") {
      const last = series[series.length - 1];
      const high = Number(last.high);
      const low = Number(last.low);
      last.close = livePrice;
      last.high = Number.isFinite(high) ? Math.max(high, livePrice) : livePrice;
      last.low = Number.isFinite(low) ? Math.min(low, livePrice) : livePrice;
      last.__snapshotProjected = true;
    }
    return series;
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
        const summary = snapshotRowFor(ticker) || {};
        state.quotes[ticker] = {
          ...existing,
          symbol: ticker,
          latest: { ...(payload.latest || {}), ...(existing.latest || {}), ...summary },
          fundamental: existing.fundamental || {},
          series: projectSeriesToSnapshot(payload, summary),
          meta: { ...(existing.meta || {}), ...(payload.meta || {}), screenerSnapshot: summary.snapshotStatus || "unavailable" },
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
      if (!snapshot || snapshot.schema_version !== SCREENER_SNAPSHOT_SCHEMA || snapshot.contract !== "canonical-screener-snapshot" || !Array.isArray(snapshot.rows) || !snapshot.rows.length) {
        throw new Error(`Invalid canonical screener snapshot contract: expected schema ${SCREENER_SNAPSHOT_SCHEMA}`);
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
        if (!index || index.schema_version !== "2.0" || !Array.isArray(index.rows)) throw new Error("Invalid technical index v2 contract");
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
      const livePrice = typeof toNum === "function" ? toNum(row.price ?? row.regularMarketPrice ?? row.close) : Number(row.price ?? row.regularMarketPrice ?? row.close);
      const liveDayPct = typeof toNum === "function" ? toNum(row.dayPct ?? row.day_change_pct) : Number(row.dayPct ?? row.day_change_pct);
      if (Number.isFinite(livePrice)) mapped.price = livePrice;
      if (Number.isFinite(liveDayPct)) mapped.dayPct = liveDayPct;
      mapped.drawdown = normalizeDrawdown(row);
      mapped.screenerSnapshotFresh = snapshotIsFresh();
      mapped.screenerSnapshotStatus = row.snapshotStatus || "unknown";
      if (mapped.ticker) rowModels.set(safeTicker(mapped.ticker), mapped);
      return mapped;
    };
  }

  if (legacyBuildAlertItems) {
    buildAlertItems = function buildCanonicalAlertItems() {
      if (state.staticMode && !snapshotCanDriveAlerts()) return [];
      return legacyBuildAlertItems();
    };
  }

  currentQuoteFor = function currentQuoteForV2(symbol) {
    const ticker = safeTicker(symbol);
    const selectedTicker = safeTicker(state.selected);
    const existing = legacyCurrentQuoteFor(ticker);
    if (ticker && ticker === selectedTicker && state.staticMode && state.staticLoaded && !hasSeries(state.quotes[ticker])) void loadTechnicalShard(ticker);
    return existing;
  };

  loadStaticData = async function loadStaticDataV2(options = {}) {
    await legacyLoadStaticData(options);
    const technical = state.staticPayloads?.technical || {};
    if (technical.__technicalV2 && state.selected) await loadTechnicalShard(state.selected);
    renderFreshnessNotice();
  };

  if (typeof setInterval === "function") setInterval(renderFreshnessNotice, 60000);

  window.StockcheckTechnicalV2 = Object.freeze({
    version: "10.7.8",
    snapshotSchema: SCREENER_SNAPSHOT_SCHEMA,
    loadTechnicalShard,
    hasSeries,
    snapshotAgeMinutes,
    snapshotIsFresh,
    snapshotCanDriveAlerts,
    drawdownFor,
    getSnapshot: () => screenerSnapshot,
    isActive: () => Boolean(state.staticPayloads?.technical?.__technicalV2),
  });
})();
