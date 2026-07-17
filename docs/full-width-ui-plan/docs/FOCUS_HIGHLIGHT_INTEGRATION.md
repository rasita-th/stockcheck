# Focus Highlight Integration

Focus Highlight ใช้ Notification data เดิมเป็น projection ไม่สร้าง pipeline ใหม่

## จุดแสดงผล

### Scanner

เพิ่มคอลัมน์ `Focus` ก่อน Ticker:

- Desktop: สูงสุด 2 tags
- Tablet: icon + count
- Mobile: แถบด้านบน card สูงสุด 1 tag

### Today

เพิ่ม `Focus Today` สูงสุด 5 รายการ เฉพาะ Critical/High

### Detail Panel

เพิ่ม banner:

```text
ทำไมต้องดูตัวนี้วันนี้
```

วางเหนือ tabs เดิม ไม่เพิ่ม tab ใหม่

## Fail-safe behavior

```text
Notification ready   → render focus tags
Notification partial → render tags เฉพาะ ticker ที่ valid
Notification stale   → render พร้อม stale badge
Notification error   → render dash; Scanner ทำงานต่อ
```

## Adapter contract

- pure function
- no network call
- no mutation
- invalid notification ถูกข้าม
- คืน `[]` เมื่อ input ไม่พร้อม
- reason มาจาก notification เดิม
- sort priority แล้วตามเวลา
- จำกัดจำนวนใน presentation layer

## Layout relationship

Focus column ต้องไม่ทำให้ตารางแคบลงจนเกิดพื้นที่ดำ

แนวทาง:

- Center workspace ขยายก่อนเพิ่ม column
- Focus column ใช้ `clamp(112px, 10vw, 160px)`
- Ticker sticky ถัดจาก Focus
- ตาราง scroll ภายในเมื่อ viewport ไม่พอ
- ห้ามลดความกว้าง center เพื่อรักษา right rail แบบ fixed
