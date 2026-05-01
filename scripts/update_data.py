#!/usr/bin/env python3
"""Compatibility wrapper.

For V2.8 GitHub Pages Hybrid Mode, use:
  python scripts/update_technical_data.py     # every ~15 minutes
  python scripts/update_fundamental_data.py   # daily/manual

Running this wrapper generates both layers once.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

subprocess.check_call([sys.executable, str(ROOT / "scripts" / "update_fundamental_data.py")])
subprocess.check_call([sys.executable, str(ROOT / "scripts" / "update_technical_data.py")])
