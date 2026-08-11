"use strict";

const MARKET_OPEN_MINUTE = 9 * 60 + 25;
const MARKET_CLOSE_MINUTE = 16 * 60 + 20;
const TARGET_QUOTE_AGE_MINUTES = 15;
const RETRY_COOLDOWN_MINUTES = 10;

function parseTimestamp(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const normalized = raw.endsWith(" UTC") ? `${raw.slice(0, -4).replace(" ", "T")}Z` : raw;
  const millis = Date.parse(normalized);
  return Number.isFinite(millis) ? millis : null;
}

function newYorkParts(now) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    weekday: values.weekday || "",
    minutes: Number(values.hour || 0) * 60 + Number(values.minute || 0),
  };
}

function isMarketOpen(now) {
  const local = newYorkParts(now);
  return !["Sat", "Sun"].includes(local.weekday)
    && local.minutes >= MARKET_OPEN_MINUTE
    && local.minutes < MARKET_CLOSE_MINUTE;
}

function ageMinutes(timestamp, nowMillis) {
  const parsed = parseTimestamp(timestamp);
  if (parsed === null) return null;
  return Math.max(0, Math.round(((nowMillis - parsed) / 60000) * 10) / 10);
}

function resolveWatchdogDecision({
  now = new Date(),
  quoteTimestamp,
  activeProducer = false,
  producerCompletedAt = null,
}) {
  const current = now instanceof Date ? now : new Date(now);
  const nowMillis = current.getTime();
  if (!Number.isFinite(nowMillis)) throw new TypeError("now must be a valid date");
  const marketOpen = isMarketOpen(current);
  const quoteAgeMinutes = ageMinutes(quoteTimestamp, nowMillis);
  const base = { marketOpen, quoteAgeMinutes, waitSeconds: 0 };

  if (!marketOpen) return { action: "stop", reason: "market_closed", ...base };
  if (activeProducer) return { action: "stop", reason: "producer_active", ...base };

  const completionAgeMinutes = ageMinutes(producerCompletedAt, nowMillis);
  const quoteWait = quoteAgeMinutes === null
    ? 0
    : Math.max(0, TARGET_QUOTE_AGE_MINUTES - quoteAgeMinutes);
  const retryWait = completionAgeMinutes === null
    ? 0
    : Math.max(0, RETRY_COOLDOWN_MINUTES - completionAgeMinutes);
  const waitMinutes = Math.max(quoteWait, retryWait);
  if (waitMinutes > 0) {
    return {
      action: "wait",
      reason: retryWait >= quoteWait ? "retry_cooldown" : "quote_fresh",
      ...base,
      waitSeconds: Math.max(1, Math.ceil(waitMinutes * 60)),
    };
  }
  return {
    action: "dispatch",
    reason: quoteAgeMinutes === null ? "quote_missing" : "quote_due",
    ...base,
  };
}

function extractQuoteTimestamp(payload) {
  if (!payload || typeof payload !== "object") return null;
  return payload.generated_at
    || payload.generatedAt
    || payload.generatedAtQuote
    || payload.updated_at
    || null;
}

module.exports = {
  RETRY_COOLDOWN_MINUTES,
  TARGET_QUOTE_AGE_MINUTES,
  extractQuoteTimestamp,
  isMarketOpen,
  parseTimestamp,
  resolveWatchdogDecision,
};
