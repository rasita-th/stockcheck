/* Stockcheck v10.7.3 storage compatibility guard. */
(() => {
  "use strict";

  const memory = new Map();
  const fallback = {
    getItem(key) {
      const normalized = String(key);
      return memory.has(normalized) ? memory.get(normalized) : null;
    },
    setItem(key, value) {
      memory.set(String(key), String(value));
    },
    removeItem(key) {
      memory.delete(String(key));
    },
    clear() {
      memory.clear();
    },
    key(index) {
      return Array.from(memory.keys())[Number(index)] ?? null;
    },
    get length() {
      return memory.size;
    },
  };

  try {
    const storage = window.localStorage;
    const probe = "__stockcheck_storage_probe__";
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    window.__stockcheckStorageMode = "native";
  } catch (error) {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      enumerable: true,
      value: fallback,
    });
    window.__stockcheckStorageMode = "memory";
    console.warn(
      "Persistent browser storage is unavailable; using in-memory session storage.",
      error,
    );
  }
})();
