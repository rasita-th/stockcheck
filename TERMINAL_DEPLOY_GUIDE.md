# Deploy Stock Timing Radar ผ่าน Terminal

## ภาพรวม

ชุดนี้ใช้สำหรับ deploy อย่างปลอดภัยผ่าน Terminal โดยเน้น:

- ตรวจ source ก่อน deploy
- ตรวจ syntax JavaScript
- ตรวจ JSON
- เตรียม clean Pages artifact
- preview ในเครื่อง
- push ไป `main`
- trigger GitHub Actions
- ตรวจ workflow
- rollback เมื่อ production พัง

---

## 1. Requirements

ติดตั้งเครื่องมือ:

```bash
git --version
python3 --version
node --version
gh --version
```

เวอร์ชันแนะนำ:

```text
Git 2.40+
Python 3.11+
Node.js 20+
GitHub CLI 2.40+
```

ติดตั้ง GitHub CLI บน macOS:

```bash
brew install gh
```

Login:

```bash
gh auth login
```

เลือก:

```text
GitHub.com
HTTPS
Login with a web browser
```

ตรวจสิทธิ์:

```bash
gh auth status
```

---

## 2. Clone Repository

```bash
git clone https://github.com/rasita2644-star/stockcheck.git
cd stockcheck
```

ตรวจ branch และ commit:

```bash
git status
git branch --show-current
git log -1 --oneline
```

ควรอยู่บน:

```text
main
```

---

## 3. สร้าง Branch สำหรับ Deploy

ห้ามแก้บน `main` โดยตรง:

```bash
git switch main
git pull --ff-only origin main
git switch -c release/desktop-stability
```

---

## 4. Preflight Check

รัน script:

```bash
bash scripts/preflight.sh
```

สิ่งที่ script ตรวจ:

- ไฟล์หลักมีอยู่
- JavaScript syntax
- Python syntax
- JSON parse
- technical rows ไม่เป็นศูนย์
- duplicate DOM IDs ใน HTML
- legacy runtime references
- navigation labels
- Market Pulse links
- required workflow files

ถ้า preflight ไม่ผ่าน ห้าม deploy

---

## 5. เตรียม Pages Artifact

ถ้า repository มี script เตรียม artifact:

```bash
python3 scripts/prepare_stable_site_v9_4_1.py
```

จากนั้นตรวจ:

```bash
python3 scripts/preflight_check.py --site site
```

ควรเห็น:

```text
PASS
```

---

## 6. Preview ในเครื่อง

### วิธี Python

```bash
cd site
python3 -m http.server 8787
```

เปิด:

```text
http://localhost:8787
```

### วิธี Node

```bash
npx serve site -l 8787
```

ทดสอบ Desktop:

- Chrome 1440px
- Chrome 1920px
- Safari
- Private Window

ทดสอบ Mobile ผ่าน DevTools:

- iPhone 14 Pro
- Pixel 7
- viewport 390x844

Checklist:

```text
[ ] Scanner เปิด
[ ] Today เปิด
[ ] Memo เปิด
[ ] Market Pulse เปิด
[ ] Technical rows โหลด
[ ] Fundamental tab เปิด
[ ] Filters ทำงาน
[ ] Sort ทำงาน
[ ] Detail เปิด
[ ] ไม่มี Console error
[ ] ไม่มี 404
[ ] ไม่มีปุ่มซ้อน
[ ] ไม่มี overlay บังปุ่ม
```

---

## 7. Commit และ Push

```bash
git status
git diff --stat
git diff
```

Commit:

```bash
git add .
git commit -m "Release desktop stability deployment"
git push -u origin release/desktop-stability
```

สร้าง PR:

```bash
gh pr create \
  --base main \
  --head release/desktop-stability \
  --title "Release: desktop stability" \
  --body-file DEPLOY_CHECKLIST.md
```

---

## 8. ตรวจ PR Checks

```bash
gh pr checks --watch
```

หากผ่านทั้งหมด:

```bash
gh pr merge --merge --delete-branch
```

หรือ merge ผ่าน GitHub UI

---

## 9. Trigger GitHub Pages Deploy

หลัง merge:

```bash
git switch main
git pull --ff-only origin main
```

ดู workflow:

```bash
gh workflow list
```

รัน workflow:

```bash
gh workflow run "Deploy GitHub Pages" --ref main
```

ดูสถานะ:

```bash
gh run list --workflow "Deploy GitHub Pages" --limit 5
```

ดู run ล่าสุดแบบ realtime:

```bash
RUN_ID=$(gh run list \
  --workflow "Deploy GitHub Pages" \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')

gh run watch "$RUN_ID"
```

ดู log:

```bash
gh run view "$RUN_ID" --log
```

---

## 10. Post-deploy Verification

หลัง workflow เป็นสีเขียว รอ GitHub Pages ประมาณ 1–3 นาที

รัน:

```bash
bash scripts/post_deploy_check.sh \
  https://rasita2644-star.github.io/stockcheck/
```

ตรวจด้วยตนเอง:

```bash
curl -I https://rasita2644-star.github.io/stockcheck/
curl -I https://rasita2644-star.github.io/stockcheck/app.js
curl -I https://rasita2644-star.github.io/stockcheck/data/technical.json
```

ตรวจ content:

```bash
curl -fsSL https://rasita2644-star.github.io/stockcheck/ \
  | grep -E "Scanner|Today|Memo|Market Pulse"
```

ตรวจจำนวน rows:

```bash
curl -fsSL \
  https://rasita2644-star.github.io/stockcheck/data/technical.json \
  | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["rows"]))'
```

---

## 11. Browser Cache Reset

Chrome Desktop:

```text
DevTools
→ Network
→ Disable cache
→ Reload
```

หรือ:

```text
Command + Shift + R
```

ล้าง service worker:

```text
DevTools
→ Application
→ Service Workers
→ Unregister
```

ล้าง site data:

```text
DevTools
→ Application
→ Storage
→ Clear site data
```

---

## 12. Rollback

### หา commit ที่ดีล่าสุด

```bash
git log --oneline --decorate -20
```

สร้าง rollback branch:

```bash
git switch main
git pull --ff-only origin main
git switch -c rollback/production
```

Revert merge commit ที่พัง:

```bash
git revert -m 1 <BAD_MERGE_COMMIT_SHA>
```

Push:

```bash
git push -u origin rollback/production
```

สร้าง PR:

```bash
gh pr create \
  --base main \
  --head rollback/production \
  --title "Rollback production" \
  --body "Revert broken deployment and restore last known good release."
```

Merge:

```bash
gh pr merge --merge --delete-branch
```

Deploy:

```bash
gh workflow run "Deploy GitHub Pages" --ref main
```

### Emergency direct revert

ใช้เฉพาะเหตุฉุกเฉิน:

```bash
git switch main
git pull --ff-only origin main
git revert -m 1 <BAD_MERGE_COMMIT_SHA>
git push origin main
```

---

## 13. วิธีป้องกันไม่ให้พังอีก

### Single Deploy Authority

มี workflow เดียวที่ deploy Pages:

```text
Deploy GitHub Pages
```

Workflow ข้อมูลห้าม upload Pages เอง

### Immutable Artifact

Artifact ต้องระบุ:

```text
commit_sha
build_id
app_version
data_release_id
built_at
```

### Required Checks

ก่อน merge ต้องผ่าน:

- JavaScript syntax
- JSON validation
- UI smoke test
- Desktop E2E
- Mobile E2E
- no legacy runtime
- no duplicate IDs
- technical rows > 0

### Automatic Post-deploy Check

ถ้า production ไม่ผ่าน:

- navigation ไม่ครบ
- technical JSON 404
- rows = 0
- script 404
- page title ผิด

ให้ rollback อัตโนมัติ

---

## 14. Recommended Terminal Flow

```bash
git switch main
git pull --ff-only origin main
git switch -c release/desktop-stability

bash scripts/preflight.sh
python3 scripts/prepare_stable_site_v9_4_1.py
python3 scripts/preflight_check.py --site site

cd site
python3 -m http.server 8787
```

หลังทดสอบ:

```bash
git add .
git commit -m "Release desktop stability"
git push -u origin release/desktop-stability

gh pr create --base main --fill
gh pr checks --watch
gh pr merge --merge --delete-branch

gh workflow run "Deploy GitHub Pages" --ref main
gh run list --workflow "Deploy GitHub Pages" --limit 1
```

หลัง deploy:

```bash
bash scripts/post_deploy_check.sh \
  https://rasita2644-star.github.io/stockcheck/
```
