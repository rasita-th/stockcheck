(() => {
  'use strict';
  /* v9.4 stability recovery: disable the experimental duplicate dashboard.
     The original scanner rendered by app.js is the single source of truth. */
  document.documentElement.dataset.scannerDashboard = 'native';
  window.StockRadarDashboard = { version: '9.4.0-stable', disabled: true };
})();
