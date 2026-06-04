# Bug Log — v2.8.1 (Tester audit)

**วันที่:** 2026-06-04 · audit โดย 3 agents ขนาน (Functional / Correctness / Holistic) · **verify กับ code จริงทุกข้อก่อนแก้**

| # | Sev | ไฟล์ | Bug | Fix |
|---|-----|------|-----|-----|
| 1 | **P0** | ui/pages/running.py:274,423 | `AgentRowWidgets` เป็น NamedTuple 5 field แต่ loop unpack เป็น 4 → `ValueError: too many values to unpack` ทุกครั้งที่เปิดหน้า Running → **แอปรัน pipeline ไม่ได้เลย** (regression v2.8.0 B-12) | เปลี่ยนเป็น attribute access (`w.dot`/`w.name_btn`/...) เหมือน done.py |
| 2 | **P0** | ui/app.py:_drain_pipeline_queue | exception จาก `refresh()` หลุดออกก่อนบรรทัด reschedule ticker → queue-drain ตายถาวร → UI ไม่อัปเดตอีกเลย | wrap `_handle_pipeline_msg` ใน try/except — reschedule ticker เสมอ |
| 3 | P1 | extractor.py:224 | เลือก debugger revision ด้วย **string sort** → `revision_10` แพ้ `revision_9` → Build .exe / Download ได้ code รอบเก่า (เมื่อ judge loop ครบ 10 รอบ) | sort ด้วยเลขรอบ (int) |
| 4 | P1 | ui/app.py:_on_auth_verified | key เสีย (format ผ่านแต่ API ปฏิเสธ) ที่ตรวจเจอตอน background ไม่ refresh ปุ่ม Run บนหน้า Home → กด Run ได้ทั้งที่ key ใช้ไม่ได้ | refresh Home gate ถ้ากำลังอยู่หน้า home |
| 5 | P2 | ui/app.py:start_pipeline | Quick mode ไม่มี doc_analyst (multimodal) แต่ยัง save attachments + flag `has_attachments=true` → ผู้ใช้เข้าใจผิดว่าไฟล์ถูกใช้ | save attachments เฉพาะ mode=thorough |
| 6 | P2 | ui/pages/home.py:on_show | Settings "Reset" เปลี่ยน project_type/mode ใน app_state แต่ปุ่ม segmented บน Home ยังโชว์ค่าเก่า → รันได้ผลคนละอย่างกับที่เห็นเลือก | re-sync segmented buttons จาก app_state ทุกครั้งที่ on_show |
| 7 | P2 | ui/pages/settings.py:_reset_settings | reset ตั้ง `model_var` แต่ไม่ `configure(values=...)` → dropdown โชว์ค่าที่ไม่อยู่ในลิสต์ตัวเอง | reconfigure `model_menu` values |
| 8 | P3 | running.py:22, done.py:58 | unused `section_card` import | ลบทิ้ง |

## ❌ False positive (verify แล้วไม่ใช่ bug)
- **pipeline.py:1142** — Agent flag ว่า Coder pass-2 ใช้ `phase_index` (ไม่ใช่ +1). Trace แล้ว: **ตั้งใจ** ให้ overwrite slot `04_coder.md` ของ pass-1 (pass-1 archive แยกที่ `04a_coder_pass1.md`). ถ้าใส่ +1 จะชนกับ slot ของ Frontend และทิ้ง pass-1 ที่ยังไม่ปรับปรุงไว้เป็น canonical → **ไม่แก้** ใส่ comment อธิบายไว้แทน

## ⏸️ ตรวจแล้วไม่แก้ (low severity / self-correcting)
- `_TPMTracker.wait_if_needed` อาจ under-sleep → 429 ครั้งคราว แต่ `_call_with_retry` จัดเป็น transient + backoff เอง
- `CODE_BLOCK_RE` จับ nested triple-backtick fence ผิด — แต่ convention `### File:` ของ Coder/Frontend กันไว้แล้ว
- `builder` internal `progress_cb` ไม่มี None-guard — แต่ไม่มี call path ที่ส่ง None จริง

## ✅ Regression tests เพิ่ม
- `tests/test_running_page_regression.py` — กัน 4-tuple unpack กลับมา + ยืนยัน 5 field ของ NamedTuple
- `tests/test_extractor_revision_order.py` — round 10 > round 9

**pytest:** 133 passed (เดิม 129 + ใหม่ 4) · ไม่มี regression
