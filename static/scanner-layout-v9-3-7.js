(() => {
  'use strict';
  /* v9.4 stability recovery: disable runtime DOM relocation.
     Moving live scanner panels broke event handlers and hid original content. */
  document.documentElement.dataset.scannerLayout = 'native';
  window.StockRadarBalancedLayout = { version: '9.4.0-stable', disabled: true };
})();
