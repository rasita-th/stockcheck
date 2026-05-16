# Stock Timing Radar v7.4 — Memo Status Cockpit

This release updates the Stock Memo card/table UI to use bilingual memo status labels.

## Added

- Memo Status dropdown in Add/Edit Memo form
- Thai + English primary status on memo cards
- Compact desktop memo table status column
- Auto/suggested tags from latest scanner data when available
- Alert Ladder display on memo cards and memo table
- Current / Note / Target compact KPI block

## Memo statuses

- เริ่มฟื้นตัว · Early Uptrend
- ขาขึ้นยืนยันแล้ว · Uptrend Confirmed
- ย่อสุขภาพดี · Healthy Pullback
- น่าลงมือ · Actionable
- ร้อนแรง / รอย่อ · HOT / Wait Pullback
- บีบตัวรอเบรก · Squeeze Setup
- เงินเริ่มหมุนเข้า · Rotation Watch
- เสี่ยงถูกขายออก · Distribution Risk
- ขายมากเกิน / รอฟื้น · Oversold Watch
- ขาลง · Downtrend
- แผนเสียแล้ว · Invalidated
- ปิดงานแล้ว · Done
- พักไว้ก่อน · Ignored

## Notes

On GitHub Pages static deploy, the status is primarily user-selected. The app can show suggested tags from the latest `technical.json`, but it does not run a full backend alert engine.
