#!/usr/bin/env python3
from pathlib import Path
import re, sys
repo=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd().resolve()
errors=[]
for root in ('site','static'):
    d=repo/root
    if not d.exists(): continue
    for name in ('shared-app-shell-v9-3-3.css','shared-app-shell-v9-3-3.js','thai-time-v9-3-3.js'):
        if not (d/name).exists(): errors.append(f'missing {root}/{name}')
    htmls=list(d.glob('*.html'))
    if not htmls: errors.append(f'no html files in {root}')
    for p in htmls:
        text=p.read_text(encoding='utf-8')
        for asset in ('shared-app-shell-v9-3-3.css','shared-app-shell-v9-3-3.js','thai-time-v9-3-3.js'):
            if asset not in text: errors.append(f'{p.relative_to(repo)} missing {asset}')
    for required in ('index.html','market.html'):
        if not (d/required).exists(): errors.append(f'missing required route {root}/{required}')
if errors:
    print('Validation failed:')
    for e in errors: print('-',e)
    raise SystemExit(1)
print('v9.3.3 validation passed: shared header assets, required routes and Thai-time assets are present.')
