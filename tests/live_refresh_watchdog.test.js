"use strict";

const assert = require("node:assert/strict");
const {
  resolveWatchdogDecision,
} = require("../scripts/live-refresh-watchdog.js");

const now = new Date("2026-08-11T15:00:00Z"); // 11:00 America/New_York

assert.deepEqual(
  resolveWatchdogDecision({
    now,
    quoteTimestamp: "2026-08-11T14:40:00Z",
    activeProducer: false,
    producerCompletedAt: "2026-08-11T14:42:00Z",
  }),
  {
    action: "dispatch",
    reason: "quote_due",
    marketOpen: true,
    quoteAgeMinutes: 20,
    waitSeconds: 0,
  },
);

assert.equal(
  resolveWatchdogDecision({
    now,
    quoteTimestamp: "2026-08-11T14:55:00Z",
    activeProducer: false,
    producerCompletedAt: "2026-08-11T14:56:00Z",
  }).action,
  "wait",
  "a fresh quote must not cause a duplicate refresh",
);

assert.deepEqual(
  resolveWatchdogDecision({
    now,
    quoteTimestamp: "2026-08-11T14:20:00Z",
    activeProducer: true,
    producerCompletedAt: "2026-08-11T14:30:00Z",
  }),
  {
    action: "stop",
    reason: "producer_active",
    marketOpen: true,
    quoteAgeMinutes: 40,
    waitSeconds: 0,
  },
);

assert.equal(
  resolveWatchdogDecision({
    now,
    quoteTimestamp: "2026-08-11T14:20:00Z",
    activeProducer: false,
    producerCompletedAt: "2026-08-11T14:55:00Z",
  }).action,
  "wait",
  "a failed/empty producer chain must respect the retry cooldown",
);

assert.equal(
  resolveWatchdogDecision({
    now: new Date("2026-08-11T21:00:00Z"),
    quoteTimestamp: "2026-08-11T20:30:00Z",
    activeProducer: false,
    producerCompletedAt: "2026-08-11T20:40:00Z",
  }).reason,
  "market_closed",
);

assert.equal(
  resolveWatchdogDecision({
    now,
    quoteTimestamp: null,
    activeProducer: false,
    producerCompletedAt: "2026-08-11T14:40:00Z",
  }).action,
  "dispatch",
  "missing canonical quote identity must fail safe during market hours",
);

console.log("live refresh watchdog policy tests passed");
