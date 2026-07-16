#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
required=["site/scanner-dashboard.css","site/scanner-dashboard.js","static/scanner-dashboard.css","static/scanner-dashboard.js"]
missing=[p for p in required if not (root/p).exists()]
if missing: raise SystemExit("Missing: "+", ".join(missing))
for rel in ["site/index.html","static/index.html"]:
 p=root/rel
 if p.exists():
  t=p.read_text(encoding="utf-8")
  if "scanner-dashboard.css" not in t or "scanner-dashboard.js" not in t: raise SystemExit(f"Assets not injected in {rel}")
print("Scanner dashboard assets validated")
