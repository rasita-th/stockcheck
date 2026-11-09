"use strict";

const assert = require("node:assert/strict");
const { classifyProducerExecution } = require("../scripts/live-producer-execution.js");

const run = (updated_at = "2026-11-09T15:00:00Z", conclusion = "success") =>
  ({ id: 42570294592, updated_at, conclusion });
const steps = (quote, snapshot) => [{
  name: "refresh",
  steps: [
    { name: "Refresh latest quotes in bounded batches", conclusion: quote },
    { name: "Build canonical intraday screener snapshot", conclusion: snapshot },
  ],
}];

assert.equal(classifyProducerExecution(run(), steps("success", "success")).kind, "produced");
assert.equal(classifyProducerExecution(run(), steps("success", "skipped")).state, "failure");
assert.equal(classifyProducerExecution(run(), steps("skipped", "skipped")).state, "failure",
  "green workflow with no actual data during market hours must fail the producer status");
assert.equal(classifyProducerExecution(run("2026-11-09T05:59:00Z"), steps("skipped", "skipped")).kind, "closed_noop",
  "planned premarket no-op must not claim to have generated data");
assert.equal(classifyProducerExecution(run("2026-11-09T05:59:00Z"), steps("skipped", "skipped")).state, "success");
assert.equal(classifyProducerExecution(run("2026-11-09T15:00:00Z", "failure"), steps("failure", "skipped")).state, "failure");

console.log("live producer execution status contract passed");
