# Stockcheck Terminal Deployment Kit

ไฟล์ในชุดนี้:

```text
DESKTOP_FAILURE_ANALYSIS.md
TERMINAL_DEPLOY_GUIDE.md
DEPLOY_CHECKLIST.md
scripts/
  preflight.sh
  preflight_check.py
  post_deploy_check.sh
```

## เริ่มใช้งาน

แตก ZIP แล้ว copy ไฟล์ทั้งหมดไปไว้ที่ root ของ repository `stockcheck`

```bash
unzip stockcheck_terminal_deploy_kit.zip
cp -R stockcheck_terminal_deploy_kit/* /path/to/stockcheck/
cd /path/to/stockcheck
chmod +x scripts/*.sh
bash scripts/preflight.sh
```

อ่านรายละเอียดใน:

```text
TERMINAL_DEPLOY_GUIDE.md
```
