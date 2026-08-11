"use strict";

const AFTER_CLOSE_FULL_SCHEDULE = "41 21 * * 1-5";
const RECENT_SUCCESS_MS = 10 * 60 * 1000;
const MARKET_CLOCK = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function isMarketSession(timestamp) {
  const value = new Date(timestamp);
  if (!Number.isFinite(value.getTime())) return false;
  const parts = Object.fromEntries(
    MARKET_CLOCK.formatToParts(value).map(({ type, value: partValue }) => [type, partValue]),
  );
  if (["Sat", "Sun"].includes(parts.weekday)) return false;
  const minuteOfDay = Number(parts.hour) * 60 + Number(parts.minute);
  return minuteOfDay >= 9 * 60 + 25 && minuteOfDay <= 16 * 60 + 20;
}

function resolveProducerAdmission({
  eventName,
  eventSchedule,
  currentRunId,
  runs,
  now = new Date(),
}) {
  if (eventName !== "schedule") {
    return { allow: true, reason: "explicit_trigger", blockingRunId: null };
  }
  if (eventSchedule === AFTER_CLOSE_FULL_SCHEDULE) {
    return { allow: true, reason: "after_close_full_refresh", blockingRunId: null };
  }

  const currentId = Number(currentRunId);
  const active = runs.find((run) => {
    const runId = Number(run.id);
    return (
      Number.isFinite(runId) &&
      runId < currentId &&
      ["queued", "in_progress", "waiting", "pending"].includes(run.status)
    );
  });
  if (active) {
    return {
      allow: false,
      reason: `older_producer_${active.status}`,
      blockingRunId: Number(active.id),
    };
  }

  const nowMs = now.getTime();
  const recentSuccess = runs.find((run) => {
    if (Number(run.id) === currentId || run.status !== "completed" || run.conclusion !== "success") {
      return false;
    }
    if (!isMarketSession(run.run_started_at || run.created_at)) return false;
    const completedMs = Date.parse(run.completed_at || run.updated_at || "");
    const ageMs = nowMs - completedMs;
    return Number.isFinite(completedMs) && ageMs >= 0 && ageMs <= RECENT_SUCCESS_MS;
  });
  if (recentSuccess) {
    return {
      allow: false,
      reason: "recent_success",
      blockingRunId: Number(recentSuccess.id),
    };
  }

  return { allow: true, reason: "intraday_schedule_due", blockingRunId: null };
}

module.exports = {
  AFTER_CLOSE_FULL_SCHEDULE,
  RECENT_SUCCESS_MS,
  isMarketSession,
  resolveProducerAdmission,
};
