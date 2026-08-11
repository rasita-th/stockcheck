"use strict";

const assert = require("node:assert/strict");
const {
  AFTER_CLOSE_FULL_SCHEDULE,
  isMarketSession,
  resolveProducerAdmission,
} = require("../scripts/live-refresh-dedupe.js");

const now = new Date("2026-08-11T16:30:00Z");

function decide(overrides = {}) {
  return resolveProducerAdmission({
    eventName: "schedule",
    eventSchedule: "7,17,27,37,47,57 * * * 1-5",
    currentRunId: 200,
    runs: [],
    now,
    ...overrides,
  });
}

assert.deepEqual(decide(), {
  allow: true,
  reason: "intraday_schedule_due",
  blockingRunId: null,
});

assert.equal(
  decide({ runs: [{ id: 199, status: "in_progress", conclusion: null }] }).allow,
  false,
  "a delayed schedule must not queue behind an older active producer",
);

assert.equal(
  decide({ runs: [{ id: 201, status: "in_progress", conclusion: null }] }).allow,
  true,
  "the oldest simultaneous schedule wins so two gates cannot cancel each other",
);

assert.equal(
  decide({
    runs: [{
      id: 198,
      status: "completed",
      conclusion: "success",
      run_started_at: "2026-08-11T16:23:00Z",
      completed_at: "2026-08-11T16:25:00Z",
    }],
  }).reason,
  "recent_success",
);

assert.equal(
  decide({
    runs: [{
      id: 198,
      status: "completed",
      conclusion: "success",
      run_started_at: "2026-08-11T16:17:00Z",
      completed_at: "2026-08-11T16:19:59Z",
    }],
  }).allow,
  true,
  "a success older than the retry cooldown must not suppress a due refresh",
);

assert.equal(
  decide({
    runs: [{
      id: 198,
      status: "completed",
      conclusion: "success",
      run_started_at: "2026-08-11T13:17:00Z",
      completed_at: "2026-08-11T13:18:00Z",
    }],
    now: new Date("2026-08-11T13:27:00Z"),
  }).allow,
  true,
  "an outside-hours no-op success must not delay the opening refresh",
);

assert.equal(
  decide({ eventName: "workflow_dispatch", runs: [{ id: 199, status: "in_progress" }] }).allow,
  true,
  "explicit watchdog/manual dispatches remain serialized and are never deduped",
);

assert.equal(
  decide({
    eventSchedule: AFTER_CLOSE_FULL_SCHEDULE,
    runs: [{ id: 199, status: "in_progress" }],
  }).reason,
  "after_close_full_refresh",
  "the after-close full refresh must never be discarded by intraday dedupe",
);

assert.equal(isMarketSession("2026-08-11T13:25:00Z"), true);
assert.equal(isMarketSession("2026-08-11T13:24:00Z"), false);

console.log("live refresh delayed-schedule admission policy passed");
