# Full-Width UI Architecture

## เป้าหมาย

Desktop ต้องใช้พื้นที่หน้าจออย่างมีประโยชน์ โดยไม่ทำให้ feature ใด feature หนึ่งขยายจนทำให้ส่วนอื่นหาย

## Layout model

### Desktop Wide — 1440px ขึ้นไป

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Header: Brand | Search | Scanner | Today | Memo | Market Pulse | Status    │
├────────────────┬─────────────────────────────────────┬──────────────────────┤
│ Controls Rail  │ Scanner Workspace                   │ Insight Rail         │
│                │                                     │                      │
│ Watchlist      │ Focus chips                         │ Selected ticker      │
│ Screeners      │ Data status                         │ Chart                │
│ Filters        │ Technical/Fundamental tabs          │ Focus reasons        │
│ Alerts summary │ Results table                       │ Setup score          │
│                │                                     │ Fundamentals         │
│                │                                     │ Playbook / Memo      │
└────────────────┴─────────────────────────────────────┴──────────────────────┘
```

Recommended ratio:

```text
Left:   clamp(280px, 20vw, 360px)
Center: minmax(640px, 1fr)
Right:  clamp(360px, 25vw, 520px)
```

Center เป็นพื้นที่ยืดหยุ่นหลัก

### Desktop Standard — 1100–1439px

```text
Left rail | Scanner + Detail stacked
```

- Left rail คงอยู่
- Scanner กว้างเต็มพื้นที่ที่เหลือ
- Detail Panel ลงใต้ Scanner หรือเปิดเป็น drawer
- ห้ามบีบ Scanner ให้เหลือคอลัมน์แคบ

### Tablet — 768–1099px

```text
Controls summary
Scanner full width
Detail below
```

- Filters เป็น collapsible section
- ตารางมี horizontal scroll ภายใน panel
- ไม่ให้ทั้ง page horizontal scroll

### Mobile — ต่ำกว่า 768px

ใช้โครงสร้างเดิม:

- navigation 4 ปุ่ม
- Scanner card mode
- Filters bottom sheet
- Detail modal/sheet
- Focus tag แสดง 1 รายการสูงสุด

## Feature allocation เพื่อไม่ให้เกิดพื้นที่ว่าง

### Left Rail

- Watchlist
- Saved Screeners
- Market groups
- Scan filters
- Compact alert summary

ถ้า section ใดไม่มีข้อมูล ให้แสดง empty state ขนาดพอดี ไม่จองความสูงเต็มจอ

### Center Workspace

- Scanner status
- Focus filter chips
- Technical/Fundamental tabs
- Scanner table
- Pagination / row count
- data freshness

นี่คือพื้นที่ที่ต้องขยายมากที่สุด

### Right Insight Rail

ใช้พื้นที่แนวตั้งทั้งหมดแบบ stacked cards:

1. Selected ticker header
2. Price/EMA chart
3. “ทำไมต้องดูตัวนี้วันนี้”
4. Setup score
5. Fundamental snapshot
6. Playbook
7. Memo link

ถ้าไม่มี ticker เลือก ให้แสดง compact onboarding state ไม่ใช่พื้นที่ดำว่าง

## กฎโครงสร้าง

1. ห้ามเพิ่ม wrapper ใหม่เพื่อย้าย panel เดิม
2. ห้าม clone `Scanner Results`
3. ห้ามสร้าง navigation ใหม่
4. ห้ามใช้ `position:fixed` กับ content panels
5. ห้ามใช้ `display:none` เพื่อปิด UI รุ่นเดิม
6. Layout ต้องมาจาก stylesheet เดียว
7. JavaScript ไม่รับผิดชอบตำแหน่ง panel
8. CSS ต้องใช้ selector ของ element เดิมแบบ scoped
