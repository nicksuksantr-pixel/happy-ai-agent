# MEMORY.md — HAPPY-Ai-Agent

> **Onboarding snapshot** — อ่านไฟล์นี้ก่อนเริ่มงานทุกครั้ง (แทนการกลับไปอ่าน MASTER + SHARED + command_pattern ซ้ำ)
> สร้างจากขั้นตอน Section 5 ของ MASTER.md
> **อัปเดตล่าสุด:** 2026-06-04 by Coddy (Claude Code)

---

## หมวด A — Path ของระบบหลัก

| ไฟล์ | Path |
|------|------|
| MASTER.md | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\MASTER.md` |
| SHARED.md | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\SHARED.md` |
| command_pattern.md | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\command_pattern.md` |
| Note Master.txt | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\Note Master.txt` |
| **โปรเจคนี้** | `C:\Users\NickSuksanTr\Documents\Projects\HAPPY-Ai-Agent\` |

- **วันที่อ่าน MASTER ครั้งล่าสุด:** 2026-06-04 (context fresh)

---

## หมวด B — Gemini & AI Settings

| Setting | ค่า |
|---------|-----|
| Default model | `gemini-3.1-flash-lite` (❌ ห้าม Vertex AI เด็ดขาด — Nick ปิด GCP เสีย ฿334) |
| API key type | Google AI Studio key เท่านั้น |
| Key location | `~/.happy/auth.json` (ไม่ใช่ .env · ไม่ hardcode ในโค้ด) |
| Rate limit | RPM 15 · TPM 250,000 · RPD 500 — เตือน Nick ก่อน batch ใหญ่ |
| Settings UI | ให้ user เลือก paid model ได้เสมอ (อย่า hard-code free-only) |

---

## หมวด C — Tools & Environment

| Tool | เวอร์ชัน |
|------|---------|
| Python | 3.13.13 (`...\Programs\Python\Python313\python.exe`) |
| pip / uv | 26.0.1 / 0.11.14 |
| google-genai (Gemini SDK) | 1.75.0 |
| CustomTkinter | 5.2.2 |
| PyInstaller | 6.20.0 |
| Git | 2.54.0 |

**โปรเจคนี้ = native CustomTkinter desktop app** (ไม่ใช่ Streamlit แล้ว — ❌ ห้ามนำ Streamlit/HTTP/localhost กลับมา)
- Entry: `happy_native.py` → `ui.app.main()`
- โครงสร้าง: `core/` (config + persistence) · `ui/` (theme + 6 pages) · `pipeline.py` (orchestrator) · `agents.py` (17 agent prompts) · `auth.py` · `builder.py` · `extractor.py` · `file_loader.py` · `updater.py`
- **เวอร์ชันปัจจุบัน: 2.8.0** (ไฟล์ `VERSION` = single source of truth)
- Pipeline: Quick = 11 phases (~15-25 นาที) · Thorough = 18 phases (~30-40 นาที). Quality gates: Tester → Debugger → Judge (0-100, threshold 100) → loop กลับ Coder ถ้าตก

---

## หมวด D — command_pattern 11 ข้อ (Quick Reference)

1. **Project Boundary** — แตะแค่โฟลเดอร์โปรเจคปัจจุบัน · โปรเจคอื่นอ่านได้อย่างเดียว ห้ามแก้
2. **Gemini** — AI Studio key เท่านั้น · default `gemini-3.1-flash-lite` · RPM15/RPD500 เตือนก่อน batch ใหญ่
3. **Branding** — Icon = App Identity (taskbar/installer) · Mascot = Helper (welcome/drop zone) · ❌ ห้ามสลับ
4. **อัปเดต Memory เมื่อพบ bug/error เสี่ยงสูง** — บันทึกลง `MEMORY.md` ทันที (ไฟล์ไหน/function/บรรทัด + วิธีแก้)
5. **Tester** — Nick พิมพ์ "Tester" → spawn 3 agent ขนาน (Functional / Code Correctness / Holistic) → แก้ทันทีไม่รอ approve → test → build → report (ไม่จำกัด token)
6. **จัดไฟล์เป็นระเบียบ** — แยกโฟลเดอร์ตามหมวด (`docs/ assets/ memory/ log/ bug/ _trash/`) · มี `_trash/` เสมอ (ย้าย ไม่ลบ)
7. **Changelog/log/bug** — แยกโฟลเดอร์ · max 20 entries/ไฟล์ · max 10 ไฟล์/ระบบ · เกินโยน `_trash/`
8. **อ่าน memory** (changelog/log/bug ที่หมุนตาม version) สูงสุด 5 ไฟล์ล่าสุด = 100 entries ยกเว้น Nick สั่ง
9. **Log** — บันทึกการคุย+คำสั่งแยกตาม version ใน `log/log_vX.md`
10. **Bug Log** — บันทึก bug+fix แยกตาม version ใน `bug/bug_vX.md`
11. **V-Log** — timeline ทุกเวอร์ชันตั้งแต่ต้นใน `V-Log.md`

> หมายเหตุ: `MEMORY.md` (ข้อ 4) = สแนปช็อตหลักไฟล์เดียว (ที่ Nick สั่ง "อ่านเมมโมรี่") · คนละตัวกับ log/bug ที่หมุนตาม version (ข้อ 7-8)

---

## หมวด E — กฎเสริมจาก Note Master.txt (Nick เขียนเอง)

- บันทึกทุกอย่างในโฟลเดอร์โปรเจคนี้เท่านั้น · ทุกครั้งที่อัปเดต → **รันเทสแล้วบันทึก** ลง memory โปรเจค
- มีโฟลเดอร์ `_trash/` (เก็บไฟล์ไม่ใช้) + โฟลเดอร์ `user/` (ผู้ใช้ — ไฟล์ส่งออกให้ผู้ใช้ที่ไม่เกี่ยวกับแอป เช่น ภาพหน้าตาแอป)
- อย่าวางไฟล์กระจัดกระจาย — จัดให้เป็นระเบียบชัดเจน
- **(มือถือ)** มี emulator ในคอม — ก่อน build aab ขึ้น Play ต้องรันเทสใน emulator ก่อนทุกครั้ง · ตั้งชื่อ apk/aab ชัดเจน + version (v0.0.0 → v0.0.1 ... ขึ้น 0.1.0 เมื่อ update ใหญ่ · มีเกณฑ์อ้างอิงได้ ไม่สุ่ม)
  - *(หมายเหตุ: HAPPY = โปรแกรมคอม ไม่ใช่มือถือ — versioning principle ใช้ได้ แต่ apk/aab/emulator ไม่เกี่ยว)*
- สรุปการทำงาน + อัปเดตให้ Nick รู้ทุกครั้งตอนจบงาน · ไม่จำกัด token/agent — ออกแบบให้ agent ทำงานขนานได้

---

## หมวด F — Team & Don'ts (จาก CLAUDE.md โปรเจค)

| คน | บทบาท |
|----|-------|
| 🧑 Nick | เจ้าของ — เพื่อน ไม่ใช่นาย · ภาษาไทย · ตอบสั้น+ตาราง+emoji |
| 💻 Coddy | Claude Code — coder, แก้ไฟล์/build (ตัวฉันเอง) |
| 🧠 Coss | Cowork strategy — analysis only ห้ามแก้โค้ด |
| 🎛️ เวิร์คกี้ | Orchestrator |

**❌ Don't:** Vertex AI · กลับไป Streamlit/HTTP/localhost · 2-step confirm delete (Nick ขอ single-click) · เปลี่ยน phase delay default โดยไม่ถาม

---

## หมวด G — หมายเหตุ / สิ่งที่ต้องระวัง (อัปเดตเมื่อพบ)

- ✅ **Docs เก่ายุค Streamlit v1.032 ถูก archive แล้ว (v2.8.1):** ย้าย `HANDOFF.md` · `HAPPY_AI_AGENT_HANDOFF.md` · `HANDOFF_ARCHIVE_coddy1to4.md` · `ONBOARD_NEW_CODDY.md` · `ONBOARD_NEW_COSS.md` · `WORKIE_NOTES.md` · `WEB_TEST_RESULTS.md` · `installer-mockup.html` → `_trash/` (git-ignored) → **ยึด `CLAUDE.md` + code จริงเป็นหลัก**
- ✅ แก้ MASTER Section 1: descriptor HAPPY จาก "Streamlit + Gemini" → "CustomTkinter native + Gemini" (2026-06-04) ให้ตรงกับ rewrite เป็น native CTk
- ✅ SHARED.md ตรวจแล้ว — ข้อมูลถูกต้อง ไม่ต้องแก้
- ✅ **v2.8.1 Tester audit (2026-06-04):** 3-agent audit → แก้ 7 bugs (P0 Running-page crash ทุกครั้งที่รัน + drain-ticker, extractor round-order, auth-gate refresh, attachments-in-Quick, Settings-reset desync) · +4 regression tests (pytest 133 passed) · [PR #1](https://github.com/nicksuksantr-pixel/happy-ai-agent/pull/1) · รายละเอียด: `bug/bug_v2.8.1.md` + `log/log_v2.8.1.md`
