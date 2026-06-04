# Log — v2.8.1 (Tester audit)

**วันที่:** 2026-06-04 · **โดย:** Coddy (Claude Code) · **PR:** [#1](https://github.com/nicksuksantr-pixel/happy-ai-agent/pull/1)

## Nick สั่งอะไร
1. Onboard ตาม MASTER Section 5 (อ่าน MASTER / SHARED / command_pattern / Note Master → เขียน MEMORY)
2. "เทสการทำงานเอไอ" — เทส multi-agent pipeline
3. **เปิดใช้งาน Tester** + "ไล่อ่านโค้ดทุกตัว อัปเดตให้ล่าสุด อย่าเชื่อ docs เก่าในโฟลเดอร์"
4. สร้าง PR

## ทำอะไรไป
- **Onboard:** อ่าน 4 ไฟล์กลางครบ · เขียน `memory/MEMORY.md` (A–G) · แก้ MASTER §1 descriptor (Streamlit→CustomTkinter)
- **เครื่องมือเทส:** สร้าง `tools/test_ai_pipeline.py` (headless: connectivity / --quick / --thorough) · connectivity ผ่าน (54 models, generate OK)
- **Tester audit:** spawn 3 agents ขนาน (Functional / Correctness / Holistic) → รวม findings → **verify กับ code จริงทุกข้อ**
- **แก้ 7 bugs** (ดู `bug/bug_v2.8.1.md`) — เด่นสุด P0 `ui/pages/running.py` crash ทุกครั้งที่เปิดหน้า Running (5-field NamedTuple unpack เป็น 4) + drain-ticker ตายถาวร
- **+4 regression tests** · pytest **133 passed** (เดิม 129)
- **docs/org:** archive 8 docs เก่ายุค Streamlit → `_trash/` · reconcile `.gitignore` · prune orphan worktree · refresh `CLAUDE.md`/`README.md`/`GEMINI_LIMITS.md` · +`V-Log.md`/`bug/`/`user/`
- bump VERSION 2.8.0 → **2.8.1**

## ผลการเทส (verify จริง ไม่เดา)
| เทส | ผล |
|-----|-----|
| pytest (unit/integration) | ✅ 133 passed |
| P0 Running page (live CTk render) | ✅ ไม่ crash — refresh() + _pulse_running_dot() ผ่าน |
| **Quick pipeline จริง (HTML stopwatch)** | ✅ 12/12 เฟส · 0 error · Judge **PASS 100/100** · 7 ไฟล์ (index.html/style.css/game.js/...) · 25 calls · 407k/65k tokens · 4.4 นาที |
| Build .exe (PyInstaller) | ✅ HappyAIAgent.exe 17.3 MB + _internal (118 items) · "Build complete" exit 0 |

## หมายเหตุ / สิ่งที่เหลือ
- false positive 1 ข้อ (pipeline.py:1142 pass-2 numbering) — verify แล้วถูกต้อง ไม่แก้
- low-pri ที่ไม่แก้: TPM under-sleep (self-correcting via retry), CODE_BLOCK_RE nested fence, builder progress_cb None-guard
- โจทย์เทส html ได้ main.py ติดมาด้วย (minor — extractor เก็บทุก code block) ไม่กระทบ gate (Judge 100)

## 🚀 Release publish (2026-06-04, follow-up — Nick เห็น GitHub ยัง 2.8.0)
- **อาการ:** main = 2.8.1 แล้ว (PR #1 merge) แต่ไม่มี **tag/Release** v2.8.1 → GitHub Releases + `updater.py` ยังเห็น 2.8.0 → ผู้ใช้แอป **ค้างที่ 2.8.0** (P0 fix ไปไม่ถึงผู้ใช้)
- **แก้:** build installer ใหม่ (`dist/HappyAIAgent-Setup.zip` 121 MB, VERSION 2.8.1) → ปัก tag `v2.8.1` ที่ main `45132b8` → `gh release create` + แนบ asset → **Latest = v2.8.1** ([release](https://github.com/nicksuksantr-pixel/happy-ai-agent/releases/tag/v2.8.1))
- **บทเรียน:** merge เข้า main ≠ ปล่อยอัปเดต — `updater.py` ดึงจาก **GitHub Releases** ไม่ใช่ branch → ทุกครั้งที่ bump version ต้องตามด้วย **cut tag + Release + แนบ `HappyAIAgent-Setup.zip`** เสมอ · (`gh release create --target` ต้องใช้ชื่อ branch หรือ full SHA — short SHA = HTTP 422)
