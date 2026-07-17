# Regression and Acceptance Criteria

## Desktop layout

- [ ] viewport 1440px ใช้พื้นที่อย่างน้อย 95% ของความกว้าง
- [ ] viewport 1920px ไม่มีพื้นที่ดำว่างขนาดใหญ่สองข้าง
- [ ] Center workspace เป็นคอลัมน์ที่ขยายมากที่สุด
- [ ] Scanner table ไม่ถูกตัดโดย parent overflow
- [ ] Right rail ใช้พื้นที่แนวตั้งด้วย cards ที่มีประโยชน์
- [ ] ไม่มี page-level horizontal scroll
- [ ] table-level horizontal scroll ทำงาน
- [ ] ไม่มี overlay บังปุ่ม
- [ ] navigation 4 ปุ่มอยู่ครบ

## Existing features

- [ ] Watchlist ทำงาน
- [ ] Saved Screeners ทำงาน
- [ ] Scan filters ทำงาน
- [ ] Scan Now ทำงาน
- [ ] Technical tab ทำงาน
- [ ] Fundamental tab ทำงาน
- [ ] Sort ทำงาน
- [ ] Detail Panel ทำงาน
- [ ] Today ทำงาน
- [ ] Memo ทำงาน
- [ ] Market Pulse ทำงาน
- [ ] Notification error ไม่ทำให้ Scanner พัง

## Structure safety

- [ ] ไม่มี duplicate IDs
- [ ] ไม่มี DOM clone
- [ ] ไม่มี DOM relocation
- [ ] ไม่มี hidden legacy UI
- [ ] ไม่มี runtime มากกว่า 1 ตัวควบคุม navigation
- [ ] ไม่มี CSS patch หลายรุ่นใน artifact
- [ ] ไม่มี data schema breaking change
- [ ] feature flags ปิดได้
- [ ] rollback ได้

## Visual tests

Screenshots:

- 1440×900 Scanner
- 1920×1080 Scanner
- 1366×768 Scanner
- 1024×768 Tablet
- 390×844 Mobile

Compare:

- side blank area
- clipped columns
- panel height
- active navigation
- selected row
- focus tags
- detail chart
