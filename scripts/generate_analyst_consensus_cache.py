#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
DIRS=[ROOT/"data",ROOT/"site"/"data",ROOT/"static"/"data"]
API_KEY=os.getenv("FINNHUB_API_KEY","").strip(); MAX_CALLS=int(os.getenv("ANALYST_CONSENSUS_MAX_CALLS_PER_RUN","2")); TTL=float(os.getenv("ANALYST_CONSENSUS_TTL_HOURS","24")); DELAY=float(os.getenv("FINNHUB_MIN_DELAY_SECONDS","1.1"))
NON_US=(".BK",".SET",".TO",".V",".CN",".L",".HK",".SS",".SZ",".KS",".KQ",".T",".AX",".PA",".DE",".SW",".MI",".AS",".ST",".OL",".CO")
def now(): return datetime.now(timezone.utc).isoformat()
def load(path:Path,default):
    try:
        if path.exists() and path.stat().st_size: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e: print(f"::warning::{path}: {e}")
    return default
def norm(v):
    t=str(v or "").strip().upper().replace("$","")
    return t if re.match(r"^[A-Z0-9.\-]{1,18}$",t) else ""
def us(t): return bool(t) and not any(t.endswith(x) for x in NON_US)
def parse_dt(v):
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00")); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return None
def age(v):
    d=parse_dt(v); return None if not d else (datetime.now(timezone.utc)-d).total_seconds()/3600
def rows(entry):
    if isinstance(entry,list): return entry
    if isinstance(entry,dict):
        for k in ("rows","data","trend"):
            if isinstance(entry.get(k),list): return entry[k]
    return []
def existing():
    for d in DIRS:
        x=load(d/"recommendation_trends.json",None)
        if isinstance(x,dict): x.setdefault("items",{}); return x
    return {"items":{},"source":"finnhub_recommendation_trends"}
def universe():
    scored=[]
    for d in [ROOT/"site"/"data",ROOT/"static"/"data",ROOT/"data"]:
        x=load(d/"technical.json",{})
        for r in x.get("rows",[]) if isinstance(x,dict) else []:
            t=norm(r.get("ticker") or r.get("symbol")); score=float(r.get("score") or 0)
            if us(t): scored.append((score,t))
    out=[]
    for _,t in sorted(scored,reverse=True):
        if t not in out: out.append(t)
    return out
def stale(t,c):
    e=c.get("items",{}).get(t) or c.get(t)
    if not e:return True
    h=age(e.get("updated_at") if isinstance(e,dict) else None)
    if not rows(e): return h is None or h>=6
    return h is None or h>=TTL
def fetch(t):
    if not API_KEY: raise RuntimeError("FINNHUB_API_KEY missing")
    url="https://finnhub.io/api/v1/stock/recommendation?"+urllib.parse.urlencode({"symbol":t,"token":API_KEY})
    with urllib.request.urlopen(url,timeout=20) as res: data=json.loads(res.read().decode())
    return [{"symbol":t,"period":r.get("period"),"strongBuy":r.get("strongBuy"),"buy":r.get("buy"),"hold":r.get("hold"),"sell":r.get("sell"),"strongSell":r.get("strongSell")} for r in data if isinstance(r,dict)] if isinstance(data,list) else []
def save(c):
    text=json.dumps(c,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    for d in DIRS:d.mkdir(parents=True,exist_ok=True);(d/"recommendation_trends.json").write_text(text,encoding="utf-8")
def main():
    c=existing(); c.setdefault("items",{}); q=[t for t in universe() if stale(t,c)]
    diag={"updated_at":now(),"api_enabled":bool(API_KEY),"queue_size":len(q),"max_calls":MAX_CALLS,"refreshed":[],"errors":[]}
    if not API_KEY: diag["errors"].append("FINNHUB_API_KEY missing")
    else:
        for t in q[:MAX_CALLS]:
            try:
                rr=fetch(t); e={"ticker":t,"updated_at":now(),"status":"ok" if rr else "empty","rows":rr}; c["items"][t]=e;c[t]=e;diag["refreshed"].append(t);time.sleep(DELAY)
            except Exception as ex: diag["errors"].append(f"{t}: {ex}")
    c.update({"generated_at":now(),"source":"finnhub_recommendation_trends","ttl_hours":TTL,"diagnostics":diag});save(c);print(diag)
if __name__=="__main__":main()
