# Screenshot Analysis — เหตุผลที่ Desktop มีพื้นที่ดำว่าง

## สิ่งที่เห็นจากภาพ

ภาพแสดงโครงสร้างประมาณ 3 คอลัมน์:

```text
[ Scan Filters ] [ Scanner Results ] [ Chart / Detail ]
```

แต่เนื้อหาจริงกินพื้นที่เพียงบางส่วนของ viewport ขณะที่พื้นที่ซ้ายและขวานอกคอลัมน์หลักเป็นพื้นดำขนาดใหญ่

อาการเด่น:

1. คอลัมน์ซ้ายมีความกว้างค่อนข้างคงที่
2. คอลัมน์กลางมีความกว้างจำกัดและตารางถูกตัดด้านขวา
3. คอลัมน์ขวามีกราฟเพียงส่วนบน แต่พื้นที่ด้านล่างว่างมาก
4. Container หลักมีแนวโน้มใช้ `max-width` หรือ fixed columns
5. Scanner table ไม่สามารถใช้พื้นที่ viewport ที่เหลือได้
6. Feature panels กระจายพื้นที่ไม่สมดุล

## Root cause เชิง layout ที่เป็นไปได้

### 1. Container มี `max-width`

ตัวอย่างรูปแบบที่ทำให้เกิดอาการ:

```css
.app-shell {
  max-width: 1440px;
  margin: 0 auto;
}
```

บนจอใหญ่กว่า 1440px จะเกิดพื้นที่ดำซ้าย–ขวา

### 2. Grid columns ถูกกำหนดตายตัว

```css
.workspace {
  grid-template-columns: 360px 760px 520px;
}
```

เมื่อ viewport กว้างขึ้น คอลัมน์ไม่ขยายตาม

### 3. Scanner Results ไม่ได้ใช้ `minmax(0, 1fr)`

ถ้า grid item ไม่มี `min-width: 0` ตารางอาจ overflow หรือตัดแทนที่จะยืด/หดอย่างถูกต้อง

### 4. Detail panel สูงไม่สัมพันธ์กับ Scanner

กราฟอยู่ด้านบน แต่พื้นที่ล่างไม่ถูกใช้สำหรับ:

- setup score
- focus reasons
- fundamental summary
- playbook
- memo context
- alert context

### 5. Layout ผูกกับตำแหน่งมากกว่าหน้าที่

หาก panel ถูกย้ายด้วย JavaScript หรือมี CSS patch หลายรุ่น จะเกิด:

- ช่องว่าง
- duplicated grid area
- orphaned container
- panel ถูกซ่อนโดยไม่ตั้งใจ

## หลักการแก้

เปลี่ยนจาก:

```text
fixed-width centered dashboard
```

เป็น:

```text
full-viewport responsive workspace
```

โดย **ไม่เปลี่ยน DOM tree**

```text
Existing App Shell
├── Existing Header
├── Existing Controls / Filters
├── Existing Scanner Results
└── Existing Detail / Analysis
```

แก้เฉพาะการจัดวางด้วย CSS Grid และ responsive breakpoints
