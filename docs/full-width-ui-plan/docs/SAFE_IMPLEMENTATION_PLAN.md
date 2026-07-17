# Safe Implementation Plan

## หลักการ

การปรับ UI นี้ต้องเป็น **layout refactor** ไม่ใช่ UI replacement

## สิ่งที่อนุญาต

- เปลี่ยน `max-width`
- เปลี่ยน CSS Grid columns
- เพิ่ม `min-width: 0`
- เพิ่ม responsive breakpoints
- ปรับ gap/padding
- ทำ panel ให้ stretch
- ทำ table container ให้ scroll ภายใน
- เพิ่ม Focus column แบบ additive
- เพิ่ม Focus summary ใน Detail โดยใช้ container เดิม

## สิ่งที่ห้าม

- `display:none` กับ panel เดิมเพื่อสร้าง panel ใหม่
- clone DOM
- append/move panel ด้วย JavaScript
- synthetic click ไปยัง hidden control
- MutationObserver เพื่อคอยย้าย layout
- duplicate IDs
- fixed overlay ที่บัง navigation
- เปลี่ยน data schema ใน PR เดียวกัน
- โหลด CSS patch หลายเวอร์ชันพร้อมกัน

## แผนแบ่ง Pull Request

### PR 1 — Layout contract + tests

เปลี่ยนเฉพาะ:

- layout CSS
- viewport tests
- screenshot tests
- overflow tests

ไม่เพิ่ม Focus Tag และไม่เปลี่ยน data

### PR 2 — Focus adapter

เปลี่ยนเฉพาะ:

- pure adapter
- schema validation
- unit tests
- feature flag ปิดโดย default

ไม่เปลี่ยน layout

### PR 3 — Focus presentation

เปลี่ยนเฉพาะ:

- Focus column
- mobile focus band
- Today Focus section
- Detail reason banner

เปิดด้วย feature flag หลัง layout ผ่าน production

## Feature flag

ตัวอย่าง:

```json
{
  "features": {
    "fullWidthDesktopLayout": false,
    "focusHighlights": false
  }
}
```

ลำดับ:

```text
Deploy code
→ test production with flag off
→ enable fullWidthDesktopLayout
→ observe
→ enable focusHighlights
```

## Layout implementation sequence

1. ตรวจ DOM จริงและระบุ owner ของแต่ละ panel
2. ทำ inventory selector
3. ลบเฉพาะ CSS rule ที่ขัดกันใน source stylesheet
4. กำหนด workspace grid ที่ stylesheet หลัก
5. เพิ่ม `min-width:0` ให้ทุก grid child
6. เพิ่ม table overflow container
7. เพิ่ม right rail stacking
8. ตรวจ desktop 1440/1920
9. ตรวจ tablet/mobile
10. เปิด feature flag

## Data safety

ยึดหลัก:

- additive fields only
- schema version
- adapter คั่นกลาง
- optional/default values
- runtime validation
- last-known-good fallback
- UI PR แยกจาก data PR
