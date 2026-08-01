/* Ensure the canonical screener snapshot wins the initial static-load race. */
(() => {
  "use strict";

  const MAX_WAIT_MS = 15000;
  const POLL_MS = 100;
  const startedAt = Date.now();
  let running = false;
  let completed = false;

  function isStaticHost() {
    try {
      return Boolean(state?.staticMode) || (typeof isStaticDeployHost === "function" && isStaticDeployHost());
    } catch (_) {
      return /github\.io$/i.test(location.hostname || "");
    }
  }

  function canonicalActive() {
    return Boolean(state?.staticPayloads?.technical?.__screenerSnapshot);
  }

  async function activateCanonicalSnapshot() {
    if (running || completed || !isStaticHost()) return;
    running = true;
    try {
      await loadStaticData({ message: "Loading canonical screener snapshot…" });
      completed = canonicalActive();
      if (!completed) throw new Error("canonical snapshot did not become active");
      if (typeof renderAll === "function") renderAll();
      if (typeof renderAlertCenter === "function") renderAlertCenter();
      document.documentElement.dataset.canonicalScreener = "active";
    } catch (error) {
      console.error("Canonical screener bootstrap failed", error);
      document.documentElement.dataset.canonicalScreener = "failed";
    } finally {
      running = false;
    }
  }

  function poll() {
    if (completed || !isStaticHost()) return;
    if (canonicalActive()) {
      completed = true;
      document.documentElement.dataset.canonicalScreener = "active";
      return;
    }
    const initialLoadFinished = Boolean(state?.staticLoaded);
    const timedOut = Date.now() - startedAt >= MAX_WAIT_MS;
    if (initialLoadFinished || timedOut) void activateCanonicalSnapshot();
    if (!completed && Date.now() - startedAt < MAX_WAIT_MS + 5000) setTimeout(poll, POLL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setTimeout(poll, 0), { once: true });
  } else {
    setTimeout(poll, 0);
  }
})();
