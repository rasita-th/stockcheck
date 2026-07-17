# Stock Radar Full-Width UI Plan

แพ็กเกจนี้เป็น **แผนออกแบบและแนวทาง implementation แบบปลอดภัย** สำหรับแก้ปัญหาพื้นที่ดำว่างซ้าย–ขวาบน Desktop โดยยึดโครงสร้างเดิมของ Stock Timing Radar

## จุดยืนของแพ็กเกจ

- ไม่สร้าง UI ชุดใหม่มาทับ UI เดิม
- ไม่ซ่อน UI เดิมด้วย `display:none`
- ไม่ clone หรือย้าย DOM หลังหน้าโหลด
- ไม่เพิ่ม JavaScript สำหรับจัด layout
- ไม่เปลี่ยน data schema
- ไม่ผูก Scanner เข้ากับ Notification แบบที่ทำให้ Scanner พังตาม
- ใช้ CSS Grid/Flex ปรับ **layout ของ element เดิม**
- แยก PR ด้าน UI ออกจาก PR ด้าน data structure

## ไฟล์สำคัญ

```text
docs/
  SCREENSHOT_ANALYSIS.md
  FULL_WIDTH_UI_ARCHITECTURE.md
  SAFE_IMPLEMENTATION_PLAN.md
  FOCUS_HIGHLIGHT_INTEGRATION.md
  REGRESSION_AND_ACCEPTANCE.md
reference/
  full-width-layout-reference.css
terminal/
  PULL_REQUEST_DEPLOY_GUIDE.md
  PR_BODY.md
```

ไฟล์ CSS ใน `reference/` เป็น reference เท่านั้น ห้ามนำไปโหลด production โดยตรงก่อน map selector ให้ตรงกับ DOM จริงและผ่าน regression tests
