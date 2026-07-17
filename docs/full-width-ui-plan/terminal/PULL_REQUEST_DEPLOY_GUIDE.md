# Terminal Pull Request and Merge Guide

## 1. แตก ZIP

จาก Downloads:

```bash
cd ~/Downloads
unzip stock_radar_full_width_ui_plan.zip
```

## 2. เข้า repository

```bash
cd /path/to/stockcheck
git switch main
git pull --ff-only origin main
```

แทน `/path/to/stockcheck` ด้วย path จริง เช่น:

```bash
cd ~/stockcheck-clean
```

## 3. สร้าง branch

```bash
git switch -c docs/full-width-ui-plan
```

## 4. Copy package เข้า repository

```bash
mkdir -p docs/full-width-ui-plan
cp -R ~/Downloads/stock_radar_full_width_ui_plan/*   docs/full-width-ui-plan/
```

ตรวจ:

```bash
git status
git diff --stat
```

## 5. Commit

```bash
git add docs/full-width-ui-plan
git commit -m "Add safe full-width UI architecture plan"
git push -u origin docs/full-width-ui-plan
```

## 6. สร้าง Pull Request

```bash
gh pr create   --base main   --head docs/full-width-ui-plan   --title "Add safe full-width desktop UI architecture plan"   --body-file docs/full-width-ui-plan/terminal/PR_BODY.md
```

เปิดดู PR:

```bash
gh pr view --web
```

## 7. ตรวจ checks

```bash
gh pr checks --watch
```

## 8. Merge

```bash
gh pr merge --merge --delete-branch
```

## 9. ดึง main ล่าสุด

```bash
git switch main
git pull --ff-only origin main
```

## ข้อสำคัญ

PR นี้เป็น documentation/reference plan จึงไม่เปลี่ยน production UI โดยตรง

ตอน implementation จริงให้ทำตาม 3 PR:

```text
PR 1: layout + tests
PR 2: focus adapter
PR 3: focus presentation
```

ห้ามรวม data schema migration กับ layout PR
