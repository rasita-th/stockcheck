# Terminal Deployment Guide

## เหตุผลที่ preflight เดิมล้มเหลว

`site/index.html` ใน source ยังอาจมี legacy references ที่ถูกลบโดย `scripts/prepare_stable_site_v9_4_1.py` ระหว่าง build ดังนั้นการตรวจ raw source โดยตรงอาจให้ false failure แม้ Pages artifact สุดท้ายสะอาด

preflight ที่ถูกต้องจึงทำงานแบบนี้:

```text
Repository source
→ copy ไป temporary directory
→ run artifact preparation
→ validate prepared site
→ ลบ temporary directory
```

Source ใน working tree จะไม่ถูกแก้โดย preflight

## ใช้งานบน macOS

จาก root ของ repository:

```bash
chmod +x scripts/preflight.sh scripts/post_deploy_check.sh
bash scripts/preflight.sh
```

เมื่อผ่านแล้ว preview ในเครื่อง:

```bash
cd site
python3 -m http.server 8787
```

เปิด `http://localhost:8787`

## สร้าง Pull Request

```bash
git switch main
git pull --ff-only origin main
git switch -c release/desktop-stability

bash scripts/preflight.sh

git add scripts docs
git commit -m "Add terminal deployment guardrails"
git push -u origin release/desktop-stability

gh pr create --base main --fill
gh pr checks --watch
```

## Merge และ Deploy

```bash
gh pr merge --merge --delete-branch

gh workflow run "Deploy GitHub Pages" --ref main
```

ติดตาม workflow:

```bash
RUN_ID=$(gh run list \
  --workflow "Deploy GitHub Pages" \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')

gh run watch "$RUN_ID"
```

ดู log เมื่อมีปัญหา:

```bash
gh run view "$RUN_ID" --log
```

## ตรวจ Production

```bash
bash scripts/post_deploy_check.sh \
  https://rasita2644-star.github.io/stockcheck/
```

Script จะตรวจ:

- หน้า production ตอบกลับ
- Navigation มี Scanner, Today, Memo, Market Pulse
- `technical.json` โหลดได้และมี rows
- `app.js`, `market.html`, `market.js` เข้าถึงได้

## Desktop Checklist

- Navigation 4 ปุ่มแสดงครบ
- ไม่มี overlay บังปุ่ม
- Scanner table มีข้อมูล
- Today เปิดได้
- Memo เปิดได้
- Market Pulse เปิดได้
- Technical/Fundamental tabs ทำงาน
- Console ไม่มี uncaught error
- Network ไม่มี 404 ของ JS, CSS หรือ JSON

## Rollback

หา merge commit ที่พัง:

```bash
git log --oneline --merges -20
```

สร้าง rollback PR:

```bash
git switch main
git pull --ff-only origin main
git switch -c rollback/production
git revert -m 1 <BAD_MERGE_SHA>
git push -u origin rollback/production
gh pr create --base main --fill
gh pr merge --merge --delete-branch
gh workflow run "Deploy GitHub Pages" --ref main
```

## กฎสำคัญ

1. ห้าม deploy จาก branch เก่าโดยตรง
2. ห้ามตรวจเฉพาะ raw `site/index.html`; ต้องตรวจ prepared artifact
3. Workflow เดียวควรเป็นผู้ deploy production
4. หลัง deploy ต้องรัน post-deploy check
5. อย่า merge เมื่อ preflight หรือ PR checks ไม่ผ่าน
