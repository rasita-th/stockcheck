#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

os.environ["INCLUDE_FUNDAMENTALS"] = "0"
os.environ.setdefault("SCAN_WORKERS", os.environ.get("TECHNICAL_SCAN_WORKERS", "8"))
ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "watchlist.txt"
OUTPUT_DIRS = [ROOT / "data", ROOT / "site" / "data", ROOT / "static" / "data"]
sys.path.insert(0, str(ROOT))
from app import scan_symbols  # noqa: E402

def read_watchlist() -> list[str]:
    if not WATCHLIST.exists():
        return ["NVDA","PLTR","TSLA","TSM","COST","MSFT","AMZN","ORCL","HOOD","MSTR"]
    out=[]
    for token in re.split(r"[\s,;|]+", WATCHLIST.read_text(encoding="utf-8", errors="replace")):
        t=token.strip().upper().replace("$","")
        if t and not t.startswith("#") and t not in out: out.append(t)
    return out

def write_all(name: str, payload: dict) -> None:
    text=json.dumps(payload,ensure_ascii=False,separators=(",",":"))
    for d in OUTPUT_DIRS:
        d.mkdir(parents=True,exist_ok=True)
        (d/name).write_text(text,encoding="utf-8")
        print("wrote",d/name)

def main() -> None:
    symbols=read_watchlist(); started=time.time()
    range_=os.getenv("TECHNICAL_RANGE","1y"); interval=os.getenv("TECHNICAL_INTERVAL","1d")
    payload=scan_symbols(symbols,range_=range_,interval=interval)
    rows=payload.get("rows") or []
    if not rows: raise SystemExit("No technical rows generated; refusing to overwrite live data")
    generated=payload.get("generatedAt") or datetime.now(timezone.utc).isoformat()
    payload.update({"mode":"github-pages-live-v9","dataLayer":"technical","generatedAt":generated,"generatedAtTechnical":generated,"range":range_,"interval":interval,"durationSeconds":round(time.time()-started,2)})
    scanner=dict(payload); scanner["mode"]="github-pages-live-scanner-v9"
    write_all("technical.json",payload); write_all("scanner.json",scanner)
    print(f"Generated {len(rows)} rows with {len(payload.get('errors',[]))} errors")
if __name__=="__main__": main()
