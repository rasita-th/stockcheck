# Stockcheck Python Local v8

รันบนเครื่องด้วย Python local server:

```bash
python app.py
```

แล้วเปิด:

```text
http://localhost:8787
```

## มีอะไรในเวอร์ชันนี้

- Technical tab: EMA 5/20/89/200, RSI, MACD 12/26/9, Vol/20D, 52W High/Low
- Fundamental tab: Level 1 rules-based summary จาก Yahoo quoteSummary แบบ best-effort
- Fundamental Highlight ใน detail view
- Watchlist ล่าสุดรวม 378 tickers อยู่ใน `watchlist.txt`
- รองรับ iPhone ผ่าน card view
- Save Screener ใน browser localStorage

## หมายเหตุ

- รอบแรกที่ scan watchlist ใหญ่ 378 ตัวอาจใช้เวลาหลายนาที เพราะ local app ต้องดึงข้อมูลเองจาก Yahoo/Stooq
- ถ้าต้องการให้เร็วขึ้น ให้ลดรายชื่อใน watchlist หรือพิมพ์เฉพาะกลุ่มที่อยาก scan ในช่อง Watchlist
- ตั้ง `INCLUDE_FUNDAMENTALS=0` เพื่อปิดการดึง fundamental data และให้ scan เร็วขึ้น
- ตั้ง `SCAN_WORKERS=4` หรือ `SCAN_WORKERS=8` เพื่อปรับจำนวน concurrent workers

ตัวอย่าง:

```bash
INCLUDE_FUNDAMENTALS=0 python app.py
```

## v8.1 Fundamental hotfix
- Added Yahoo quote v7 fallback when Yahoo quoteSummary blocks/404s.
- Added SEC companyfacts no-key fallback for US quarterly revenue/net income/EPS plus QoQ/YoY.
- Fundamental tab still shows N/A for ETFs, non-US tickers, or companies without enough SEC/Yahoo data.
