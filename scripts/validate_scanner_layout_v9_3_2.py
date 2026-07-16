#!/usr/bin/env python3
from pathlib import Path
import sys
repo=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
required=[
 'site/scanner-dashboard.css','site/scanner-dashboard.js','site/scanner-layout-v9-3-2.css','site/scanner-layout-v9-3-2.js',
 'static/scanner-dashboard.css','static/scanner-dashboard.js','static/scanner-layout-v9-3-2.css','static/scanner-layout-v9-3-2.js'
]
missing=[p for p in required if not (repo/p).exists()]
if missing: raise SystemExit('Missing: '+', '.join(missing))
for rel in ('site/index.html','static/index.html'):
 p=repo/rel
 if p.exists():
  text=p.read_text(encoding='utf-8')
  for asset in ('scanner-layout-v9-3-2.css','scanner-layout-v9-3-2.js'):
   if asset not in text: raise SystemExit(f'{rel} does not load {asset}')
print('v9.3.2 layout validation passed')
