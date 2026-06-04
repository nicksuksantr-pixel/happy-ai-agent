# Bug Log — v2.8.2 (Tester audit + cleanup)

**วันที่:** 2026-06-04 · audit โดย 3 agents ขนาน (Functional / Correctness / Holistic) · **verify กับ code จริงทุกข้อก่อนแก้**

> baseline v2.8.1 = known-good (pytest 133 passed) → audit รอบนี้ codebase สุขภาพดีมาก (core/ui แยกสะอาด · atomic write ทั่ว · subprocess ปลอดภัย) — findings ส่วนใหญ่เป็น polish + 1 security hardening

## ✅ แก้แล้ว

| # | Sev | ไฟล์ | Bug | Fix |
|---|-----|------|-----|-----|
| 1 | **P1** | updater.py · ui/app.py | auto-updater ดาวน์โหลด + **รัน installer โดยไม่ verify integrity** (เช็คแค่ ZIP ไม่พัง) → ถ้า asset ถูกแก้ (account/PAT รั่ว, MITM ที่ S3 redirect) แอป auto-run โค้ดผู้โจมตี | เพิ่ม SHA-256 gate: `parse_expected_sha256` ดึง hash จาก release body → `verify_sha256` หลังโหลด ก่อน launch · mismatch = wipe+retry · **backward-compat**: ไม่มี hash = ข้าม (พฤติกรรมเดิม) |
| 2 | P2 | builder.py:843 `_build_web_exe` | bundle web asset ด้วย `--add-data "{src};."` → **flatten ทุกไฟล์ไป root** → `css/style.css` ที่ index.html อ้างถึง landed ที่ root → **404 ใน .exe** | preserve subfolder: dest = `str(Path(asset).parent)` |
| 3 | P2 | ui/pages/home.py `_pick_files` | attach ไฟล์รอบ 2 = **overwrite** ของเดิม → แนบ mockup.png แล้วเปิด picker เพิ่ม spec.pdf → mockup.png หายเงียบ | เปลี่ยนเป็น **append + de-dupe by name** |
| 4 | P3 | pipeline.py `create_session` | meta เขียน `started_at` แต่ไม่เขียน `created_at` ทั้งที่ 5 จุด UI (home/runs/stats) อ่าน `created_at` ก่อน (fallback `started_at` เลย work) = phantom key เสี่ยง refactor พังเงียบ | เขียน `created_at` จริง (= `started_at`) |
| 5 | P3 | updater.py `_parse_version`/`is_newer` | pre-release tag (`2.8.1-beta`) เทียบเท่า final `2.8.1` → user บน -beta ไม่เคยได้ตัว final · (latent — โปรเจคใช้ tag เลขล้วน) | แยก numeric กับ pre-release flag: pre-release < final |
| 6 | P3 | agents.py:2 · README · CLAUDE.md | doc drift จำนวน agent: docstring "10" · README/CLAUDE "17" · จริง = **11 impl + 7 kickoff = 18 roles** | sync เลขให้ตรง code ทั้ง 3 ไฟล์ |

## 🧪 Tests เพิ่ม (audit H-A3#7 — 2 module fragile ที่ไม่เคยมี unit test)
- `tests/test_updater.py` — `is_newer` (numeric / ต่าง length / 10>9 / pre-release) · `parse_expected_sha256` · `verify_sha256` (match/mismatch/empty/missing) · `_validate_partial_for_url` (sidecar match/mismatch/missing — Range-resume guard)
- `tests/test_file_loader.py` — `get_file_type`/`get_mime_type` mapping · `load_file_for_gemini` dispatch + **PDF 20 MB threshold** (inline vs text) · `build_gemini_parts`

**pytest:** **188 passed** (เดิม 133 + ใหม่ 55) · ไม่มี regression

## ⏸️ ตรวจแล้ว "ตั้งใจไม่แก้" (verify แล้ว — defer + document)
- **A1#2 Build .exe ไม่อ่าน project_type** (done.py) — build ใช้งานได้อยู่ (html→pywebview wrapper, desktop→PyInstaller) แค่ label/expectation ไม่ตรง · เป็น UX polish เสี่ยงปานกลาง → defer
- **A1#1 multimodal attachment เข้าแค่ doc_analyst** — by design (doc_analyst สรุปให้ทีม)
- **A2#5/A3#6 build_combined_txt โชว์ judge_round/revision เป็น section พิเศษ** — cosmetic · **เก็บไว้ตั้งใจ** (เนื้อหา revision มีประโยชน์ใน full report ไม่ใช่ noise)
- **A2#3 max_output_tokens 65536 > TPM ของ 1.5-pro (32k)** — เฉพาะ model deprecated non-default
- **A2#4 unnamed same-lang block → orphan `block_NN`** — เฉพาะ output ที่ไม่ทำตาม `### File:` convention
- **A3#5 Tester prompt game-centric (PLAYABLE/BROKEN)** — เปลี่ยน = behavior change ของ pipeline ต้องเทส Gemini จริงก่อน → defer (reference-integrity check ครอบอยู่แล้ว gate ไม่เพี้ยน)

## ❌ False positive (ยกมาจาก v2.8.1 — re-verify แล้วยังถูก)
- **pipeline.py:1142** Coder pass-2 ใช้ `phase_index` overwrite slot 04 = **ตั้งใจ** (pass-1 archive แยก) · TPM under-sleep / CODE_BLOCK_RE nested fence / builder progress_cb None-guard = low-pri self-correcting

## 🙋 ต้องให้ Nick ตัดสิน (ไม่แก้เอง — outward/data-loss/UX call)
- **A3#2 PAT ฝังใน .exe** (`.env` ถูก bundle ใน HappyAIAgent.spec → ใครได้ installer แกะ `_internal/.env` อ่าน PAT ได้) — แก้ในโค้ดไม่ได้ (updater ต้องใช้ token เข้า private repo) · ทางแก้ = **scope PAT ให้แคบ (fine-grained, single-repo, Contents:read) + rotate เป็นระยะ** หรือทำ repo เป็น public (releases) จะไม่ต้องฝัง token เลย
- **A3#3 delete session ใช้ 2-step confirm** (runs.py / done.py `askyesno`) — ขัด preference "single-click delete" ใน memory แต่เป็น `rmtree` data-loss → ขอ Nick ยืนยันว่าจะเอา single-click หรือเก็บ confirm ไว้สำหรับ delete ที่ลบข้อมูลถาวร
