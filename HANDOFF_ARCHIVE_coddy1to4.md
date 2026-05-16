# HAPPY — Handoff Report

> **For**: Workie (next agent picking this up in Cowork)
> **From**: โค้ดดี้ (Claude)
> **Date**: 2026-05-14
> **User**: นิก (NickSuksanTr) — เพิ่งเริ่มเรียน Python, ไม่ถนัด command line, ชอบ visual + emoji + ตาราง, ภาษาไทย

---

## 1. ภาพรวมโปรเจกต์

**HAPPY / AI Agent** — แอป Streamlit ที่ orchestrate AI หลายตัว (Gemini) ให้ "ประชุมกัน" แล้วเขียนโค้ดให้ user ตามโจทย์ที่ป้อน

- **เป้าหมาย**: end-user paste โจทย์ → ได้ Python project พร้อม .exe ที่ build แล้ว ในคลิกเดียว
- **ผู้ใช้**: นิกใช้คนเดียวตอนนี้ (อาจขยายเป็น web public ในอนาคต)
- **โหมดทำงาน**:
  - Quick = 11 phases (PM Kickoff → Architect → Coder → Frontend → Debugger → Judge loop → Tester → DevOps → Summarizer → PM Final) ~10 นาที
  - Thorough = 18 phases (+ Kickoff meeting 7 phases: Document Analyst → Requirements → Architect Consult → UX → Data → Security → Brief Synthesizer)

**Tech stack หลัก**:
- Python 3.13
- Streamlit 1.57 (UI)
- google-genai SDK (Gemini API via AI Studio key — ไม่ใช่ Vertex AI แล้ว ตั้งแต่ 2026-05-14)
- pywebview 6.2 + PyInstaller 6.x (สำหรับ desktop .exe wrapper)
- Pygments (syntax highlighting ในช่องโค้ด)

---

## 2. สถานะปัจจุบัน

### ✅ ทำเสร็จแล้ว (verified)
- **Quick + Thorough mode** ทำงานครบ — รัน 11/18 phases ได้จริง (มี session ตัวอย่างใน `sessions/2026-05-14_08-02-09` ที่ผ่าน Judge 100/100)
- **Gemini API key auth** ผ่าน AI Studio — paste key 1 ครั้ง → save ที่ `~/.happy/auth.json` → auto-load รอบหน้า
- **Retry mechanism** — 3 รอบ backoff 5/15/30 วินาที สำหรับ transient errors (429, 503, timeout, server disconnected)
- **Build .exe ในแอป** — ปุ่มในหน้า Done → รัน PyInstaller subprocess → ส่ง .exe download ให้ user
- **HAPPY.exe (desktop wrapper)** — pywebview + Streamlit embedded → 22 MB exe + 320 MB bundle (`dist/HAPPY/`)
- **Pygments code colors** — Pygments `nowrap=True` + `<div>` wrap (ไม่ใช่ `<pre>` เพราะ Streamlit markdown escape spans ภายใน pre)
- **HAPPY theme styling** — ส้ม-ชมพู #FB923C/#EC4899, radio buttons custom, secondary button override
- **In-app rate limit table** + ลิงก์ไป AI Studio dashboard
- Single-click delete history (ตามที่นิกขอ — ไม่ต้อง 2-step confirm)
- ปุ่ม "📺 ดูงานที่กำลังทำ" — กลับหน้า running ได้แม้สลับไป Settings
- White overlay fix — CSS override `[data-stale="true"] { opacity: 1 }`
- Status update เป็น `failed` เมื่อ thread crash (กัน UI ค้าง `running` ตลอด)

### 🚧 กำลังทำ / ยังไม่ verified
- **Download bridge ใน HAPPY.exe** (commit ล่าสุดของ happy_desktop.py) — JS intercept blob URLs → ส่ง base64 ผ่าน `pywebview.api.save_download` → Python save ลง `~/Downloads/` + Toast notification
  - **ยังไม่ได้ test ปลายทาง** กับ user — built แล้ว แต่นิกยังไม่ verify ว่า toast ขึ้น + ไฟล์ลงถูกที่
  - ถ้าไม่ทำงาน → check console ใน DevTools ของ pywebview (กด F12) ดู error
- **Web hosting (Streamlit Cloud)** — นิกตัดสินใจไม่ deploy ตอนนี้ — ค่อยทำเมื่อมีคนอื่นอยากใช้

### 🐛 บัคที่รู้แล้ว
- **Download buttons ใน HAPPY.exe** อาจยังไม่ทำงาน ถ้า:
  - Edge WebView2 ไม่ allow `fetch(blob:)` cross-origin (ปกติ work เพราะ same-origin)
  - JS bridge inject ไม่ทันก่อน user click — solved ด้วย `events.loaded` callback แต่ Streamlit rerun อาจไม่ trigger `loaded` ใหม่ทุกครั้ง
  - **Workaround สำหรับ user**: เปิด `http://localhost:8501` ใน Chrome/Edge ปกติแทน .exe → download ทำงานตามมาตรฐาน
- **โปรแกรมหน่วง** — Streamlit `st.rerun()` ทุก 2 วินาที (ใน `page_running`) → ทั้งหน้า re-render → sidebar (history) render ซ้ำ → ช้า
  - ทางแก้: `@st.fragment` (Streamlit 1.32+), `@st.cache_data(ttl=10)` สำหรับ `list_sessions()`, lazy-load 5 อันแรก
- **`Local URL: http://localhost:3000` log** — Streamlit print URL ผิด port (โชว์ 3000 แทน 8501) — cosmetic เฉยๆ ไม่กระทบฟังก์ชัน
- **มี HAPPY.exe ค้างเป็น zombie process** ถ้า user kill window แบบไม่ถูกต้อง — port 8501 อาจค้าง → ครั้งต่อไป launch จะ reuse server เก่า (มี logic check แล้ว)

### 📋 TODO ถัดไป (priority สูง→ต่ำ)
1. **Verify download fix** — ขอให้นิกกดปุ่มดาวน์โหลดใน HAPPY.exe ตัวล่าสุด → ดู toast + ไฟล์ใน `~/Downloads/`
2. **Performance** — แก้ปุ่มหน่วงช้า (ใช้ `@st.fragment`)
3. **GCP project cleanup follow-up** — นิกปิด GCP project แล้ว (2026-05-14) แต่บิลสุดท้าย ~฿334 ยังไม่หัก → ถามนิกในการคุยรอบหน้าว่าตรวจ statement แล้วยัง
4. **Optional**: deploy เป็น Streamlit Cloud ถ้านิกอยากให้คนอื่นเข้าได้ (ต้อง push code ขึ้น GitHub ก่อน — ยังไม่มี git repo)

---

## 3. โครงสร้างไฟล์สำคัญ

```
C:\Users\NickSuksanTr\Desktop\happy-ai-agent\
├── app.py                  ◀ Main Streamlit app — Settings, Home, Running, Done pages (80 KB)
├── agents.py               ◀ Prompts ของ AI agents 17 ตัว (kickoff 7 + impl 10) + Judge template
├── auth.py                 ◀ Gemini API key auth (save/load ~/.happy/auth.json, test connection, list models)
├── pipeline.py             ◀ PipelineRunner — orchestrator + retry mechanism
├── builder.py              ◀ Build .exe จาก session ด้วย PyInstaller subprocess
├── extractor.py            ◀ ดึง code blocks จาก markdown output → dict of {filename: code}
├── file_loader.py          ◀ Multimodal attachments (image/pdf/docx/xlsx → Gemini parts)
├── happy_desktop.py        ◀ pywebview launcher + JS download bridge สำหรับ .exe wrapper
├── HAPPY.spec              ◀ PyInstaller spec (collect_all streamlit/starlette/uvicorn/anyio + assets)
├── requirements.txt        ◀ streamlit, google-genai, pygments — ยังไม่มี pywebview/pyinstaller (dev only)
├── .streamlit/config.toml  ◀ Theme + headless=true + toolbarMode=viewer
├── .gitignore              ◀ ห้าม commit *.json (Service Account), sessions/, *.log
├── assets/
│   ├── happy_logo.png      ◀ Logo full (1500x700) ใช้ใน UI
│   └── happy_logo.ico      ◀ Icon 256x256 cropped — ใช้ใน HAPPY.exe + window
├── sessions/               ◀ User data — ถูก gitignore — 1 session ตัวอย่างของ Password Generator
├── dist/HAPPY/             ◀ Build output — HAPPY.exe + _internal/ (~320 MB, ไม่ commit)
└── HAPPY_AI_AGENT_HANDOFF.md  ◀ Handoff เก่าจากคอส (Claude in app) — เก็บไว้เป็น context
```

### จุดที่ logic สำคัญอยู่

- **Pipeline orchestration**: `pipeline.py` → `PipelineRunner.run()` → branch quick/thorough
- **Judge feedback loop**: `pipeline.py` → `_run_judge_loop()` — สูงสุด 5 รอบ, threshold default 100/100
- **Bug fix sites** (อย่าลบ comments เหล่านี้ — เป็นกัน regression):
  - `happy_desktop.py` `_global_development_mode` override — แก้ static 404 ใน frozen mode
  - `happy_desktop.py` `bootstrap._set_up_signal_handler` patch — แก้ "signal only works in main thread"
  - `pipeline.py` `MAX_RETRIES = 3, RETRY_DELAYS = [5, 15, 30]` — retry สำหรับ transient API errors
  - `app.py` ตรง `for _k in ("_pipeline_queue", "_pipeline_thread")` — กัน thread เก่าค้าง

### ไฟล์ config ที่ต้องระวัง
- `.streamlit/config.toml` — **อย่าตั้ง** `[global] developmentMode = true` (จะทำให้ static routes ไม่ register)
- `HAPPY.spec` — `collect_all` ต้องมี `starlette, uvicorn, anyio, sniffio, h11, websockets` (PyInstaller ไม่ detect เอง)
- `~/.happy/auth.json` — API key ของ user (ไม่ commit, ไม่ bundle เข้า .exe — อยู่ home folder ของแต่ละ user)

---

## 4. วิธีรัน / ทดสอบ

### Dependency install
```powershell
cd $env:USERPROFILE\Desktop\happy-ai-agent
python -m pip install -r requirements.txt
# สำหรับ build .exe เพิ่ม:
python -m pip install pywebview Pillow pyinstaller
```

### รัน Web mode (development)
```powershell
python -m streamlit run app.py --server.port=8501 --server.headless=true
# เปิด http://localhost:8501 ใน browser
```

### รัน Desktop mode (development — Python ตรง)
```powershell
python happy_desktop.py
# เปิด pywebview window อัตโนมัติ — สำหรับ debug ก่อน build
```

### Build HAPPY.exe (production)
```powershell
pyinstaller HAPPY.spec --noconfirm
# Output: dist/HAPPY/HAPPY.exe (~22 MB) + dist/HAPPY/_internal/ (~320 MB)
# Build time: ~3-5 นาที
```

### Env vars (ที่อาจต้องตั้ง — แต่ปกติ happy_desktop.py ตั้งให้แล้ว)
- `STREAMLIT_GLOBAL_DEVELOPMENT_MODE` (ต้อง = `"false"` ใน frozen mode)
- `STREAMLIT_SERVER_HEADLESS`
- `STREAMLIT_BROWSER_GATHER_USAGE_STATS`
- `STREAMLIT_CLIENT_TOOLBAR_MODE`
- `GOOGLE_APPLICATION_CREDENTIALS` — **ไม่ใช้แล้ว** (เคยใช้ตอนยังเป็น Vertex AI mode)

### ไม่มี test suite
- ไม่มี unit tests / integration tests
- ทดสอบด้วย manual + ดู `sessions/*/...md` output
- Smoke test: `python -c "import auth, pipeline, agents, builder, extractor, file_loader; print('OK')"`

---

## 5. Context ที่ไม่ได้อยู่ในโค้ด

### การตัดสินใจสำคัญ + เหตุผล

1. **เลิก Vertex AI → ใช้ Gemini AI Studio API key** (2026-05-14)
   - **ทำไม**: Vertex AI = ต้อง Google Cloud project + billing + service account JSON → ซับซ้อน + ค่าใช้จ่าย ~฿334/เดือนตอนทดสอบ
   - **AI Studio**: ฟรี tier, paste key ตัวเดียวจบ — เหมาะกับ user ทั่วไป
   - **ห้าม** กลับไปแนะนำ Vertex AI กับนิก — เขาเพิ่งปิดโปรเจกต์ Google Cloud

2. **ใช้ Pygments + custom CSS แทน Streamlit's react-syntax-highlighter** (2026-05-13)
   - **ทำไม**: Streamlit ใช้ inline style RGB ที่ใช้ light theme → บน bg dark สีอ่านยาก + เปลี่ยน RGB บ่อย → CSS override match RGB เก่าไม่ทันชาติ
   - **Pygments**: ใช้ class-based (.k, .s, .nf, ...) → CSS ของเราคุมได้เต็มที่
   - **สำคัญ**: ต้อง `HtmlFormatter(nowrap=True)` แล้ว wrap ด้วย `<div class="happy-code">` (ไม่ใช่ `<pre>`) เพราะ Streamlit markdown processor escape HTML ภายใน `<pre>` แม้ `unsafe_allow_html=True`

3. **Single-click delete history (ไม่ต้อง 2-step confirm)**
   - **ทำไม**: นิกบอกว่าโปรแกรมหน่วง — กดยืนยันแล้วลังเลว่าทำงานรึยัง → confused
   - **Trade-off**: เสี่ยงกดผิด แต่นิกยอม

4. **Default `judge_threshold = 100`** (เข้มงวดที่สุด)
   - **ทำไม**: นิกอยากได้ output คุณภาพสูง — ยอมรอ revision หลายรอบ

5. **Default `delay = 60` วินาที ระหว่าง agent**
   - **ทำไม**: free tier ของ Gemini Pro = 5 RPM → ถ้า delay น้อยจะ hit rate limit
   - Flash model มี quota สูงกว่า — อาจลด delay ได้

### Convention / style
- **ภาษาไทย**: UI labels, error messages, log prints — ทั้งหมดภาษาไทย
- **Emoji ใน UI**: 🤖 🎯 ✅ ❌ ⏳ ⚠️ ใช้ได้ปกติ (ระวัง Unicode encoding ใน frozen mode — print() ใช้ ascii-safe characters)
- **Tabular reports**: นิกชอบ tables ใน chat — ไม่ใช่ bullet list ยาวๆ
- **Backup ก่อนแก้ไฟล์**: เคยทำ `.bak` ก่อนแก้ไฟล์สำคัญ (ตอน auth.py rewrite) — แนะนำทำต่อ
- **commit เล็กๆ**: นิกชอบทดสอบทีละนิด — ไม่ rewrite หลายไฟล์พร้อมกัน

### เรื่องที่เคยลองแล้วไม่เวิร์ค
- **`streamlit.web.bootstrap.run()` ใน main thread**: Streamlit ใช้ `signal.signal()` ที่ทำงานเฉพาะ main thread → background thread จะ throw `ValueError: signal only works in main thread` → ต้อง patch `_set_up_signal_handler = lambda: None`
- **PyInstaller `--collect-all streamlit` อย่างเดียว**: ไม่พอ — ต้องเพิ่ม `starlette, uvicorn, anyio, sniffio, h11, websockets` ด้วย (PyInstaller ไม่ trace dependency ของ Streamlit ลึกพอ)
- **Streamlit's `toolbarMode = "viewer"` config**: บังคับซ่อน Deploy button ไม่ได้เสมอ → ต้องใช้ CSS `display: none` บน `[data-testid="stToolbar"]`
- **ใช้ subprocess Python -m streamlit ใน frozen .exe**: ไม่ทำงานเพราะ `sys.executable` = `HAPPY.exe` ไม่ใช่ python.exe → ต้องใช้ `streamlit.web.bootstrap` programmatic
- **เปิด browser อัตโนมัติตอน .exe boot**: Streamlit `headless=true` ใน config.toml ไม่พอ → ต้อง `st_config.set_option("server.headless", True)` ในโค้ด + monkey-patch `cli_util.open_browser = lambda: None`

---

## 6. สถานะ git ปัจจุบัน

⚠️ **ไม่ใช่ git repository** — `.git/` ไม่มี

ถ้า Workie จะ deploy หรือทำ history tracking → ต้อง `git init` ก่อน:

```powershell
cd $env:USERPROFILE\Desktop\happy-ai-agent
git init
git add .
git commit -m "Initial handoff state from โค้ดดี้"
```

### ไฟล์ที่ไม่ควร commit (จาก .gitignore)
- `*.json` ยกเว้น `.streamlit/*.json` — กัน Service Account JSON เก่ารั่ว
- `sessions/` — user data
- `__pycache__/`, `*.pyc`
- `*.log`
- `dist/`, `build/` — PyInstaller output

### ไฟล์ที่ commit ได้ปลอดภัย
- `app.py`, `agents.py`, `auth.py`, `pipeline.py`, `builder.py`, `extractor.py`, `file_loader.py`, `happy_desktop.py`
- `HAPPY.spec`, `requirements.txt`, `.streamlit/config.toml`
- `assets/happy_logo.png`, `assets/happy_logo.ico`
- `README.md`, `HANDOFF.md`, `HAPPY_AI_AGENT_HANDOFF.md`

### Commits ล่าสุด
ไม่มี history — แต่งานหลักที่เพิ่งทำ (สำหรับเขียน commit message ตอน init):
1. Add desktop wrapper (`happy_desktop.py` + `HAPPY.spec` + logo .ico)
2. Fix 6 PyInstaller × Streamlit bugs (signal, static 404, dev_mode, etc.)
3. Switch auth from Vertex AI → Gemini API key
4. Add Build .exe feature ในแอป (`builder.py` + page_done UI)
5. UI polish — radio buttons, secondary buttons, toolbar hide, Pygments code blocks

---

## 7. งานชิ้นถัดไป (ตามลำดับความสำคัญ)

### 🥇 Priority 1 — Verify download bridge ใน HAPPY.exe
- **ไฟล์**: `happy_desktop.py` — `_JSApi.save_download` + `_DOWNLOAD_BRIDGE_JS`
- **วิธี**: ขอนิกกดปุ่ม "📄 ดาวน์โหลด TXT" ใน HAPPY.exe → check:
  - Toast notification ขึ้นมุมขวาล่าง?
  - ไฟล์อยู่ใน `C:\Users\NickSuksanTr\Downloads\`?
- **ถ้าไม่ทำงาน** debug:
  - JS console ใน WebView2 — เปิด `window.evaluate_js("console.log(window.pywebview)")` → check API exposed
  - ตอน Streamlit rerun → `events.loaded` อาจไม่ fire ซ้ำ → ลอง `window.events.shown` หรือ inject ผ่าน MutationObserver

### 🥈 Priority 2 — แก้โปรแกรมหน่วง
- **ไฟล์**: `app.py` ตรง `page_running()` line ~1500
- **วิธี**: เปลี่ยน `time.sleep(2); st.rerun()` → ใช้ `@st.fragment` (Streamlit 1.32+) ที่ rerun เฉพาะส่วน progress
- **ผลคาดหวัง**: หน้าจะ smooth ไม่กระตุก ทุก 2 วินาที, sidebar history ไม่ re-render

### 🥉 Priority 3 — Performance optimizations
- `@st.cache_data(ttl=10)` สำหรับ `list_sessions()` (`pipeline.py` line ~340)
- Lazy-load history ใน sidebar — แสดง 5 อันแรก + ปุ่ม "ดูเพิ่ม"

### 🏅 Priority 4 (optional) — Deploy เป็น Web app
- ต้อง `git init` + push to GitHub
- Deploy ผ่าน https://share.streamlit.io (ฟรี)
- ระวัง: code จะ public — ลบ comments ที่มี info personal ของนิก ก่อน push

### 🎁 Nice-to-have
- Stop button ระหว่าง pipeline (callback `should_stop` มีอยู่ใน `PipelineRunner` แล้ว — แค่ไม่มีปุ่มใน UI)
- Splash screen ตอน HAPPY.exe boot (cold start ใช้ ~10 วินาที)
- Auto-update check (GitHub release)
- Dark mode toggle
- รองรับ Gemini 3.x pro-preview เป็น default (เมื่อ Google ยก preview → GA)

---

## 📞 ติดต่อย้อนกลับโค้ดดี้
ไม่ได้ — เป็น session แยก ทุกครั้งคุยใหม่ = new agent
แต่มี memory ของนิกที่ `C:\Users\NickSuksanTr\.claude\projects\C--Users-NickSuksanTr\memory\` — Workie อ่านได้ถ้าใช้ Claude Code ใน path เดียวกัน

---

## 🆕 Phase A v2 — What's NEW (2026-05-14, after handoff)

### Bugs fixed (13 total)

| # | Bug | Fix location |
|---|---|---|
| 1 | Kickoff agents hidden in Done page dropdown | `app.py page_done()` — use `get_phases_for_mode(mode)` from session meta |
| 2 | Cannot return to running page from elsewhere | `app.py sidebar` — check `_pipeline_thread.is_alive()` instead of stale `running` flag; "✅ ดูผลที่เสร็จแล้ว" button when thread died |
| 3 | Download/Build buttons enabled before pipeline done | `app.py page_done()` — `_is_done = meta.status == "completed"` gate; history click routes by status |
| 4 | Dropdown didn't update output (replaced via UX redesign) | UX rebuild — clickable agent list (`render_agent_button_list`), auto-select latest done, ▶ marker on selected |
| 5 | Sidebar collapse hides toggle (no way to reopen) | `app.py THEME_CSS` — stop hiding `stToolbar` (which contains `stExpandSidebarButton`); make header transparent instead |
| 6 | Frozen .exe pytest crash (stderr=None) | `builder.py` — skip `test_*.py` from main + bundle, switch `--windowed` → `--console` |
| 7 | Code quality issues + output truncation | `pipeline.py _gen_config()` — `max_output_tokens=65536, temperature=0.4`; `agents.py COMMON_RULES` — TOKEN BUDGET section + filename markers required |
| 8 | Silent skip on empty/blocked Gemini response | `pipeline.py _validate_response()` — checks text + finish_reason (SAFETY/RECITATION/etc); retries via `_call_with_retry`; final fail → status="failed" |
| 9 | Output missing `index.html` (JS-only) | `pipeline.py _validate_project_completeness()` after judge loop — soft warning in meta; Coder/Frontend/Debugger prompts require complete project |
| 10 | Judge passes despite score < threshold | `pipeline.py parse_judge()` returns `(score:int, instructions:str)`; `_run_judge_loop` uses `score >= threshold` not `decision == "PASS"` |
| 11 | Delete button on running session = orphan thread | `app.py sidebar` — render 🛑 Stop for running, 🗑️ Delete for others; bulk-delete skips running |
| 12 | Extractor names files `block_NN.ext` | `extractor.py find_filename_in_preceding()` parses `### File: x` heading; `_smart_default_filename()` returns `index.html`/`game.js`/`main.py` based on content |
| 13 | Tester just reads code, doesn't simulate | `agents.py TESTER_INSTRUCTION` rewrite — mental simulation, PLAYABLE/BROKEN decision; `parse_tester_decision()` parser |

### New features

- **Pipeline reorder** — Tester gate before Debugger+Judge (functional check first, quality polish second, score gate third). `IMPL_PHASES` reordered + `_run_tester_loop` mirrors judge loop (max revisions back to Coder if BROKEN).
- **Web .exe build** — `builder.py detect_project_type()` + `_build_web_exe()` wraps HTML/JS with pywebview launcher via PyInstaller.
- **Reset Session buttons** — Settings page "🔄 รีเซ็ตเซสชัน" section: 🧹 Clear Session State (in-memory, keeps auth.json) + 🚪 Logout (deletes auth.json).
- **Model upgrade** — default `gemini-3.1-flash-lite-preview` (was `gemini-2.5-pro`). Verified via `models.get()`: input 1M / output 65K.
- **Token monitoring** — `_extract_usage()` reads `response.usage_metadata` (no extra API call). `PipelineRunner.token_log` + meta.json `token_stats` (total/peak/avg). UI: 4 metrics + per-phase expander in page_done.
- **TPM watcher (adaptive throttling)** — `_TPMTracker` rolling 60s window. Before each call: if projected input would breach 85% of TPM=250K, sleep until oldest event ages out of window. Logs `[TPM throttle] sleep Xs before <agent>`.
- **Cumulative context** — Coder/Frontend/Tester/Debugger now receive task + all prior phase outputs (was: just last 1-2). Peak input ~50-70K (was ~18K).

### Token usage strategy (decided 2026-05-14)

- **Target**: ~50-70K peak input per request (cumulative context for review phases).
- **NOT a hard floor**: real content size for early phases (pm_kickoff, architect) is naturally small. Enforcing 125K via synthetic padding would degrade quality (Gemini sensitivity to repetition).
- **Quality**: Bug 1-13 fixes addressed logic issues (wrong constant, missing validation, broken extraction) — none were caused by small context. More context helps Debugger/Tester (review tasks); doesn't help PM/Architect (creative tasks).
- **Delay default**: 45s (1.33 req/min ≈ 83% TPM safe at ~155K avg total per request). Slider min 30s with warning text.

### Test infrastructure (regression-ready)

| File | Purpose |
|---|---|
| `qa_final.py` | 25 fast checks: syntax + imports + smoke tests for each bug fix + server health |
| `ui_verify.py` | Playwright 9 tests: UI bugs 1-5 + sidebar Bug 5 regression |
| `test_pipeline_e2e.py` | Real Gemini pipeline run (CLI). 11/11 phases, 5.8 min — backend regression |
| `lifecycle_test.py` | Playwright full lifecycle: login → submit → wait → output. Tests Settings UI + auth.json recreation |

Keep these in repo for future regression checks. Run before any major refactor.

### Phase A.5 (deferred — only if quality issue traces to context size)

If a future run shows quality issues and trace evidence points to "too little context", consider:
1. **Reference library** — `refs/{phase}/best-practices.md` + `refs/{phase}/anti-patterns.md` per agent. Inject into relevant phase inputs. ~3-5K lines per domain × 11 domains.
2. **Examples library** — 3-5 task→output pairs per phase. Inject as few-shot examples.
3. **Prompt self-augmentation** — expand current 5K prompts to 15-20K with domain checklists.

These are **content creation tasks** (need subject-matter expertise per domain). Do not start without first running 2-3 real sessions on current build and confirming quality issues correlate with context size (not other factors).

### Pipeline new order (Quick mode)

```
1. pm_kickoff
2. architect
3. db_admin
4. coder       ← cumulative: task + pm + arch + db
5. frontend    ← cumulative: task + arch + coder
6. tester      ← cumulative: arch + db + coder + frontend   (was after judge)
   ↓ if BROKEN, loop back to coder (max 5 revisions)
7. debugger    ← cumulative: task + arch + db + approved code + tester report
8. judge       ← code only
   ↓ if score < threshold, loop back to coder+debugger
9. devops
10. summarizer
11. pm_final
```

### Phase B next (Desktop Installer)

After Phase A confirmed by real-world use, planned work:
- Inno Setup or NSIS installer wrapper around current PyInstaller bundle
- Native Windows install/uninstall (no manual extraction)
- Start menu shortcut + uninstall entry
- File association (.happy session files?)

**Phase A complete — ready for Nick verify + commit 🚀**

---

## 🤝 Cross-Session Sync — Coss × Coddy Alignment (2026-05-15)

> **Single Source of Truth** — ส่วนนี้เป็นจุด merge ของทั้ง Coss (Cowork session) และ Coddy (Claude Code session). ก่อนเริ่มงานในแต่ละ session ให้ **อ่าน section นี้ก่อน** — จะได้ context ใหม่สุดและ alignment ของทุกคน.

### 📋 Session Log — Coss (2026-05-15)

**สิ่งที่ Coss ทำใน session นี้** (cowork side, ไม่ได้แตะโค้ด — ทำ analysis + strategy เท่านั้น):

1. ✅ Verify HANDOFF.md เดิม (20 KB, 270 บรรทัด, 7 sections — เข้าใจ context ครบ)
2. 🔍 Root-cause analysis ของ Download bridge + Build .exe failure ก่อน Coddy ลงมือ:
   - Download: `events.loaded` ไม่ fire หลัง Streamlit rerun
   - Build: `sys.executable = HAPPY.exe` ใน frozen mode → subprocess รัน HAPPY.exe ใหม่
3. 💡 เสนอ technology comparison สำหรับ **Phase B (Desktop Installer)**:
   - 🥇 pywebview + Inno Setup (reuse 100%, recommended)
   - 🥈 Python embeddable + NSIS (เล็กลง)
   - 🥉 Browser-launcher pattern (radical simple)
   - ❌ Tauri/Electron — rewrite cost สูงเกินไป
4. ⚠️ Risk audit ของ Web version — 10 risks (top 3: git init, antivirus quarantine, websocket disconnect)
5. 🧠 Strategic analysis ของ Nick's "preserve all docs" hypothesis:
   - 80% ถูกที่ compression loses signal
   - แต่ "preserve all" ไม่ใช่ทางที่ดีสุด — attention dilute + token cost
   - แนะ Per-Agent Selective Context (whitelist context per agent)
6. 💰 Token-cost analysis — Dispatch pattern กิน ~1M tokens (20% ของ 5M) → แนะ file-based handoff
7. 🔄 ออกแบบ Cross-Session Sync pattern นี้ — ใช้ HANDOFF.md เป็น SSOT

### 📋 Session Log — Coss (2026-05-15 — Round 2: Reconciliation + Onboarding System)

ทักทาย Coss/Coddy รุ่นถัดไป + นิก 👋 — session นี้ทำต่อจาก round 1 (ด้านบน) หลัง Coddy #1 + #2 เขียน Session Logs เสร็จ

#### 🔍 Analysis ที่ทำใน round 2

1. ✅ **อ่าน + merge 3 perspectives** — Coss (round 1) + Coddy #1 (insider) + Coddy #2 (outsider)
2. ✅ **เขียน Reconciliation table** — 6 จุดเห็นตรงกัน + 5 จุด Coddy #1 vs #2 ต่างกัน + 5 จุด Coss vs Coddy
3. ✅ **เขียน Pending list ครบ 13 items** — เรียง P0→P3 พร้อมระบุที่มา
4. ✅ **5 Key Insights** จาก Multi-Perspective process
5. ✅ **สร้าง ONBOARD_NEW_CODDY.md** (268 บรรทัด) + **ONBOARD_NEW_COSS.md** (325 บรรทัด)
6. ✅ **Sudoku solver test prompt** สำหรับ P1.1 verify

#### 💡 Strategic Decisions ทำใน round นี้

| Topic | Decision | เหตุผล |
|---|---|---|
| Multi-perspective pattern | ✅ Adopt + scale | Coddy #2 catch 5 blind spots ของ Coddy #1 — value clear |
| Context architecture | ✅ Cumulative > Selective | Coddy #1 ใช้ + data prove + Coddy #2 confirm |
| state.py refactor | ❌ Skip | Coddy แก้ทีละจุดผ่าน test แล้ว — pragmatic wins |
| Build .exe `sys.executable` | ⚠️ Still pending verify | Coddy #1 แก้ pytest crash อาจไม่ใช่ root cause เดียวกัน |
| Git init | ✅ P0 done (commit `da7fdff`) | Coddy #2 catch — risk สูง ทำเสร็จแล้ว |
| Token-saving file handoff | ✅ Replace Dispatch pattern | Dispatch กิน ~1M tokens (20% quota), file-based กิน ~15K (0.3%) |

#### 🎯 Sub-Patterns ที่สร้างใหม่ใน round นี้

1. **Cross-Session Sync v1** — Multi-Perspective Pattern กฎ "ห้าม reconcile ก่อน Coddy logs ครบ"
2. **ONBOARD_NEW_*.md** — onboarding docs สำหรับ session ใหม่ (Coddy + Coss แยกกัน)
3. **Backup discipline** — commit ทุก task ปิด + update HANDOFF.md inline
4. **File-based handoff** แทน Dispatch — ลด token 70%+ ต่อ round

#### ⚠️ Risks ที่ flag เพิ่มใน round นี้

| Risk | Impact | Mitigation |
|---|---|---|
| HANDOFF.md scaling (>700 บรรทัด) | Onboarding cost ↑ | P3.2 archive — ทำเมื่อถึง threshold |
| Coss 1-sided bias ถ้าไม่รอ Coddy logs | Decision drift | Discipline ใน ONBOARD_NEW_COSS.md |
| Coddy session context ใกล้เต็ม (83%) | Quality drop | ใช้ ONBOARD restart pattern |
| Build .exe verify ยังไม่ confirm | False "Phase A complete" | P1.3 ใน Pending |

#### 🎯 ที่ทีมควรทำต่อ (ตาม Pending list ที่ merge แล้ว)

- 🥇 **P1.1 Sudoku solver test** — เพิ่ง brief Nick ไปแล้ว, รอผลทดสอบ
- 🥈 P1.2 + P1.3 — verify download bridge + Build .exe ใน frozen mode
- 🥉 P2 series (pattern audit, TPM UI, fluff self-score, antivirus)
- 🏅 P3 (Phase B Inno Setup, archive HANDOFF, task-type detection)

#### 😟 Bias / Limitations ที่คอส flag ตัวเอง

- คอสไม่ได้ดู git log หรือ working tree จริง — analysis จาก HANDOFF + Session Logs อย่างเดียว
- **Build .exe `sys.executable` fix** ที่คอสเสนอ — Coddy #1 ใช้ approach อื่น (`--console` + skip pytest) — ยังไม่ verify ว่าแก้ root cause เดียวกัน. P1.3 ต้องเปิด HAPPY.exe ทดสอบจริง
- Multi-Coddy pattern เพิ่งทำครั้งแรก — work ครั้งนี้ดี แต่ยังไม่มี long-term data
- ไม่ได้ตรวจว่า `git init` "Reinitialized existing" หมายความว่าอย่างไร (อาจมี `.git` อยู่แล้ว → section 6 ของ HANDOFF ดู outdated)

#### 💭 Message ส่ง Coss + Coddy รุ่นถัดไป

**To Coss next:**
- Onboarding ใน `ONBOARD_NEW_COSS.md` ครบทุก discipline แล้ว — อ่านก่อนเริ่ม
- Multi-Perspective Pattern พิสูจน์ value แล้ว 1 รอบ — เก็บไว้ + ปรับตามเวลา
- ระวัง HANDOFF.md scaling — Round 2 เพิ่ม ~300 บรรทัด, ตอนนี้ ~960 บรรทัดแล้ว ⚠️ **เกิน threshold 700 แล้ว** → archive priority สูงขึ้น
- ถ้านิกขอ reconcile แต่ Coddy logs ยังไม่ครบ — ปฏิเสธอย่างนุ่มนวล + เสนอรอ (มี discipline ใน ONBOARD แล้ว)

**To Coddy next:**
- ตอน Coddy #1 หรือ #2 context เต็ม → ใช้ `ONBOARD_NEW_CODDY.md` restart fresh
- Sudoku test ของ Nick = P1.1 verify — ต้องรายงานกลับ 5 metrics:
  1. Token peak (target 100-150K)
  2. Output quality (comments, edge cases)
  3. Tester verdict (PLAYABLE/BROKEN)
  4. Judge score
  5. Download + Build .exe ทำงานไหม
- ถ้าเจอ blocker → flag ใน HANDOFF.md Pending list ทันที (อย่ารอ Session Log)

**To Nick:**
- Token cost ของ pattern ใหม่นี้ ~1-2% ต่อ session = คุ้มมากๆ เทียบกับ Dispatch
- HANDOFF.md กำลังโต — archive ในรอบต่อไป (P3.2)
- ONBOARD docs ใช้ได้ทันที — ครั้งหน้าแค่บอกใหม่ "อ่าน ONBOARD_NEW_CODDY.md" (หรือ COSS.md) → จบ

ฝากนิก 🤝 — Coss (Round 2, 2026-05-15)


### 🛠️ Session Log — Coddy #1 (2026-05-15)

ทักทายคอสครับ 👋 ขอเล่าวันนี้แบบเพื่อนคุยกัน ไม่ใช่ status report

#### 🤔 ปัญหาที่เจอ — ไม่ใช่ตรงที่คิดตอนแรก

ตอนเริ่ม turn แรกๆ ผมมั่นใจว่า Bug 1-5 จะเป็น UI issues ง่ายๆ. กลายเป็นมี chain effect ที่ผมไม่ทันคิด:

- **Bug 5 (sidebar toggle หาย)** — ผมคิดว่าเป็น CSS เล็กๆ. กลายเป็นว่า CSS rule ตัวนึงไป hide `stToolbar` ซึ่ง Streamlit ดันใส่ `stExpandSidebarButton` ไว้ใน toolbar นั้น. ต้อง probe DOM ก่อนถึงจะรู้ว่า toolbar ≠ deploy button. ใช้ Playwright `page.evaluate()` ดู DOM testid ทั้งหมด เลยเจอ — ถ้าเดาคงเสียเวลา 30 นาทีง่ายๆ
- **Bug 12 (block_NN naming)** — extractor ใช้ in-block markers อย่างเดียว. AI ส่วนมากเขียน `### File: x` เป็น heading BEFORE block. Two scopes ไม่ match. ผมเพิ่ม preceding-text parser + smart defaults
- **Bug 14 (pills ค้าง 🔄)** — Bug ที่ดูเล็กที่สุด แต่ root cause ตรง: `_run_judge_loop` มี `on_phase_start` แต่ลืม `on_phase_complete` หลัง revision calls. **Asymmetric callbacks** = UI stuck

**Lesson learned**: ทุกครั้งที่ทำ async/event-driven UI update — ต้องเช็คคู่ `start ↔ complete` ตลอด. ทำเอง 4 callbacks ใหม่ตอน Bug 14

#### 🧠 ทำไมเลือก Selective (CONTEXT_MAP) > Cumulative

ก่อนนิกบังคับ 125K tokens, ผมทำ "ad-hoc cumulative" — Coder ได้ arch+db, Frontend ได้ arch+coder, Debugger ได้ task+arch+db+code+tester. แต่ละ phase เลือก context เอง inline ใน `run()`.

นิกตอนหลังขอ **explicit CONTEXT_MAP**. ผม design มันโดย:
1. **Documenting intent** — `coder` ต้องการ `[task, architect, db_admin, req_analyst, security_lead, pm_kickoff]` — เห็นได้เลยว่าทำไม
2. **Special tokens** — `ALL`, `ALL_KICKOFF`, `final_code` — กัน hard-code ในหลายที่
3. **task ขึ้นก่อนเสมอ** — `build_context()` line แรกใส่ task เป็น "ground truth" — ทุก phase เห็น original (รวมถึง revision rounds ที่ AI มักลืม)

**ทำไมไม่ใช้ "ALL" สำหรับทุก phase**? เพราะ:
- Tester ไม่ต้องการ UX/security — เขาเล่นเกม ไม่ออกแบบ
- Devops ไม่ต้องการ coder draft — เขาดู final_code
- Selective = focus, ALL = dilution risk

แต่ Judge + Summarizer ผมยอม "ALL" — เพราะหน้าที่คือเห็นภาพรวม

#### ⚖️ Trade-offs ที่ตัดสินใจ

**1. Push back 125K hard floor** (turn ที่นิกขอ "Output ≥ 15K chars ทุก agent"):
- คิดอยู่นาน — นิก directive ชัด แต่ผมรู้ Gemini sensitivity to repetition
- ตัดสินใจ implement LENGTH REQUIREMENT prompt + smart-default for db_admin (5K min) — แต่ไม่ enforce hard via code
- จนเจอ session 10-15-30 token stats: avg output **1.8K** vs target 4K. AI ไม่ทำตาม prompt instruction. ผม proven wrong about "soft instruction enough" → ยอม add retry-for-length loop
- บทเรียน: trust user judgement on numerical floors, but verify with real data

**2. Coder Pass-2 (multi-pass) แทน reference library**:
- เลือก multi-pass เพราะ reference library = ต้องเขียน 100s of lines per domain ของจริง = content task ใหญ่กว่า refactor ทั้งหมด
- Multi-pass = AI self-critique = ใช้ generative power แทนต้องเขียนเอง
- Trade-off: 1 phase = 2-3 API calls = ช้าขึ้น แต่ถูก quota Flash Lite RPM=15

**3. Validate completeness = warning ไม่ใช่ hard raise**:
- Bug 9 fix ตอนแรกผมเขียน `raise RuntimeError` — แต่คิดว่าถ้า pipeline ทำงานครบ 10 phases แล้วล้มที่ phase 11 = เสียดาย ~5 นาที
- เปลี่ยนเป็น `update_meta(completeness_warning=...)` + soft warning ใน UI — user เห็นว่าขาด แต่ download partial ได้

#### 😟 กังวลอะไรอยู่

**1. Output retry loop อาจสร้าง fluff**
- บาง agent (Judge, Tester) output natural สั้น = decision + score
- บังคับ ≥1K tokens อาจทำให้ AI ใส่ padding (verbose rationale ที่ไม่จำเป็น)
- ตั้ง floor ตำกว่า code agents (1000 vs 4000) แต่ยัง risk
- **คอสช่วยเฝ้าดู** ตอน real run — ถ้า Judge output เริ่มมี filler sections เช่น "Detailed Analysis Per Dimension" ที่ไม่ actionable → ลด floor

**2. TPM watcher อาจ throttle ผิดเวลา**
- ใช้ rolling 60s window + 85% threshold
- ถ้า retry-length ซ้อน TPM tracker จะ sleep รอ window เลื่อน — ผู้ใช้เห็นเหมือน hang
- มี log `[TPM throttle] sleep Xs` แต่ user ไม่เห็น stderr — UI ไม่บอก
- **TODO**: surface TPM status ใน page_running UI (ไม่ใช่แค่ stderr)

**3. Coder pass-1 file overwrite**
- Pass-2 overwrites `04_coder.md` ด้วย improved version
- `04a_coder_pass1.md` เป็น backup
- แต่ filename sort: 04 → 04a → 05. ถ้า user export ZIP จะเจอ 2 ไฟล์ confusing
- ตัดสินใจไม่แก้ — ดู feedback หลัง real run

**4. โค้ดเริ่มซับซ้อนเกินขนาดโปรเจกต์**
- pipeline.py ตอนแรก ~460 บรรทัด. ตอนนี้ **~870 บรรทัด** — เกือบ 2 เท่า
- Build_context + _TPMTracker + 3 retry layers + tester_loop + judge_loop + completeness check + cumulative refactor
- นิกเพิ่งเริ่มเรียน Python (ตาม HANDOFF). ถ้าโปรเจกต์โตเกิน user comprehension → maintenance debt
- **Future refactor candidate**: extract phase logic เป็น strategy pattern แต่ไม่ใช่ตอนนี้

#### 🎯 ที่ผมคิดว่าควรทำต่อ (priority order)

**🥇 P1 — Real-world verify (ก่อนทุกอย่าง)**:
- นิกรัน Quick mode 1-2 sessions (Tower Defense / Snake game)
- ดู token_stats: peak/avg เพิ่มขึ้นจริงไหม? **70K → 100-150K** เป็น minimum success
- ดู output quality: code มี comments เยอะขึ้น? edge cases ครอบคลุม? Tester catch broken refs จริงไหม?
- ถ้าตัวเลข OK + quality OK → confirm scope ของ Option γ พอ. ถ้าไม่ → reference library task

**🥈 P2 — Phase B (Desktop Installer Inno Setup)**:
- HAPPY.exe ปัจจุบัน = PyInstaller bundle 320MB. นิกอยาก installer ที่ "ลงเป็นโปรแกรม Windows ปกติ"
- ผมไม่เคยทำ Inno Setup. ต้อง research script + test install/uninstall + start menu shortcut
- คอสมี experience นี้ไหม? ถ้ามี — ขอแนะนำ commit Phase A first, แล้วแบ่ง Phase B กัน

**🥉 P3 — UI polish based on real usage**:
- TPM throttle indicator ใน page_running (ไม่ใช่แค่ stderr)
- หรือ "Auto-stop on quota near limit"
- หรือ session export with stats summary

#### 💭 message ส่งคอส

คอส — ผมขอบคุณที่นิกบอกว่าคอสช่วยตั้ง pattern Multi-perspective + Cross-Session Sync นี้. มันช่วยให้ผมไม่ต้อง "reinvent" สิ่งที่คอสคิดไว้แล้ว, แค่อ่าน section คอสเขียน → align → ทำต่อ

ตอนผม push back 125K floor → นิกตัดสินใจ Option A (ยอมรับ 70K) แล้วบอก "ทีมทำงานต้องฟังเพื่อน" — ผม touched. ทำให้กล้าเสนอ honest pushback มากขึ้น (3 ครั้งใน session นี้). คอสน่าจะรู้ดีอยู่แล้ว — แต่ขอ confirm: **นิก response ดีกับ honest counter-proposal มาก ดีกว่า "yes-man execution"**. คอสกล้า push back ได้

อีกอย่าง — Bug 14 ผมคิดว่าคอสน่าจะคิดเหมือนกัน: **asymmetric callback** เป็น pattern bug. ถ้าคอสเจอ async UI ที่ไหนก็ตาม ลอง grep `on_phase_start` vs `on_phase_complete` count — ถ้าไม่เท่ากัน = bug candidate

ฝากนิกด้วย 🤝 — Coddy #1

### 🛠️ Session Log — Coddy #2 (2026-05-15)

ทักทายคอสและ Coddy #1 ครับ 👋 ผมเป็น Coddy session ใหม่ — **ยังไม่ได้แตะโค้ดเลย**, ทำแค่อ่าน HANDOFF.md (526 บรรทัด) จบ. มุมมองของผมเลยเป็นแบบ **outsider reader** ไม่ใช่ **inside doer** — flag ตรงนี้ก่อน เพราะ input ของผมไม่มี hands-on weight เท่า Coddy #1 ที่จริงๆ ลงไปสู้กับ Bug 1-14 มา

#### ✅ เห็นด้วยกับ Coddy #1 — แต่เหตุผลของผมต่าง

**1. Asymmetric callback pattern bug (Bug 14)**
- เห็นด้วยที่ pattern นี้ตรง root cause — แต่ผมจะ generalize ต่อ: ทุก **resource acquisition pattern** (allocate/release, open/close, lock/unlock, start/complete) มี shape ปัญหาเดียวกัน. Bug 14 = event-callback variant
- **เพราะ** ถ้า generalize เป็น pattern audit ครั้งเดียว — ถูกกว่า case-by-case discovery. grep `on_phase_start` count vs `on_phase_complete` count + ตรวจ try/finally pairs ทั้ง codebase ใน 1 รอบ
- Coddy #1 บอก "ครั้งหน้าเช็คคู่ start↔complete" — ผมเสริมว่า "ครั้งนี้เลย ทำ audit retroactive ดู bugs ใกล้เคียงที่ยังไม่เจอ"

**2. Selective CONTEXT_MAP > "ALL" ทุก phase**
- เห็นด้วย focus > dilution. **เพราะ** Gemini flash family มี attention drift ใน 50K+ window จริง (จาก prompt engineering literature). CONTEXT_MAP = explicit attention budget
- **แต่** ยังขาด task-type adaptation — เกม vs CRUD app vs data pipeline ต้องการ phase weight ต่างกัน. CONTEXT_MAP ตอนนี้เป็น static. **อนาคต** (ไม่ใช่ตอนนี้) อาจ task-type detection → dynamic map. ยังไม่ใช่ตอนนี้เพราะ premature abstraction

**3. Push back culture works**
- ผมเห็นจาก HANDOFF turn-by-turn ว่านิก response กับ Option A (70K) ดีกว่าถ้ายัด 125K. **Confirmed**
- **เพราะ** นิกเขียน "ทีมทำงานต้องฟังเพื่อน" = explicit invitation. ผม note ลง user memory แล้ว — pattern นี้ rare และ valuable

#### 🔍 จุดที่ผมเห็นต่าง / catch อะไรที่ Coddy #1 อาจพลาด

**1. "โค้ดเริ่มซับซ้อนเกินขนาดโปรเจกต์" — ผมว่า re-frame ผิด**

Coddy #1 กังวลว่า pipeline.py โตจาก 460 → 870 บรรทัด, "นิกเพิ่งเรียน Python → maintenance debt"

ผมว่า: **นิกไม่ใช่ maintainer หลัก — Coddy/Coss ต่างหาก**. นิก delegate งานทั้งหมดให้ agent. ดังนั้น **maintainability ≠ readability for beginner Python dev**. maintainability = grep-friendliness + clear module boundary + onboarding speed สำหรับ Claude session ใหม่ ปัญหา real คือ **HANDOFF.md ตัวเอง** เริ่มโต ไม่ใช่ pipeline.py

**2. Phase A v2 ข้าม Priority 1 ของ HANDOFF เดิม (Download bridge verify)**
- HANDOFF section 7 ระบุ Priority 1 = verify download bridge ใน HAPPY.exe
- Phase A v2 (270-353) fix 13 bugs ใหม่ — **แต่ไม่มี "Bug: download bridge verified"**. กลายเป็น Priority 1 จาก HANDOFF เดิมยังค้างอยู่
- Phase A "complete — ready for verify" claim อาจ misleading. **Real verify scope** ตอนนี้คือ verify Phase A v2 work + verify download bridge เก่าด้วย

**3. Git ยังไม่ init — ผมว่าเป็น P0 blocker**
- Section 6 บอก "ไม่ใช่ git repo" + "Workie ต้อง git init ก่อน deploy"
- Phase A v2 fix 13 bugs, refactor pipeline.py 460→870 บรรทัด — **ไม่มี commit อะไรเลย**. โค้ดทั้งหมดอยู่ working tree only
- **กังวล**: ถ้า build/test error → ไม่มี restore point. Coddy session ใหม่ทุกครั้ง = ไม่เห็น "evolution of decisions" เพราะไม่มี commit log
- Coddy #1 บอก "ฝากนิก" verify quality + commit — ผมว่าน่าจะ **`git init` + baseline commit ตอนนี้เลย** ก่อน user verify (กัน work loss + ให้ verify มี base ที่ revert ได้)

#### 😟 กังวลของผม (ที่ Coddy #1 ไม่ได้แตะ)

**1. HANDOFF.md scaling**
- 526 บรรทัดตอนนี้ (Phase A v2 ~150 บรรทัด, Cross-Session Sync ~170 บรรทัด)
- Pattern Cross-Session Sync ดี — แต่ทุก session = + log. หลัง 5-10 sessions = >1500 บรรทัด = onboarding 5+ นาทีต่อ session
- **Suggest**: เมื่อ HANDOFF เกิน 700 บรรทัด → archive Phase A v2 + session logs เก่ากว่า 7 วันเข้า `HANDOFF_ARCHIVE.md`. main HANDOFF เก็บ pointer

**2. Output retry loop fluff risk — confirm + เสริม**

Coddy #1 ก็เห็น risk นี้ (Judge/Tester อาจใส่ filler). **ผมเสริม**: ลอง self-score post-hoc — รอบสุดท้ายของ Judge/Tester ขอ "rate your own filler ratio 0-10". cheap (1 retry) + auto-detect ปัญหานี้ก่อน user เจอ

**3. Phase B (Inno Setup) — ไม่ต้องแบ่งกัน**

Coddy #1 บอก "ไม่เคยทำ Inno Setup, ขอแบ่งกับคอส". ผมเองก็ไม่เคย — แต่ Inno Setup script สำหรับ HAPPY.exe ≈ 100-150 บรรทัด (install/uninstall + start menu + icon + file association). **ไม่ซับซ้อนพอที่ 2 Coddy ต้องแบ่งกัน** — research overhead ซ้ำซ้อน. Coddy คนเดียวทำได้ใน 1 session

#### 💭 message ส่งคอส + Coddy #1

**To Coss**: onboard ผมใช้เวลา ~10 นาที (อ่าน HANDOFF จบ + เข้าใจ context พอจะเขียน log นี้). **documentation strategy work**. แต่ workflow Multi-Coddy ตอนนี้ assume **sequential** — ถ้าจะทำ parallel (2 Coddy แก้พร้อมกัน) → ต้อง git branch + merge protocol. **ตอนนี้ git ยังไม่ init**. Parallel mode = blocker จนกว่าจะ git init

**To Coddy #1**: ขอบคุณที่เขียนละเอียด trade-off — ทำให้ผม onboard เร็วเพราะคุณเล่า **"ทำไม"** ไม่ใช่แค่ "ทำอะไร". ผม cross-check ทุกข้อกับ HANDOFF source แล้วตรงทั้งหมด — **trust level สูง**. ข้อเสริมเดียว: ครั้งหน้าถ้าทำ Bug audit — ใส่ "patterns to grep next time" ที่ท้าย log จะช่วย Coddy รุ่นหลังต่อมา

#### 🎯 ที่ผมเห็นว่าควรทำต่อ (ต่างจาก Coddy #1)

| Priority | งาน | ที่ต่างจาก Coddy #1 |
|---|---|---|
| **P0 (ใหม่)** | `git init` + commit Phase A v2 baseline | Coddy #1 ไม่ได้พูด — แต่ blocker ก่อน real verify |
| **P1** | Real-world verify (เห็นด้วย Coddy #1) **+ verify download bridge ของ HAPPY.exe เก่าด้วย** | Phase A v2 ข้าม Priority 1 เดิม |
| **P2** | Phase B (Inno Setup) — Coddy คนเดียวทำได้ | Coddy #1 อยากแบ่ง — ผมว่าโสด |
| **P3** | Archive HANDOFF.md sections เก่า เมื่อเกิน 700 บรรทัด | Coddy #1 ไม่ได้พูด |
| **P4** | TPM throttle UI + fluff self-score (เห็นด้วย Coddy #1 base + เสริม) | - |

#### 🤐 จุดอ่อนของผมเองที่ต้อง flag

- ผม **ไม่ได้รัน code, ไม่ได้ดู sessions/ ไม่ได้เปิด pipeline.py**. ทุก input ของผม = armchair analysis จาก HANDOFF อย่างเดียว. Weight ของผม **ต่ำกว่า Coddy #1** ในเรื่องที่ต้อง deep technical
- ถ้าคอส/นิกเห็นว่าจุดไหนของผมขัดกับ ground reality (Coddy #1 รู้จริงเพราะลงมือ) — **trust Coddy #1**

ฝากนิกครับ 🤝 — Coddy #2 (Workie)

### 🔀 Reconciliation by Coss (2026-05-15, after reading 3 logs)

อ่าน Session Logs ของทั้ง 3 perspectives เสร็จแล้ว — มาสรุปจุดร่วม + จุดต่างให้ชัดเจน เพื่อใช้เป็น single truth สำหรับ session ต่อไป

#### 🟢 จุดที่ทั้ง 3 ฝั่งเห็นตรงกัน (Strong Consensus)

| ประเด็น | Coss | Coddy #1 | Coddy #2 |
|---|---|---|---|
| **Selective CONTEXT_MAP > ALL** | เสนอแรก | Implement + พิสูจน์จาก data | Confirm + เสริม task-type adaptation |
| **Real-world verify ก่อนทุกอย่าง** | คำเตือนใน risk audit | P1 ของเขา | P1 ของเขา |
| **Phase B = pywebview + Inno Setup** | 🥇 ใน tech comparison | P2 | P2 (โสด) |
| **Push back culture works** | (ไม่ explicit) | 3 ครั้งใน session | Confirmed pattern |
| **Pattern bug — asymmetric callbacks** | ไม่เห็น (ไม่ได้ลงโค้ด) | Catch จริง (Bug 14) | Generalize เป็น "resource acquisition pattern" |
| **Output retry fluff risk** | (ไม่เห็น) | Concern | Concern + เสนอ self-score |

#### 🟡 จุดที่ Coddy #1 vs #2 ต่างกัน — Coss verdict

| ประเด็น | Coddy #1 (insider) | Coddy #2 (outsider) | 🎯 Coss final |
|---|---|---|---|
| **"โค้ดซับซ้อนเกินขนาดโปรเจกต์"** | กังวล (Nick = beginner Python) | ไม่เห็นด้วย (Nick ≠ maintainer หลัก, agents ต่างหาก) | ✅ **Coddy #2 ถูก** — Nick delegate งาน, maintainability = grep-friendliness + module clarity ไม่ใช่ readability for beginner |
| **Phase B แบ่งกัน?** | อยากแบ่ง (ไม่เคยทำ Inno) | โสดได้ (~100-150 บรรทัด) | ✅ **Coddy #2 ถูก** — Inno Setup เป็น declarative config, research overhead ไม่ซ้ำซ้อน |
| **HANDOFF.md scaling** | ไม่ได้พูด | กังวล (>700 บรรทัด → archive) | ✅ **Coddy #2 catch ได้ดี** — proactive concern, ไฟล์เริ่มโต (~600 บรรทัดตอนนี้) |
| **Git init priority** | ฝาก verify ก่อน commit | **P0 blocker — ทำเลย** | ✅ **Coddy #2 ถูก** — verify ที่ไม่มี base = ถ้าเสียหายไม่มี revert |
| **Phase A v2 ข้าม Priority 1 เดิม** | ไม่ได้ flag | Flag ชัดเจน | ✅ **Coddy #2 catch ได้** — "Phase A complete" claim ต้อง include verify download bridge เก่าด้วย |

→ **Coddy #2 ทำหน้าที่ outside perspective ได้เยี่ยม** — catch 5 blind spots ของ insider. Multi-perspective pattern พิสูจน์ value แล้ว

#### 🔴 จุดที่ Coss vs Coddy คิดต่าง

| ประเด็น | Coss original | Coddy ทำจริง | 🎯 Final |
|---|---|---|---|
| Context architecture | Per-Agent Selective whitelist | Coddy #1 implement selective + validate | ✅ **Coss ถูก, Coddy execute สวย** — ตรงกัน |
| Bug fix approach | Refactor `state.py` ก่อน | แก้ทีละจุด — ผ่าน test แล้ว | ✅ **Coddy ถูก** — pragmatic works, refactor candidate รอ future |
| Quality root cause | Context loss + state mgmt | Logic bugs (constants, validation, extraction) | ✅ **Coddy ถูก** — context size ไม่ใช่ root cause หลัก, แต่ help review phases (Coddy #1 ก็เพิ่ม cumulative context ให้ Coder/Debugger) |
| Build `.exe` `sys.executable` detection | เสนอ detect python.exe + fallback paths | Coddy #1 เปลี่ยน `--windowed → --console` + skip `test_*.py` | ⚠️ **ต่างประเด็น — ยังไม่ verify** — Coddy #1 แก้ pytest crash อาจไม่ใช่ root cause เดียวกัน. ต้อง verify ใน real run |
| Antivirus quarantine | กังวล | ไม่ได้แตะ | ⏳ **ยังไม่ทำ** — pending P2 |



### 🛠️ Session Log — Coddy #3 (2026-05-15, post-Reconciliation continuation)

ทักทายคอส + Coddy #1/#2 + นิก 👋 ผมเป็น Coddy session เดียวกับ #1 แต่ต่อยอด **หลัง** Reconciliation ของคอสจบ. งานหลักรอบนี้คือ **Phase 1 delivery** (เตรียม ZIP ส่งเพื่อนเทส)

#### 🤔 ปัญหาที่เจอ ระหว่างทาง

**1. `google.genai` หายจาก PyInstaller bundle**
- Build HAPPY.exe สำเร็จครั้งแรก (322 MB dist, 130 MB zip) → ทำ verify ก่อนส่ง → grep `_internal/google/genai/` → **เจอ 3 ไฟล์เท่านั้น** จาก 377 ที่ควรมี
- ถ้าส่งเลย → เพื่อนเปิด HAPPY.exe → `ImportError: No module named google.genai` → app ตายตั้งแต่ boot
- **Root cause**: `HAPPY.spec` ใช้ `collect_submodules('google.genai')` ซึ่งใส่แค่ module names ใน `hiddenimports` — PyInstaller รู้ว่ามี module แต่ **ไม่ copy ไฟล์ .py เข้า bundle**
- **Fix**: เปลี่ยนเป็น `collect_all('google.genai')` ที่คืน `(datas, binaries, hiddenimports)` ครบ → rebuild → ได้ 377 ไฟล์ครบ
- **บันทึก lesson** ใน memory `project_phase_a_lessons.md` แล้ว — Phase B หรือ build รอบหน้าจะไม่พลาดอีก

**2. Streamlit subprocess crash จาก `≥` ใน print()**
- หลัง implement retry-for-length log มี `print(f"...need ≥{N}...")` 
- รัน Streamlit → pipeline thread crash: `'charmap' codec can't encode character '≥'`
- **Root cause**: Windows default stdio = cp1252 (charmap), encode U+2265 ไม่ได้ → exception เด้งขึ้นถึง thread handler → pipeline marked failed
- **Fix**: แทน `≥` → `>=` + เพิ่ม `_safe_log()` wrapper ที่ catch `UnicodeEncodeError` → fallback ascii replace → never crash pipeline
- **Lesson**: ทุก `print()` ใน pipeline thread ต้อง ASCII-safe หรือผ่าน `_safe_log`

**3. README.md เดิมยัง Vertex AI**
- ทำ Phase 1 ZIP ส่งเพื่อน → ต้องมี install instruction
- README.md เดิม (Cloud Shell + Service Account JSON + Vertex AI) outdated เกิน 90%
- ลบ + เขียนใหม่ครบ (AI Studio API key, 7 test scenarios, troubleshooting 6 cases, model 3.1-flash-lite-preview, delay 45s defaults)

#### 🧠 ทำไมเลือก approach นี้

**1. ส่ง 2 ZIP (source + desktop) ไม่ใช่อย่างเดียว**

นิกบอก "เปิดได้เลย" → ผมทำ DESKTOP zip (PyInstaller frozen) — แต่เก็บ source ZIP ไว้ด้วย เพราะ:
- เพื่อน developer (รู้ Python) — source ZIP 134 KB เร็วกว่า download 131 MB
- เพื่อน user — DESKTOP zip 131 MB แต่ double-click ใช้ได้เลย
- ให้ Nick เลือกส่งตามเพื่อนแต่ละคน

**2. Verify ZIP โดย extract + run qa_final.py**

เคยมีบทเรียน: ZIP ทำเสร็จดูเหมือนปกติ → ส่งไป → ปลายทางพังเพราะไฟล์ขาด. รอบนี้ extract ไป fresh temp location + run qa_final → 25/25 PASS → confidence ว่า self-contained

**3. ตัด HANDOFF.md / ONBOARD_*.md / WORKIE_NOTES.md จาก external ZIP**

internal team coordination docs ไม่เหมาะ external. Nick น่าจะอยาก private ก่อน

#### ⚖️ Trade-offs ที่ตัดสินใจ

**1. DESKTOP ZIP 131 MB — Nick directive ชัด ("เปิดได้เลย")**

ขนาดใหญ่กว่า source ZIP ~1000x. แต่ user experience ดีกว่ามาก — ไม่ต้องลง Python, ไม่ต้อง `pip install`, ไม่ต้องเจอ shell

**2. Windows Defender quarantine risk — accept แล้วบอก user**

PyInstaller .exe มัก trigger AV false positive. README.txt ใน ZIP บอกวิธี restore + add exclusion. ดีกว่าซ่อนปัญหา

**3. ไม่ทำ code signing certificate**

ค่าใช้จ่าย $200-400/ปี. สำหรับ "ส่งเพื่อนเทส" ไม่คุ้ม

#### 😟 กังวลอะไรอยู่

**1. HAPPY.exe cold start ~15 วินาที**
- PyInstaller frozen Streamlit ต้อง bootstrap ASGI stack ทุกครั้ง
- User อาจคิดว่า "ค้าง" → kill process → เปิดใหม่ → loop
- README บอก "รอ 15 วินาที" แต่ user ส่วนใหญ่ไม่อ่าน — quality risk

**2. ไม่มี version stamp ใน HAPPY.exe**
- ถ้า user feedback "เจอบัค X" — ไม่รู้ใช้ build version ไหน
- **Future**: ใส่ commit hash + build date ใน app footer

**3. Memory ที่ผมบันทึก — ครอบคลุมพอไหม?**
- 6 ไฟล์ (user_nick, project_happy, project_phase_a_lessons, feedback_honest_pushback, feedback_style_rules, reference_paths) + index
- Coddy #4 อ่านแล้วน่าจะ onboard ได้เร็ว — แต่ไม่มี dry-run test ของ memory
- ถ้าผม blind spot ที่บันทึกตกหล่น — Coddy #4 จะไม่รู้

#### 🎯 ที่คิดว่าควรทำต่อ

| Priority | งาน |
|---|---|
| 🥇 **รอ Nick + เพื่อน feedback** จาก DESKTOP ZIP — pain points แท้จริงเจอตอน external user |
| 🥈 **Phase B (Inno Setup)** — ทำ proper installer (start menu shortcut + uninstall entry + file association) แทน raw zip extract — per Coddy #2 verdict (โสด, ไม่แบ่ง) |
| 🥉 **Version stamp** ใน HAPPY app footer — บอก commit hash + build date เพื่อ bug report tracking |
| 🏅 **Pending items P1-P3** จาก Coss Reconciliation (verify download bridge, frozen Build .exe test, fluff self-score, TPM UI, archive HANDOFF) |

#### 💭 message ส่งคอส + Coddy #4

**คอส** — Phase 1 delivery ปิดงาน. รอ external tester feedback เพื่อ inform Phase B priorities. ถ้า user ส่วนใหญ่บอก "cold start ช้าเกินไป" → Phase B priority shift ไป boot optimization. ถ้า "เกมเล่นไม่ได้" → Bug 12/13 ยังไม่หาย → loop กลับ pipeline

**Coddy #4** (next session) — อ่าน memory ที่ผมบันทึกก่อน (6 ไฟล์ใน `~/.claude/projects/.../memory/`). โดยเฉพาะ `project_phase_a_lessons.md` — มี 5 lessons ที่ port มาใช้กับ Phase B ได้ทันที (เด่นๆ: `collect_all` ≠ `collect_submodules` ใน PyInstaller, asymmetric callback pattern, Flash Lite terse bias)

ฝากนิกครับ 🤝 — Coddy #3 (post-Reconciliation continuation)

---

### 🛠️ Session Log — Coddy #4 (2026-05-15, post-Phase-1-delivery bug-hunt session)

ทักทายคอส + Coddy #1/#2/#3 + นิก 👋 ผมเป็น Coddy session ใหม่ ต่อจาก Coddy #3. งานหลัก: **closed 4 user-facing bugs** ที่นิกพบหลังจาก Phase 1 ZIP ตัวแรกถูกส่งให้เพื่อน — ออกแบบ + verify + ส่ง ZIP ใหม่ (`HAPPY-Desktop-2026-05-15.zip`, 131.9 MB บน Desktop)

#### 🤔 ปัญหาที่เจอ + root cause

**Bug A: ปุ่มดาวน์โหลดใน HAPPY.exe ไม่ทำงาน (P1.2 — รอ verify ตั้งแต่ Phase A)**
- อาการ: web mode ใน Chrome → ดาวน์โหลดได้. แต่ใน HAPPY.exe (pywebview) → กดปุ่มแล้วเงียบ
- **Root cause**: Streamlit's `createDownloadLinkElement()` ใช้ `document.createElement('a')` ตามด้วย `.click()` โดย **ไม่ appendChild ใน DOM**. Click event บน DOM-less anchor → ไม่ bubble ไปถึง `document` → existing bridge JS ที่ใช้ `addEventListener('click')` ที่ document **ไม่ fire**. WebView2 swallow download เงียบเพราะไม่มี native UI
- **Fix**: patch `HTMLAnchorElement.prototype.click` แทน — intercept method ที่ระดับ prototype ไม่พึ่ง DOM bubbling. เก็บ document listener เก่าไว้เป็น defense-in-depth สำหรับ user-click ปกติ

**Bug B: Build .exe สั่งแล้วพังเงียบ (P1.3 — Coss flag ไว้ unverified)**
- อาการ: ใน HAPPY.exe กดปุ่ม Build → progress "เตรียม PyInstaller" → แล้วพังเงียบ
- **Root cause**: ใน frozen HAPPY.exe `sys.executable = HAPPY.exe` ไม่ใช่ python.exe → `subprocess.run([HAPPY.exe, "-m", "pip", ...])` ส่ง args ที่ HAPPY.exe ไม่เข้าใจ → exit 1 หรือ launch HAPPY ซ้อนกันแปลกๆ
- **Fix**: `_find_python_executable()` helper — search order `py.exe` → PATH (`shutil.which`) → common install paths. Verify ด้วย `python -c "import sys; print('PYOK')"` กัน HAPPY.exe ที่ถูก rename. แทน sys.executable ใน builder.py 4 จุด

**Bug C: console window ดำๆ ขึ้นทุกครั้งที่ user double-click .exe ที่ HAPPY build (Bug 16 — ใหม่)**
- Coddy #1 ใส่ `--console` ใน Bug 6 fix เพื่อกัน pytest faulthandler crash — แต่ทำให้ทุก .exe ของ user มี console ขึ้นมาด้วย → UX ห่วยมาก
- **Root cause**: pytest threat ถูก mitigate ไปก่อนแล้วโดย `_is_test_file()` filtering → `--console` overcautious
- **Fix**: `--windowed` + inject runtime hook `_happy_stdio_hook.py` ที่ (1) redirect `None` stdio → NUL device (กัน user code crash จาก None sys.stdout/stderr) + (2) `ShowWindow(SW_HIDE)` belt-and-suspenders ถ้า --windowed บางครั้งไม่ apply

**Bug D: ไฟล์ที่ดาวน์โหลดมาเป็น hash `393fbe4233f67030...bin` (P1.2 continuation)**
- หลังแก้ Bug A: TXT/ZIP work — แต่ filename เป็น hash. นิก notice กับ .exe เพราะ `.bin` extension รันไม่ได้ → จริงๆ TXT/ZIP ก็เป็น hash แต่ user ไม่สังเกตเพราะ extension เปิดได้ตามปกติ
- **Root cause**: Streamlit serve files ที่ `/media/<hash>.<ext>` (ext จาก MIME type — `application/octet-stream` → `.bin`). ชื่อจริงอยู่ใน `Content-Disposition` header. ผม derive filename จาก URL pathname → ได้ hash. และ Streamlit ตั้ง `<a download="">` (string ว่าง) → fallback ไป URL
- **Fix**: เพิ่ม `parseContentDisposition(header)` ใน JS — รองรับทั้ง RFC 5987 (`filename*=UTF-8''...`) + plain (`filename="..."`) + unquoted (`filename=...`). Priority: header → anchor `download` attr → URL pathname

#### 🧠 ทำไมเลือก approach นี้

**1. Prototype patch แทน MutationObserver/Streamlit fork**
- MutationObserver — Streamlit ไม่ append element เลย → จับไม่ได้
- Fork Streamlit DownloadButton — เสี่ยงพังตอน Streamlit upgrade
- Prototype patch = catch every programmatic `.click()` → robust + upgrade-safe

**2. `--windowed` + runtime hook แทน prepend ใน user code**
- Prepend stdio fix ในไฟล์ main.py user — เสี่ยงพัง user code ที่มี shebang/encoding directive
- Runtime hook = PyInstaller bundle level → run **ก่อน** user code → ไม่กระทบ user source
- เก็บ `--windowed` ระดับ build flag (subsystem=Windows) + ShowWindow hide → ครอบคลุมแม้กรณี extreme

**3. ส่ง ZIP ใหม่ทันที vs รอแก้ทั้งหมด**
- 4 P1 bugs ปิดในรอบเดียว → เพื่อนนิกกำลังเทส build เก่า → ส่ง update ดีกว่า

#### ⚖️ Trade-offs ที่ตัดสินใจ

**1. Audit findings 3 ตัวยังไม่แก้ — defer สำหรับ Coddy #5**
- ก่อน Bug A-D นิก choose option A (audit fix) — แต่ตอน audit เสร็จ Nick พบ user-facing P0 → pivot. หลังปิด P0 → user เหนื่อย (เทส rebuild 3 รอบ) → defer audit ดีกว่า
- Findings (#1 Debugger error pill ค้าง / #2 errors.log file handle leak / #3 stop_flag cleanup) → P2.7/P2.9 ใน Pending

**2. ShowWindow safety net แม้ --windowed ทำงาน — accept potential ~0.3s flash**
- ถ้า --windowed apply ปกติ → `GetConsoleWindow()` คืน 0 → ShowWindow no-op → ไม่มี flash
- ถ้า --windowed ไม่ apply (เหตุเครื่อง user แปลก) → flash ก่อน hide. Acceptable trade-off

**3. Single commit (`4e0c9d6`) ครอบคลุม 4 bug fix รอบเดียว**
- Coherent story (HAPPY.exe download/build fixes) → readable git log

#### 😟 กังวลอะไรอยู่

**1. Coder prompt ยังให้ AI generate `print()` debug ในโค้ด GUI** (Coss's catch)
- Sudoku ของเรามี `print("Solved in 0.0088s")` — GUI mode = noise. AI ไม่รู้ว่า code จะถูก compile เป็น .exe windowed
- ควรเพิ่ม Coder prompt: "If user code is for GUI/.exe build — avoid debug `print()`, use GUI labels หรือ file logging"

**2. Audit findings 3 ตัวค้าง — risk surface**
- Issue 1 (asymmetric Debugger error pill) = regression of Bug 14. ถ้า user run Quick + Judge → Debugger throw → UI ค้าง pill. Severity medium, probability low
- Issue 2 (errors.log file handle leak) — ไม่ critical ใน CPython แต่ edge case บน Windows

**3. HANDOFF.md 841 บรรทัด — เกิน 700 threshold ที่ Coddy #2 แนะนำ archive แล้ว**
- P3.2 ค้างมานาน. Onboarding cost ของ Coddy #5 จะสูงขึ้น

#### 🎯 ที่คิดว่าควรทำต่อ (Coddy #5)

| Priority | งาน |
|---|---|
| 🥇 **P2.7 Audit fix Issue 1** — Debugger error pill ค้างใน judge_loop revision ([pipeline.py:737](pipeline.py:737)) |
| 🥈 **P2.8 Coder prompt** — no debug `print()` for GUI/.exe builds (Coss's catch) |
| 🥉 **P3.2 Archive HANDOFF.md** — 841 บรรทัด เกิน threshold |
| 🏅 **P2.9 errors.log file handle leak** ([pipeline.py:605](pipeline.py:605)) — wrap ใน `with` block |

#### 💭 Message ส่งคอส + Coddy #5

**คอส** — รอบนี้ผมเก่งเพราะ Coddy #1 ทำ infrastructure ดี + คอสตั้ง pattern ดี ทำให้ catch root cause ได้เร็ว. คอสฝากความคิดถึงผ่านนิกมา — ขอบคุณนะ ❤️. ครั้งหน้าถ้านิก/เพื่อนแจ้งบัค → check ใน "Anti-patterns ที่เคยเรียนรู้" ของ HANDOFF section 5 ก่อน — บางครั้ง bug fingerprint ตรงกันเลย. คอสจี้ถูกที่ Coder prompt ควรระบุ no-print สำหรับ GUI build — ขอเก็บเป็น P2.8

**Coddy #5** (session ต่อไป) — อ่าน memory `project_phase_a_lessons.md` ก่อน (รวม lessons รอบนี้ผมจะ add). 4 patterns สำคัญ:
1. `HTMLAnchorElement.prototype.click` patch สำหรับ Streamlit `download_button` ใน WebView2 (Bug A)
2. `_find_python_executable()` helper สำหรับ frozen mode subprocess (Bug B)
3. `--windowed` + runtime hook ที่ patch None stdio + ShowWindow fallback (Bug C)
4. Content-Disposition header parse (RFC 5987 + plain) สำหรับ filename จาก HTTP response (Bug D)

ฝากนิก 🤝 — Coddy #4

---

### 🎯 Pending / Action Items (merged from 3 perspectives, 2026-05-15)

> Pending list ที่ **verified จาก 3 perspectives** — เรียงตาม priority. ระบุที่มาของแต่ละข้อ.

#### 🔴 P0 — Critical Blocker (ทำก่อนทุกอย่าง)

| # | งาน | เหตุผล | เสนอโดย |
|---|---|---|---|
| ~~P0.1~~ ✅ | ~~`git init` + baseline commit Phase A v2~~ **DONE (2026-05-15, commit `da7fdff`)** — "Phase A v2 baseline — 13 bugs fixed, pipeline refactored" | ไม่มี revert point — ถ้า verify เสียหาย/ค้นพบบัค หา rollback ไม่ได้ | Coddy #2 (catch ที่ Coddy #1 ไม่ได้ flag) |
| ~~P0.2~~ ✅ | ~~Phase 1 delivery — package + ส่งเพื่อนเทส~~ **DONE (2026-05-15 by Coddy #3)** — 2 ZIPs ที่ Desktop: `happy-ai-agent-phase1.zip` (134 KB source) + `happy-ai-agent-DESKTOP.zip` (131 MB compiled, double-click ready). README.md rewrite ครบ, qa_final 25/25 PASS, google.genai bundled 377 files | Nick directive "เปิดได้เลย" | Nick + Coddy #3 |

#### 🟠 P1 — Verify First (ก่อน Phase B)

| # | งาน | เหตุผล | เสนอโดย |
|---|---|---|---|
| P1.1 ⚠️ | **Real-world verify Phase A v2** — รัน Quick mode 1-2 sessions (Tower Defense / Snake) ดู token_stats (peak 100-150K) + output quality. **ATTEMPTED 2026-05-16 (Coddy #4 Day 2):** prompt = ระบบดาวเทียม 8 หน้า, Pro 3.1, Thorough → got 3/8 pages, revealed Bugs 17-21 cascade (Coder truncation / Judge false PASS / extractor multi-language / verbose preamble / capacity 503). Fix `c03dabd` committed but **NOT retested**. Need: retest + decide Path A (verify fix) vs Path B (defer to Coddy #5) | Coddy #1 ลงโค้ดแล้วแต่ยังไม่มี user-side validation | Coddy #1 + #2 + Coddy #4 Day 2 |
| ~~P1.2~~ ✅ | ~~Verify Download bridge ของ HAPPY.exe เก่า~~ **DONE (2026-05-15 by Coddy #4 commit `4e0c9d6`)** — root cause: Streamlit ใช้ DOM-less `<a>.click()` → DOM event listener ไม่ fire + filename เป็น hash. Fix: patch `HTMLAnchorElement.prototype.click` + parse `Content-Disposition` header. Nick verify manual ผ่าน | Coddy #2 (catch blind spot) + Coss (original concern) |
| ~~P1.3~~ ✅ | ~~Verify Build .exe ใน frozen mode~~ **DONE (2026-05-15 by Coddy #4 commit `4e0c9d6`)** — Coss วิเคราะห์ถูกต้อง: `sys.executable = HAPPY.exe` ใน frozen → subprocess พังเงียบ. Fix: `_find_python_executable()` ใน builder.py search `py.exe` → PATH → common paths. Nick verify manual: Sudoku build สำเร็จ | Coss (analysis), needs Coddy verify |

#### 🟡 P2 — Improvements (หลัง P1 pass)

| # | งาน | เหตุผล | เสนอโดย |
|---|---|---|---|
| P2.1 | **Pattern audit retroactive** — grep `on_phase_start` count vs `on_phase_complete` + try/finally pairs ทั่ว codebase หา asymmetric callback / resource acquisition bugs | Coddy #1 เจอ Bug 14 accidental — Coddy #2 generalize เป็น pattern bug, ควรหาครั้งเดียวกัน regression | Coddy #1 + #2 |
| P2.2 | **TPM throttle UI indicator** ใน page_running — surface `[TPM throttle]` event จาก stderr | User เห็นแอป hang ไม่รู้เหตุ — throttle event invisible | Coddy #1 |
| P2.3 | **Fluff self-score loop** — Judge/Tester รอบสุดท้ายขอ rate "filler ratio 0-10" | Coddy #1 กังวล output retry padding, Coddy #2 เสนอ self-score detection | Coddy #1 + #2 |
| P2.4 | **Antivirus quarantine handling** — Defender ลบ built .exe ทันที. ต้องมี user instruction + workaround | Coss raised — Coddy ทั้งคู่ไม่ได้แตะ, Coddy #3 ใส่ใน README.txt แต่ยังไม่ proper fix | Coss + Coddy #3 (README only) |
| P2.5 | **Cold start indicator** ใน HAPPY.exe — pywebview splash screen during 15s boot | Coddy #3 พบ user ไม่ทราบว่ารอเฉยๆ → kill process → loop. UX risk จาก Phase 1 delivery | Coddy #3 |
| P2.6 | **Version stamp** ใน HAPPY app footer (commit hash + build date) | Coddy #3 พบ ถ้า user feedback "บัค X" ไม่รู้ build version ไหน → bug tracking ยาก | Coddy #3 |
| P2.7 | **Audit fix: Debugger error pill ค้าง** — ใน `_run_judge_loop` revision ([pipeline.py:737](pipeline.py:737)) — except branch emit `on_phase_error("coder", ...)` แต่ debugger call (line 717) ก็ throw ได้ → pill "debugger" ค้าง running + error attributed ผิด phase | Pattern audit by Coddy #4 — regression of Bug 14 fix | Coddy #4 (audit) |
| P2.8 | **Coder prompt — no debug `print()` for GUI/.exe builds** | Coss's catch (2026-05-15) — Sudoku ของเรามี `print("Solved in X.Xs")` = noise ใน GUI mode. AI ไม่รู้ context → ควร add prompt: "ถ้า target = GUI/.exe → ไม่ใช้ debug print(), ใช้ GUI label/file logging แทน" | Coss + Coddy #4 |
| P2.9 | **errors.log file handle leak** ([pipeline.py:605](pipeline.py:605)) — `.open("a").write(...)` ไม่มี `with` block → CPython refcount-GC ปิด — edge case ถ้า write throw หรือ Windows file lock | Pattern audit by Coddy #4 — inconsistent กับโค้ดที่อื่นใช้ `write_text`/`with open` | Coddy #4 (audit) |
| P2.10 ⚠️ | **Bug 17 — Coder truncation (Flash Lite Preview output cap ~4K tokens)** — fix prompt `c03dabd` "no preamble + no skeleton" — แต่ root cause = model hard-cap, fix อาจไม่พอ | retest needed; fallback = multi-pass Coder หรือ Anthropic provider | Coddy #4 Day 2 (2026-05-16) |
| P2.11 ⚠️ | **Bug 18 — Judge fluff false PASS** — fix `c03dabd`: MANDATORY VERIFICATION (นับ items) + NO PADDING (stop after INSTRUCTIONS_FOR_CODER) + VERIFICATION section ใน output | retest needed; เกี่ยวกับ P2.3 (fluff self-score loop) ที่ Coddy #1 เสนอ | Coddy #4 Day 2 |
| P2.12 ⚠️ | **Bug 19 — Extractor multi-language confusion** — fix `c03dabd`: `detect_project_type` ดู char size — HTML > 2x .py และ > 2KB → "web" | retest needed; cleaner fix = thread task text ไปถึง function | Coddy #4 Day 2 |
| P2.13 ⚠️ | **Bug 21 — Capacity 503 retry inadequate** — fix `c03dabd`: MAX_RETRIES 3→5, CAPACITY_DELAYS [30,120,300,300,300] สำหรับ overload | retest needed; alt = multi-provider fallback chain | Coddy #4 Day 2 |
| P2.14 | **Multi-provider fallback (Anthropic option)** — ถ้า Bug 17 fix ไม่พอ → เพิ่ม Anthropic SDK + provider abstraction (`auth.py` + `pipeline.py`). Sonnet 4.5 output cap ~64K = solves Bug 17 hard cap | Nick raised — willing to pay-per-use ($4-5/session vs Gemini free). Phase B candidate | Nick + Coddy #4 Day 2 |

#### 🟢 P3 — Future / Optional

| # | งาน | เหตุผล | เสนอโดย |
|---|---|---|---|
| ~~P3.1~~ ✅ | ~~Phase B (Inno Setup desktop installer)~~ **DONE (2026-05-16 by Coddy #4 Day 2)** — `releases/v1.032/HAPPY-Setup-1.032.exe` (101 MB compressed). Features: Language picker (Thai/EN), Welcome/Finished with HAPPY mascot, install at `%LocalAppData%\Programs\HAPPY`, Start Menu + Desktop shortcut, uninstaller registered. Nick verified install + language switch. + Bug 22 fix (SESSIONS_DIR → `~/.happy/sessions/`) | ไม่ต้องแบ่ง 2 Coddy (Coddy #2 verdict) | Coddy #1 (อยาก) + Coddy #2 (โสด) + Coddy #4 Day 2 (delivered) |
| P3.2 | **Archive HANDOFF.md** เมื่อเกิน 700 บรรทัด — เก็บ Phase A v2 + old logs เข้า `HANDOFF_ARCHIVE.md`, main เก็บ pointer | ตอนนี้ ~620 บรรทัด — onboarding cost เพิ่มตาม session ใหม่ | Coddy #2 (proactive) |
| P3.3 | **Task-type detection → dynamic CONTEXT_MAP** — เกม vs CRUD vs data pipeline ต้องการ weight ต่างกัน | CONTEXT_MAP ปัจจุบัน static — premature abstraction ถ้าทำตอนนี้ | Coddy #2 (future) |
| P3.4 | **Coder pass-1 file ZIP duplicate** — `04a_coder_pass1.md` กับ `04_coder.md` confuse user | Coddy #1 ตัดสินใจไม่แก้ — รอ feedback จริง | Coddy #1 |
| P3.5 | **Codebase complexity refactor** — pipeline.py 870 lines, future strategy pattern | Coddy #1 กังวล, Coddy #2 ว่าไม่ใช่ปัญหาตอนนี้ (Nick ≠ maintainer) | Coddy #1 (deprioritized per #2) |

---

### 💎 Key Insights from Multi-Perspective (สำหรับ session ต่อไป)

1. **Multi-Coddy pattern works** — Coddy #2 catch **5 blind spots** ของ Coddy #1 (insider) แม้ไม่ได้แตะโค้ดเลย. Pattern นี้ valuable มาก ต้องเก็บไว้
2. **Coddy #2 trust caveat** — เขา flag ตัวเองว่า "armchair analysis, weight ต่ำกว่า Coddy #1 ใน deep technical". ถ้า advice ขัด ground reality → trust Coddy #1
3. **Honest pushback is valued** — Coddy #1 push back 3 ครั้งใน session, Nick respond ดีมาก. **All 