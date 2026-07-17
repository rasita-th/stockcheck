# Production Deploy Checklist

## Source

- [ ] Deploy branch มาจาก `main` ล่าสุด
- [ ] ไม่มี uncommitted files ที่ไม่เกี่ยวข้อง
- [ ] ไม่มี legacy UI runtime ถูกโหลดพร้อมกัน
- [ ] Navigation มี owner เดียว

## Validation

- [ ] `bash scripts/preflight.sh` ผ่าน
- [ ] JavaScript syntax ผ่าน
- [ ] JSON validation ผ่าน
- [ ] Technical rows มากกว่า 0
- [ ] ไม่มี duplicate IDs
- [ ] ไม่มี Console error

## Desktop

- [ ] Chrome 1440px
- [ ] Chrome 1920px
- [ ] Safari
- [ ] Navigation 4 ปุ่มครบ
- [ ] ปุ่มไม่ถูก overlay บัง
- [ ] Scanner table โหลด
- [ ] Today โหลด
- [ ] Memo โหลด
- [ ] Market Pulse โหลด
- [ ] Detail Panel เปิด

## Mobile

- [ ] 390px
- [ ] 430px
- [ ] Navigation 4 ปุ่มไม่ซ้อน
- [ ] Filters sheet เปิด
- [ ] Alerts sheet เปิด
- [ ] Detail modal เปิด

## Deployment

- [ ] PR checks ผ่าน
- [ ] GitHub Pages workflow ผ่าน
- [ ] Post-deploy check ผ่าน
- [ ] Live HTML ใช้ asset version ล่าสุด
- [ ] Rollback commit ถูกระบุไว้
