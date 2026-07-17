# วิเคราะห์สาเหตุ Desktop โหลดหน้าเว็บไม่ได้

## Executive Summary

ปัญหา Desktop ของ Stock Timing Radar มีแนวโน้มไม่ได้เกิดจากข้อมูลหุ้นหาย แต่เกิดจาก **Frontend runtime หลายชุด, deployment artifact ไม่ตรงกับ source, cache ของ asset เก่า และ workflow หลายตัวที่สามารถ deploy GitHub Pages ทับกันได้**

อาการที่พบร่วมกัน:

- Today หาย
- Market Pulse หาย
- การ์ดไม่ render
- ปุ่มคลิกไม่ได้
- Mobile บางครั้งทำงาน แต่ Desktop พัง
- หน้า live ไม่ตรงกับ commit ล่าสุดใน `main`

## Root Causes ที่เป็นไปได้มากที่สุด

### 1. มี JavaScript หลายชุดควบคุม Navigation และ DOM เดียวกัน

เมื่อหน้าเว็บโหลดไฟล์หลายรุ่น เช่น navigation patch, shared shell, runtime guard และ layout patch พร้อมกัน จะเกิด race condition:

```text
script A สร้าง navigation
script B ลบ navigation
script C สร้าง navigation ใหม่
script D click ปุ่มเดิมที่ถูกลบแล้ว
```

เครื่อง Desktop อาจโหลดไฟล์เร็วกว่า Mobile หรือใช้ cache คนละชุด ทำให้อาการต่างกันตาม browser และเครื่อง

### 2. Desktop CSS override เปลี่ยน layout เกินขอบเขต

CSS ที่ใช้ selector กว้าง เช่น:

```css
header.topbar
.workspace
.content-area
.scanner-panel
```

สามารถทำให้:

- panel ซ้อนกัน
- element ถูกบีบจนกว้างเป็นศูนย์
- overlay บังปุ่ม
- `pointer-events` ถูกปิด
- grid item ล้นออกนอก viewport
- header ทับ content

Mobile อาจไม่โดนเพราะ selector อยู่ใน media query สำหรับ desktop

### 3. Deployment Artifact ไม่ตรงกับ Source

GitHub Pages อาจ deploy จาก artifact ที่ถูกสร้างก่อนหน้า แม้ source ใน `main` จะแก้แล้วก็ตาม

ต้องแยก 3 สิ่ง:

```text
Repository source
Build artifact
Live GitHub Pages
```

ทั้งสามอาจเป็นคนละเวอร์ชันได้

### 4. มี Workflow หลายตัว Deploy Pages

หากทั้ง workflow UI และ workflow อัปเดตข้อมูลมีสิทธิ์ deploy Pages:

```text
Deploy workflow A → เว็บไซต์ใหม่
Data workflow B → deploy site เก่าทับ
```

ทำให้เว็บกลับไปพังภายหลังโดยไม่มีการแก้โค้ด UI ใหม่

### 5. Browser/CDN Cache

การใช้ชื่อไฟล์เดิม เช่น:

```text
app.js
styles.css
```

แม้มี query version แต่ถ้า HTML live ยังเก่า browser จะยังโหลด asset รุ่นเก่าได้

ควรตรวจ:

- HTML version
- JS version
- CSS version
- build SHA
- data release ID

### 6. JavaScript Error ก่อน `renderAll()`

หาก script error ตั้งแต่ bootstrap:

- cards ไม่ render
- navigation handler ไม่ bind
- scanner table ว่าง
- Memo/Today ไม่ทำงาน

ต้องตรวจด้วย Browser DevTools:

```text
Console
Network
Application → Cache Storage
```

### 7. UI ไม่มี Error Boundary

ถ้า component หนึ่ง throw error แล้วไม่มี boundary ระบบอาจหยุด render ทั้งหน้า

ควรแยก error boundary ต่อ view:

- Scanner
- Today
- Memo
- Market Pulse

## วิธีพิสูจน์ต้นเหตุแบบเป็นขั้นตอน

### Step 1 — ตรวจหน้า live ใช้ build ไหน

เปิด DevTools Console:

```js
document.querySelector('script[src*="app.js"]')?.src
document.querySelector('link[href*="styles.css"]')?.href
location.href
```

จากนั้นตรวจ Network ว่าโหลด:

- `app.js` รุ่นใด
- shell รุ่นใด
- technical JSON สำเร็จหรือไม่
- มี 404 หรือไม่

### Step 2 — ตรวจ Runtime Error

ใน Console:

```js
window.onerror = (...args) => console.log("GLOBAL ERROR", args)
window.onunhandledrejection = e => console.log("PROMISE ERROR", e.reason)
```

Reload แล้วดู error แรกสุด เพราะ error แรกมักเป็น root cause

### Step 3 — ตรวจ DOM

```js
document.querySelectorAll('.app-mode-nav').length
document.querySelectorAll('#technicalTableBody').length
document.querySelectorAll('#alertCenter').length
document.querySelectorAll('#detailPanel').length
```

ค่าที่ควรได้คือ `1` สำหรับ element หลัก หากมากกว่า 1 แสดงว่ามี duplicate UI

### Step 4 — ตรวจ Overlay

```js
document.elementsFromPoint(window.innerWidth / 2, 80)
```

ดูว่ามี element ใดบัง navigation หรือไม่

### Step 5 — ตรวจ Data

```js
fetch('data/technical.json', {cache:'no-store'})
  .then(r => r.json())
  .then(d => console.log(d.rows?.length, d))
```

ถ้ามี rows แต่ UI ว่าง แสดงว่าเป็น render/runtime problem ไม่ใช่ data problem

## แนวทางแก้ระยะยาว

1. ใช้ Navigation owner เพียงหนึ่งชุด
2. ใช้ App Shell เพียงหนึ่งชุด
3. ห้ามย้าย DOM หลัง load
4. ห้ามใช้ hidden-button click proxy
5. มี workflow deploy production เพียงตัวเดียว
6. Data workflow อัปเดตข้อมูลอย่างเดียว
7. ทุก build มี commit SHA
8. เพิ่ม E2E test Desktop และ Mobile
9. เพิ่ม post-deploy smoke test
10. เก็บ last-known-good artifact สำหรับ rollback
