# ⚠️ Gemini Free Tier Limits

**หมายเหตุสำหรับคอสและโค้ดดี้** — นิกใช้ Gemini AI Studio key ฟรี ห้ามเกิน rate limit

## Default Model: `gemini-3.1-flash-lite`

นิกตั้งเป็น default สำหรับทุก project ที่ใช้ Gemini ฟรี (2026-05-17)
ห้ามแนะนำ 2.5 หรือต่ำกว่านี้เป็น default

| Metric | Free Limit |
|---|---|
| Requests per minute (RPM) | **15** |
| Tokens per minute (TPM) | **250,000** |
| Requests per day (RPD) | **500** |

## ✅ ก่อน session ใหม่ที่ใช้ Gemini หนัก — ถามนิกก่อน

1. "นี่จะ call Gemini กี่ครั้ง?"
2. "ใช้ free key หรือ paid key?"
3. ถ้า free + จะเกิน → ต้อง throttle หรือ split + แจ้งนิก

## ❌ อย่า fix ว่า "ห้ามใช้ paid"

- Default ใน code = `gemini-3.1-flash-lite` (free-friendly)
- Settings/config ต้องให้นิกเลือก pro / paid model ได้เสมอ
- บางโปรเจคต้องใช้ pro (เช่น batch ใหญ่ของ HAPPY) — อย่า hard-code free

## 🔗 อ้างอิง

- AI Studio key: https://aistudio.google.com/apikey
- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits

---

**บันทึก:** 2026-05-17 โดยนิก ผ่านโค้ดดี้ — เผื่อคอสมาทำ HAPPY ต่อ
