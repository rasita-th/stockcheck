"use strict";

const { isMarketOpen } = require("./live-refresh-watchdog.js");

const QUOTE_STEP = "Refresh latest quotes in bounded batches";
const SNAPSHOT_STEP = "Build canonical intraday screener snapshot";

function classifyProducerExecution(run, jobs) {
  const completedAt = new Date(run.updated_at || run.run_started_at || run.created_at);
  const marketOpen = Number.isFinite(completedAt.getTime()) && isMarketOpen(completedAt);
  const refresh = (jobs || []).find(job => job.name === "refresh");
  const steps = refresh && Array.isArray(refresh.steps) ? refresh.steps : [];
  const outcome = name => steps.find(step => step.name === name)?.conclusion || "missing";
  const quote = outcome(QUOTE_STEP);
  const snapshot = outcome(SNAPSHOT_STEP);

  if (run.conclusion !== "success") {
    return { kind: "failed", state: "failure", description: `Live producer ${run.conclusion || "failed"} (run ${run.id})` };
  }
  if (quote === "success" && snapshot === "success") {
    return { kind: "produced", state: "success", description: `Quote and snapshot generated (run ${run.id}); publish not yet verified` };
  }
  if (!marketOpen && quote === "skipped" && snapshot === "skipped") {
    return { kind: "closed_noop", state: "success", description: `No data generated outside market hours (run ${run.id})` };
  }
  return {
    kind: "incomplete",
    state: "failure",
    description: `No valid live data produced: quote=${quote}, snapshot=${snapshot} (run ${run.id})`.slice(0, 140),
  };
}

module.exports = { classifyProducerExecution };
