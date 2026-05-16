# Stock Timing Radar — GitHub Pages Deploy v6.6

เวอร์ชันนี้เตรียมไว้สำหรับ deploy ลง GitHub Pages โดยตรง และยังคงแยกข้อมูลเป็น 2 ชั้นเหมือนเดิม:

- `site/data/technical.json` — ข้อมูล Technical: price, EMA5/20/89/200, % vs EMA, RSI, MACD, volume, score
- `site/data/fundamental.json` — ข้อมูล Fundamental: SEC companyfacts, earnings snapshot, guidance, AI view/highlights

หน้าเว็บ static จะ merge 2 ไฟล์นี้ใน browser แล้วแสดงผ่านแท็บ `Technical` และ `Fundamental` ใน UI เดียวกัน

## โครงสร้างสำคัญ

```text
site/
  index.html
  styles.css
  app.js
  data/
    technical.json
    fundamental.json
    scanner.json
.github/workflows/
  deploy-pages.yml          # update technical data + deploy Pages
  update-fundamental.yml    # update fundamental data daily/manual
scripts/
  update_technical_data.py
  update_fundamental_data.py
app.py                      # local Python backend / data engine
watchlist.txt               # list หุ้นที่ workflow ใช้ generate data
```

## วิธี deploy ครั้งแรก

1. แตก ZIP แล้วอัปโหลดทุกไฟล์ขึ้น repo GitHub
2. ไปที่ `Settings → Pages → Build and deployment → Source`
3. เลือก `GitHub Actions`
4. ไปที่แท็บ `Actions`
5. รัน workflow นี้ก่อน:
   - `Update static fundamental data`
6. จากนั้นรัน:
   - `Update technical data and deploy GitHub Pages`

หลังจากนั้น GitHub Pages จะ deploy จากโฟลเดอร์ `site/`

## รอบอัปเดตข้อมูล

- Technical workflow รันทุกประมาณ 15 นาทีตาม cron และ deploy Pages ใหม่
- Fundamental workflow รันวันละครั้ง หรือกด manual ได้
- ถ้าต้องเพิ่ม/ลดหุ้นใน deploy จริง ให้แก้ `watchlist.txt` แล้ว commit จากนั้นรัน workflow ใหม่

## ใช้ local Python ทดสอบก่อน deploy

```bash
python app.py
```

เปิด:

```text
http://localhost:8787
```

Local mode จะใช้ `/api/scan` และ `/api/quote` จาก Python backend

GitHub Pages mode จะใช้ static JSON จาก `site/data/` แทน เพราะ GitHub Pages รัน Python backend ไม่ได้

## หมายเหตุ

- Analyst Consensus เปลี่ยนเป็นปุ่ม link ไป Yahoo Finance Analysis แล้ว ไม่ต้องใช้ Alpha Vantage key
- Technical / Fundamental tabs ยังแยกเหมือนเดิม
- ถ้าหน้าเว็บขึ้นว่า `Not generated yet` ให้รัน workflow ใน GitHub Actions ก่อน
