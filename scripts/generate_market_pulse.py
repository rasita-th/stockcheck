#!/usr/bin/env python3
from __future__ import annotations
import json, math, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parents[1]
UNIVERSE_PATHS=[ROOT/"data/market_universe.json",ROOT/"site/data/market_universe.json",ROOT/"static/data/market_universe.json"]
OUTPUT_DIRS=[ROOT/"data/generated",ROOT/"data",ROOT/"site/data",ROOT/"static/data"]

def universe():
    for p in UNIVERSE_PATHS:
        if p.exists() and p.stat().st_size:
            x=json.loads(p.read_text(encoding="utf-8"))
            if isinstance(x,dict): return x
    raise SystemExit("market_universe.json not found")

def safe(v):
    try:
        n=float(v); return round(n,2) if math.isfinite(n) else None
    except Exception:return None

def change(s:pd.Series,n:int):
    s=s.dropna()
    return None if len(s)<=n or float(s.iloc[-n-1])==0 else safe((float(s.iloc[-1])/float(s.iloc[-n-1])-1)*100)

def ytd(s):
    s=s.dropna()
    if s.empty:return None
    z=s[s.index.year==s.index[-1].year]
    return None if len(z)<2 or float(z.iloc[0])==0 else safe((float(z.iloc[-1])/float(z.iloc[0])-1)*100)

def get_one(symbol):
    last=None
    for attempt in range(3):
        try:
            h=yf.download(symbol,period="18mo",interval="1d",auto_adjust=True,progress=False,threads=False)
            if not h.empty:
                c=h["Close"]
                if isinstance(c,pd.DataFrame):c=c.iloc[:,0]
                c=c.dropna()
                if not c.empty:return c
        except Exception as e:last=e
        time.sleep(1+attempt)
    raise RuntimeError(str(last or "no price history"))

def enrich(item,series):
    r=dict(item)
    r.update({"price":safe(series.iloc[-1]),"day_pct":change(series,1),"week_pct":change(series,5),"month_pct":change(series,21),"ytd_pct":ytd(series),"year_pct":change(series,252),"as_of":series.index[-1].strftime("%Y-%m-%d"),"status":"ok"})
    return r

def build(items,cache,failed):
    rows=[]
    for item in items:
        sym=item.get("symbol")
        try:
            if sym not in cache:cache[sym]=get_one(sym)
            rows.append(enrich(item,cache[sym]))
        except Exception as e:
            failed.append({"symbol":sym,"error":str(e)})
            r=dict(item);r.update({"price":None,"day_pct":None,"week_pct":None,"month_pct":None,"ytd_pct":None,"year_pct":None,"as_of":None,"status":"unavailable"});rows.append(r)
    return rows

def pulse(sectors,themes):
    out=[]
    for group,rows in (("sector",sectors),("theme",themes)):
        for r in rows:
            d,w=r.get("day_pct"),r.get("week_pct")
            if d is None and w is None:continue
            score=abs(d or 0)*1.3+abs(w or 0)*.7
            out.append({"symbol":r.get("symbol"),"label":r.get("label"),"group":group,"direction":"leading" if (w or 0)>0 else "lagging","day_pct":d,"week_pct":w,"month_pct":r.get("month_pct"),"score":round(score,2)})
    return sorted(out,key=lambda x:x["score"],reverse=True)[:10]

def save(payload):
    text=json.dumps(payload,ensure_ascii=False,indent=2)+"\n"
    for d in OUTPUT_DIRS:
        d.mkdir(parents=True,exist_ok=True);(d/"market_pulse.json").write_text(text,encoding="utf-8");print("wrote",d/"market_pulse.json")

def main():
    u=universe();cache={};failed=[]
    globals_=build(u.get("global_markets",[]),cache,failed)
    us_indices=build(u.get("us_indices",[]),cache,failed)
    sectors=build(u.get("us_sectors",[]),cache,failed)
    themes=build(u.get("themes",[]),cache,failed)
    total=len(cache)+len(failed);ok=sum(1 for x in globals_+us_indices+sectors+themes if x.get("status")=="ok")
    payload={"schema_version":"2.0","version":"9.2.1","generated_at":datetime.now(timezone.utc).isoformat(),"source":"Yahoo Finance via yfinance; indices and ETF proxies","status":"ok" if not failed else ("partial" if ok else "error"),"successful_symbols":ok,"requested_rows":len(globals_)+len(us_indices)+len(sectors)+len(themes),"failed_symbols":failed,"global_markets":globals_,"us_indices":us_indices,"us_sectors":sectors,"themes":themes,"today_pulse":pulse(sectors,themes),"breadth":{"sectors_positive_day":sum(1 for r in sectors if (r.get("day_pct") or 0)>0),"sectors_positive_week":sum(1 for r in sectors if (r.get("week_pct") or 0)>0),"sector_count":sum(1 for r in sectors if r.get("status")=="ok")}}
    save(payload)
if __name__=="__main__":main()
