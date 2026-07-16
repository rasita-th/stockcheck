#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
required=[
 'site/scanner-dashboard.css','site/scanner-dashboard.js',
 'static/scanner-dashboard.css','static/scanner-dashboard.js',
 'site/scanner-layout-v9-3-1.css','site/scanner-layout-v9-3-1.js',
 'static/scanner-layout-v9-3-1.css','static/scanner-layout-v9-3-1.js'
]
missing=[p for p in required if not (root/p).exists()]
if missing: raise SystemExit('Missing: '+', '.join(missing))
for rel in ('site/index.html','static/index.html'):
 p=root/rel
 if p.exists():
  t=p.read_text(encoding='utf-8')
  for asset in ('scanner-dashboard.css','scanner-dashboard.js','scanner-layout-v9-3-1.css','scanner-layout-v9-3-1.js'):
   if asset not in t: raise SystemExit(f'{asset} not injected in {rel}')
print('v9.3.1 full-width scanner layout validated')
