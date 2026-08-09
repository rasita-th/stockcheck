import fs from "node:fs";
import assert from "node:assert/strict";

const site = fs.readFileSync("site/final-ui-coordinator.js", "utf8");
const mirror = fs.readFileSync("static/final-ui-coordinator.js", "utf8");

assert.equal(site, mirror, "site/static final UI coordinator mirrors must match");

assert.match(
  site,
  /if \(wasOpen\) document\.body\.classList\.remove\("stock-detail-open"\);/,
  "closeStockDetail must not mutate the body class when Stock Detail is already closed"
);

assert.match(
  site,
  /if \(!scannerViewIsActive\(\) && document\.body\.classList\.contains\("stock-detail-open"\)\) closeStockDetail\(\{ restoreFocus: false \}\);/,
  "body-class observer must call closeStockDetail only when the detail-open class is present"
);

assert.doesNotMatch(
  site,
  /clearTimeout\(detailCloseTimer\);\s*document\.body\.classList\.remove\("stock-detail-open"\);/,
  "unconditional stock-detail-open removal can self-trigger the body-class MutationObserver"
);

console.log("final UI view observer contract passed: detail close is idempotent");
