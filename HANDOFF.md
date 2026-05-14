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

**Ready for handoff to Workie 🤝**
