# HAPPY — Handoff Report (Lean v2)

> **For**: Workie (next agent in Cowork)
> **From**: Coddy #5 (Claude)
> **Date**: 2026-05-16
> **User**: นิก (NickSuksanTr) — เพิ่งเรียน Python, ไม่ถนัด command line, ชอบ visual + emoji + ตาราง, ภาษาไทย
>
> **📁 Full history** (Phase A v2, Coddy #1–#4 session logs): `HANDOFF_ARCHIVE_coddy1to4.md`

---

## 1. ภาพรวมโปรเจกต์

**HAPPY / AI Agent** — แอป Streamlit orchestrate AI หลายตัว (Gemini) ให้ "ประชุมกัน" แล้วเขียนโค้ดให้ user ตามโจทย์

- **เป้าหมาย**: end-user paste โจทย์ → ได้ Python project พร้อม .exe build แล้ว ในคลิกเดียว
- **โหมดทำงาน**:
  - **Quick** = 11 phases (PM → Architect → Coder → Frontend → Debugger → Judge loop → Tester → DevOps → Summarizer → PM Final) ~10 นาที
  - **Thorough** = 18 phases (+ 7 Kickoff phases: Doc Analyst → Requirements → Arch Consult → UX → Data → Security → Brief Synthesizer)

**Tech stack**:
- Python 3.13, Streamlit 1.57
- google-genai SDK (Gemini API via AI Studio key — **ไม่ใช่ Vertex AI**, นิกปิด GCP 2026-05-14)
- pywebview 6.2 + PyInstaller 6.x (desktop .exe wrapper)
- Pygments (syntax highlighting), Inno Setup (installer)

---

## 2. สถานะปัจจุบัน (2026-05-16)

### ✅ Verified & Shipped
- Quick + Thorough mode ทำงานครบ (Judge 100/100 session ตัวอย่างมีใน `sessions/`)
- Gemini AI Studio key auth → save `~/.happy/auth.json` → auto-load
- Retry 3 รอบ (5/15/30s backoff) สำหรับ 429, 503, timeout
- Build .exe ในแอป (builder.py + `_find_python_executable()` สำหรับ frozen mode)
- HAPPY.exe desktop wrapper (pywebview + Streamlit embedded, 22MB exe)
- Download bridge: patch `HTMLAnchorElement.prototype.click` + `Content-Disposition` parse (Bug A fix)
- Pygments code colors (class-based CSS, `nowrap=True`, `<div>` wrap)
- **Phase B Installer**: `releases/v1.032/HAPPY-Setup-1.032.exe` (101MB compressed, Thai/EN, Start Menu/Desktop shortcut, uninstaller)
- Sessions dir → `~/.happy/sessions/` (Bug 22 — ไม่ต้อง admin เพื่อเขียน)

### ⚠️ รอ Retest (commit `c03dabd` — fixes belts Bugs 17-21, ยังไม่ได้รัน manual ยืนยัน)
- Bug 17: Coder truncation (no-preamble/no-postamble prompt fix — อาจไม่พอถ้า model hard-cap)
- Bug 18: Judge fluff false PASS (MANDATORY VERIFICATION + NO PADDING prompt)
- Bug 19: Extractor multi-language confusion (detect_project_type ดู char size)
- Bug 21: Capacity 503 retry (MAX_RETRIES 5, CAPACITY_DELAYS [30,120,300,300,300])

---

## 3. โครงสร้างไฟล์สำคัญ

```
C:\Users\NickSuksanTr\Documents\Projects\HAPPY\
├── app.py                  ◀ Main Streamlit — Settings, Home, Running, Done pages
├── agents.py               ◀ Prompts ของ AI agents 17 ตัว + Judge template + COMMON_RULES
├── auth.py                 ◀ API key auth (save/load ~/.happy/auth.json, test, list models)
├── pipeline.py             ◀ PipelineRunner — orchestrator + retry + judge loop
├── builder.py              ◀ Build .exe จาก session (PyInstaller subprocess)
├── extractor.py            ◀ ดึง code blocks จาก markdown → dict {filename: code}
├── file_loader.py          ◀ Multimodal attachments (image/pdf/docx/xlsx → Gemini parts)
├── happy_desktop.py        ◀ pywebview launcher + JS download bridge
├── HAPPY.spec              ◀ PyInstaller spec (collect_all google.genai/streamlit/starlette/…)
├── requirements.txt
├── .streamlit/config.toml  ◀ Theme + headless=true + toolbarMode=viewer
├── .gitignore
├── assets/
│   ├── happy_logo.png
│   └── happy_logo.ico
├── sessions/               ◀ User data (gitignored) — 1 ตัวอย่าง Password Generator
├── releases/v1.032/        ◀ Inno Setup installer output
├── dist/HAPPY/             ◀ PyInstaller output (gitignored)
├── HANDOFF.md              ◀ ← ไฟล์นี้ (lean)
└── HANDOFF_ARCHIVE_coddy1to4.md  ◀ Full history Phase A v2 + Coddy #1-#4 logs
```

### Logic สำคัญ
- **Pipeline orchestration**: `pipeline.py` → `PipelineRunner.run()` → branch quick/thorough
- **Judge feedback loop**: `_run_judge_loop()` — สูงสุด 5 รอบ, threshold default 100/100
- **Coder → Debugger → Judge revision**: ใน `_run_judge_loop` lines 720-766

### Bug fix sites (อย่าลบ comments)
- `happy_desktop.py` — `_global_development_mode` override (static 404 ใน frozen mode)
- `happy_desktop.py` — `bootstrap._set_up_signal_handler` patch (signal only works in main thread)
- `pipeline.py` — `MAX_RETRIES = 3, RETRY_DELAYS` (transient API errors)
- `pipeline.py` — `CAPACITY_DELAYS` (503 overload, commit `c03dabd`)
- `app.py` — `for _k in ("_pipeline_queue", "_pipeline_thread")` (กัน thread เก่าค้าง)

### Config ที่ต้องระวัง
- `.streamlit/config.toml` — **ห้าม** `[global] developmentMode = true` (static routes ไม่ register)
- `HAPPY.spec` — `collect_all` ต้องมี `starlette, uvicorn, anyio, sniffio, h11, websockets`
- `~/.happy/auth.json` — API key (ไม่ commit, ไม่ bundle)

---

## 4. วิธีรัน / ทดสอบ

### Install
```powershell
cd C:\Users\NickSuksanTr\Documents\Projects\HAPPY
python -m pip install -r requirements.txt
# สำหรับ build .exe เพิ่ม:
python -m pip install pywebview Pillow pyinstaller
```

### รัน Web mode (dev)
```powershell
python -m streamlit run app.py --server.port=8501 --server.headless=true
# เปิด http://localhost:8501
```

### รัน Desktop mode (dev)
```powershell
python happy_desktop.py
```

### Build HAPPY.exe
```powershell
pyinstaller HAPPY.spec --noconfirm
# Output: dist/HAPPY/HAPPY.exe (~22 MB) + dist/HAPPY/_internal/ (~320 MB)
```

### Smoke test
```powershell
python -c "import auth, pipeline, agents, builder, extractor, file_loader; print('OK')"
```

### ไม่มี test suite — ทดสอบ manual + ดู `sessions/*/...md` output

---

## 5. Context ที่ไม่อยู่ในโค้ด

### การตัดสินใจสำคัญ
1. **เลิก Vertex AI → Gemini AI Studio** (2026-05-14) — ฟรี tier, paste key ตัวเดียว. **ห้ามแนะนำ Vertex AI กับนิก**
2. **Pygments + custom CSS** แทน Streamlit's react-syntax-highlighter — class-based CSS คุมได้เต็มที่. ต้อง `HtmlFormatter(nowrap=True)` + `<div class="happy-code">` (ไม่ใช่ `<pre>`)
3. **Single-click delete history** (ไม่ต้อง 2-step confirm) — นิกยอมรับ trade-off
4. **Default `judge_threshold = 100`** — นิกอยากได้ output คุณภาพสูง
5. **Default `delay = 60`s** — free tier Gemini Pro = 5 RPM

### Convention
- ภาษาไทยใน UI labels, error messages, log prints
- Emoji ใน UI: 🤖🎯✅❌⏳⚠️ — print() ใน frozen mode ใช้ ascii-safe
- นิกชอบ tables ใน chat — ไม่ใช่ bullet list ยาวๆ
- Backup ก่อนแก้ไฟล์สำคัญ (.bak)
- Commit เล็กๆ ทีละนิด

### สิ่งที่ลองแล้วไม่เวิร์ค
- `streamlit.web.bootstrap.run()` ใน background thread → ต้อง patch `_set_up_signal_handler`
- PyInstaller `--collect-all streamlit` อย่างเดียว → ต้องเพิ่ม starlette/uvicorn/anyio/sniffio/h11/websockets
- `subprocess python -m streamlit` ใน frozen .exe → `sys.executable = HAPPY.exe` ไม่ใช่ python.exe
- `headless=true` ใน config.toml อย่างเดียว → ต้อง `st_config.set_option(...)` + patch `cli_util.open_browser`

---

## 6. Git

**Repository**: `C:\Users\NickSuksanTr\Documents\Projects\HAPPY\`
**Latest commit**: `3020fbc` — "builder: auto-open python.org when Python missing"

### Recent commit history (สำคัญ)
| Commit | Message |
|--------|---------|
| `3020fbc` | builder: auto-open python.org when Python missing |
| `c03dabd` | Bugs 17-21 fixes (Coder preamble / Judge false PASS / extractor / capacity retry) |
| `4e0c9d6` | Download bridge fix + builder frozen mode (_find_python_executable) |
| `da7fdff` | Phase A v2 baseline — 13 bugs fixed, pipeline refactored |

### ไม่ควร commit
- `*.json` ยกเว้น `.streamlit/*.json`, `sessions/`, `*.log`, `dist/`, `build/`, `__pycache__/`

---

## 7. Pending / Action Items

> Active items เท่านั้น (✅ completed ถูก archive ไปแล้ว)

### 🟠 P1 — Verify First (ก่อน Phase B)

| # | งาน | เหตุผล |
|---|---|---|
| P1.1 ⚠️ | **Real-world verify Phase A v2** — รัน Quick mode 1-2 sessions ดู token_stats + output quality. `c03dabd` fix Bugs 17-21 **ยังไม่ได้ retest** → ต้องยืนยัน Path A (verify fix ok) vs Path B (fallback Anthropic) | fix committed แต่ไม่มี user-side validation |

### 🟡 P2 — Improvements (หลัง P1 pass)

| # | งาน | เหตุผล |
|---|---|---|
| P2.1 | **Pattern audit retroactive** — grep `on_phase_start` vs `on_phase_complete` count ทั่ว codebase | หา asymmetric callback/resource acquisition bugs (Bug 14 pattern) |
| P2.2 | **TPM throttle UI indicator** ใน page_running | User เห็น hang ไม่รู้เหตุ |
| P2.3 | **Fluff self-score loop** — Judge/Tester รอบสุดท้ายขอ rate "filler ratio 0-10" | ตรวจ output retry padding |
| P2.4 | **Antivirus quarantine handling** — Defender ลบ .exe ทันที | proper fix (README.txt เฉยๆ ไม่พอ) |
| P2.5 | **Cold start indicator** ใน HAPPY.exe — splash screen during 15s boot | UX risk: user kill process → loop |
| P2.6 | **Version stamp** ใน app footer (commit hash + build date) | bug tracking ยาก ถ้าไม่รู้ build version |
| P2.7 ✅ | **Debugger error pill ค้าง** ใน `_run_judge_loop` — except ส่ง `on_phase_error("coder")` แม้ debugger throw | Fixed by Coddy #5 |
| P2.8 ✅ | **Coder prompt — no debug `print()` for GUI/.exe** | Fixed by Coddy #5 |
| P2.9 ✅ | **errors.log file handle leak** — `.open("a").write(...)` ไม่มี `with` block | Fixed by Coddy #5 |
| P2.10 ⚠️ | **Bug 17 — Coder truncation** (Flash Lite ~4K token hard-cap) | `c03dabd` fix อาจไม่พอ — retest; fallback = multi-pass/Anthropic |
| P2.11 ⚠️ | **Bug 18 — Judge fluff false PASS** | `c03dabd` fix ยังต้อง retest |
| P2.12 ⚠️ | **Bug 19 — Extractor multi-language confusion** | `c03dabd` fix ยังต้อง retest |
| P2.13 ⚠️ | **Bug 21 — Capacity 503 retry** (MAX_RETRIES 5, new CAPACITY_DELAYS) | `c03dabd` fix ยังต้อง retest |
| P2.14 | **Multi-provider fallback (Anthropic)** — Sonnet 4.5 output cap ~64K → solves Bug 17 hard cap | Nick willing to pay-per-use if needed |

### 🟢 P3 — Future / Optional

| # | งาน | เหตุผล |
|---|---|---|
| P3.2 ✅ | **Archive HANDOFF.md** | Done by Coddy #5 — `HANDOFF_ARCHIVE_coddy1to4.md` |
| P3.3 | **Task-type detection → dynamic CONTEXT_MAP** | Static CONTEXT_MAP ตอนนี้ — premature abstraction ถ้าทำตอนนี้ |
| P3.4 | **Coder pass-1 file ZIP duplicate** (`04a_coder_pass1.md` vs `04_coder.md`) | รอ feedback จากนิกก่อน |
| P3.5 | **Codebase complexity refactor** — pipeline.py 870+ lines | ไม่ใช่ปัญหาตอนนี้ (Nick ≠ maintainer) |

---

## 8. Key Insights (สำหรับ session ต่อไป)

1. **Multi-Coddy pattern works** — Coddy #2 catch 5 blind spots ของ Coddy #1 — เก็บ pattern นี้ไว้
2. **Honest pushback is valued** — Coddy #1 push back 3 ครั้ง, Nick respond ดีมาก. Future agents ควร counter-propose ได้
3. **Insider vs Outsider perspectives ทั้งคู่จำเป็น**
4. **HANDOFF.md threshold = 700 บรรทัด** → archive เมื่อถึง
