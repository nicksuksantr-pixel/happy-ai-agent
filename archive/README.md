# 📚 HAPPY Archive — เอกสารย้อนหลัง

ไฟล์เก่าจาก Project HAPPY ช่วงเริ่มต้น (พ.ค. 2026 ก่อน Phase A) — เก็บไว้สำหรับ historical reference

ย้ายมาจาก `Downloads\HAPPY_archive\` วันที่ 2026-05-16 (Coddy #4 Day 2)

## ไฟล์ในนี้

| ไฟล์ | คืออะไร | ใช้อ้างอิงตอนไหน |
|---|---|---|
| `HAPPY_AI_AGENT_HANDOFF.md` | Handoff ดั้งเดิมจาก Coddy รุ่นแรก (Claude in app) ก่อน Cowork session | ดู context เริ่มต้นโปรเจกต์ |
| `cloudshell_cheatsheet.html` | Cheatsheet สำหรับ Google Cloud Shell (Vertex AI era) | **DEPRECATED** — เราใช้ AI Studio API key แล้ว |
| `cloudshell_cheatsheet.md` | เหมือนข้างบนแต่ markdown | **DEPRECATED** |
| `implementation_guide.md` | คู่มือ implementation รุ่นแรก | reference โครงสร้างเก่า |
| `index.html` | HTML doc รุ่นแรก | reference |
| `nick-ai-agent-2026-eaa7e01224fb.json` | ⚠️ **Service Account JSON** ของ GCP (โปรเจกต์ที่นิกปิดแล้ว 2026-05-14) | DEAD credentials — แต่ **อย่า share** ไฟล์นี้ |
| `nik-brain.zip` | ZIP เล็กๆ ที่ไม่แน่ใจว่าคืออะไร | unknown — เปิดดูเองได้ |

## ⚠️ Sensitive files

- `nick-ai-agent-*.json` = Service Account credentials
  - GCP project ปิดแล้ว → credentials ใช้ไม่ได้
  - **แต่ก็ยัง sensitive** — `*.json` อยู่ใน `.gitignore` แล้ว = ไม่ commit ขึ้น git
  - ถ้าอยากให้สบายใจสุด → ลบทิ้ง (เพราะใช้ไม่ได้แล้ว)

## รูปแบบโปรเจกต์ปัจจุบัน (อ้างอิงเทียบ)

- API: AI Studio Gemini API key (`~/.happy/auth.json`) — ไม่ใช่ Vertex AI / Service Account แล้ว
- HANDOFF ปัจจุบัน: `../HANDOFF.md` (อันใหม่)
- Releases: `../releases/` (installer + release notes)
