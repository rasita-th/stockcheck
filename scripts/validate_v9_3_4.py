#!/usr/bin/env python3
from pathlib import Path
import sys
repo=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
errors=[]
for root in ('site','static'):
    d=repo/root
    if not d.exists(): continue
    for f in ('shared-app-shell-v9-3-4.css','shared-app-shell-v9-3-4.js','thai-time-v9-3-4.js','scanner-dashboard.css','scanner-dashboard.js','scanner-layout-v9-3-2.css','scanner-layout-v9-3-2.js'):
        if not (d/f).exists(): errors.append(f'missing {root}/{f}')
    for html in d.glob('*.html'):
        t=html.read_text(encoding='utf-8')
        for f in ('shared-app-shell-v9-3-4.css','shared-app-shell-v9-3-4.js','thai-time-v9-3-4.js'):
            if t.count(f)!=1: errors.append(f'{html}: expected exactly one reference to {f}, got {t.count(f)}')
        if 'v9-3-3' in t: errors.append(f'{html}: stale v9.3.3 asset reference remains')
    idx=d/'index.html'
    if idx.exists():
        t=idx.read_text(encoding='utf-8')
        for f in ('scanner-dashboard.css','scanner-dashboard.js','scanner-layout-v9-3-2.css','scanner-layout-v9-3-2.js'):
            if t.count(f)!=1: errors.append(f'{idx}: expected exactly one reference to {f}, got {t.count(f)}')
if errors:
    print('\n'.join(errors));raise SystemExit(1)
print('v9.3.4 validation passed: v9.3.2 retained, v9.3.3 removed, assets are single-instance')
