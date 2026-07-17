## Summary

เพิ่มแผน architecture สำหรับปรับ Desktop UI ให้ใช้พื้นที่เต็มหน้าจออย่างปลอดภัย โดยอ้างอิงจาก screenshot ปัจจุบันและ Focus Highlight specification

## Key constraints

- ไม่สร้าง UI ใหม่มาซ่อน UI เดิม
- ไม่ clone หรือย้าย DOM
- ไม่ใช้ JavaScript จัด layout
- ไม่เปลี่ยน data schema
- ไม่รวม layout, data และ notification changes ใน PR เดียว
- ใช้ CSS Grid กับ DOM เดิม
- มี feature flag และ rollback path

## Documents

- Screenshot analysis
- Full-width architecture
- Safe implementation sequence
- Focus Highlight integration
- Regression and acceptance criteria
- Terminal PR/merge instructions
- Reference-only CSS layout contract

## Production impact

ไม่มีการเปลี่ยน production code ใน PR นี้
