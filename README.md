# 🤖 HAPPY / AI Agent

> Multi-Agent AI orchestrator — ใส่โจทย์ → AI 11/18 ตัวประชุมกัน → ได้โค้ดที่รันได้ทันที

ระบบให้ AI Gemini หลายตัวทำงานต่อเนื่องกันเป็น "ทีม" (PM → Architect → Coder → Frontend → Tester → Debugger → Judge → DevOps → ...) เพื่อสร้างโครงงานตามโจทย์ที่พิมพ์เข้ามา. UI เป็น Streamlit web app เปิดในเบราว์เซอร์

---

## ✨ Features หลัก

- 🎨 **UI สวย ใช้งานง่าย** — Streamlit + theme ส้ม-ชมพู
- 🤖 **2 โหมด**: **Quick** (11 phases, ~15-25 นาที) / **Thorough** (18 phases, +Kickoff meeting 7 agents)
- ⚖️ **3 quality gates**: Tester (runnable?) → Debugger (clean?) → Judge (score?)
- 🔄 **Auto revision loops** — ถ้า Tester บอก BROKEN หรือ Judge < threshold → loop กลับ Coder แก้
- 💾 **Save per-phase** — phase พังกลางทาง output ที่ทำไปแล้วยังอยู่
- 📜 **Session history** — เก็บทุก session ที่เคยรัน, click กลับมาดูได้
- 🔐 **Gemini API key** (AI Studio, ฟรี) — paste key 1 ครั้ง → save ที่ `~/.happy/auth.json`
- 📊 **Token monitoring** — แสดง peak/avg/total tokens ใน UI หลังจบ
- 🛡️ **TPM watcher** — adaptive throttle กัน rate limit
- 📤 **Export** — TXT report / Code ZIP / All-in-one ZIP
- 🔨 **Build .exe** — Python project + Web project (HTML/JS via pywebview wrapper)
- 🛑 **Stop button** — หยุด pipeline กลางคันได้ (กัน orphan thread)

---

## 🚀 ติดตั้ง (Windows)

### 1. ติดตั้ง Python

ต้องใช้ **Python 3.10+** (แนะนำ 3.13). ถ้ายังไม่มี → ดาวน์โหลดที่ https://www.python.org/downloads/

ตรวจสอบ:
```powershell
python --version
```

### 2. แตกไฟล์ + เข้าโฟลเดอร์

```powershell
cd $env:USERPROFILE\Desktop
# (extract ZIP ที่นี่)
cd happy-ai-agent
```

### 3. ติดตั้ง dependencies

```powershell
python -m pip install -r requirements.txt
```

หลัก: `streamlit`, `google-genai`, `pygments`. ลงประมาณ 30 วินาที

### 4. ขอ Gemini API key (ฟรี)

1. ไปที่ https://aistudio.google.com/apikey
2. Login ด้วย Google account
3. กด **"+ Create API key"** → เลือก project ใหม่ก็ได้
4. **Copy** key (ขึ้นต้นด้วย `AIza...`, ยาว 39 ตัว)

### 5. รันแอป

```powershell
python -m streamlit run app.py --server.port=8501
```

→ เปิดเบราว์เซอร์ไปที่ **http://localhost:8501**

ครั้งแรก: ไป ⚙️ Settings → paste API key → กด "💾 บันทึก & เชื่อมต่อ"

---

## 📖 วิธีใช้

1. **Home** — พิมพ์โจทย์ เช่น:
   - `เขียน Python function บวกเลข 2 ตัว มี docstring + 3 test cases`
   - `สร้างเกม Snake ด้วย HTML/JS canvas — ใช้คีย์ลูกศรควบคุม`
   - `เครื่องคิดเลข HTML แบบ single file`

2. **เลือก mode**:
   - **Quick** — 11 agents, ~15-25 นาที (งานทั่วไป)
   - **Thorough** — 18 agents (+ Kickoff meeting วิเคราะห์ละเอียด), ~30-40 นาที (งานคุณภาพสูง / ใส่ไฟล์อ้างอิงได้)

3. **กด ▶️ ให้น้องช่วยทำ!** → ดู progress real-time

4. **เสร็จ** → ดู output ของแต่ละ agent (คลิกชื่อ agent ทางซ้าย) → ดาวน์โหลด TXT / ZIP / Build .exe

---

## ⚙️ Settings สำคัญ

| Setting | Default | คำอธิบาย |
|---------|---------|---------|
| 🤖 **Model** | `gemini-3.1-flash-lite-preview` | Flash Lite ฟรี + RPD 500/day |
| ⏱ **Delay** | 45 วินาที | พักระหว่าง agent (กัน TPM hit) — ห้ามต่ำกว่า 30s |
| ⚖️ **Judge Threshold** | 100/100 | คะแนนผ่านขั้นต่ำ (เข้มสุด = 100) |
| 🔁 **Max Judge Loops** | 5 | จำนวนรอบ revise สูงสุด |
| 🎯 **Pipeline Mode** | Quick | Quick (11) / Thorough (18) |

---

## 🤖 ลำดับ Agent (Quick mode = 11 phases)

```
1. 📋 PM Kickoff        → วางแผนภาพรวม
2. 🏗️ Architect         → ออกแบบระบบ + API contracts
3. 🗄️ DB Admin          → schema (ถ้าต้องใช้ DB)
4. 💻 Coder              → backend code (มี pass 1 + pass 2 critique)
5. 🎨 Frontend Dev       → UI code
6. 🧪 Tester             → "เล่นจริง" simulate — ถ้า BROKEN ส่งกลับ Coder revise
7. 🔍 Debugger           → review + แก้ bugs
8. ⚖️ Judge              → ให้คะแนน 0-100 — ถ้า < threshold ส่งกลับแก้
9. 🚀 DevOps             → คำแนะนำ deploy
10. 📝 Summarizer         → เอกสารสรุป
11. ✅ PM Final           → รายงานสุดท้าย
```

**Thorough mode** เพิ่ม 7 phases ก่อนเริ่ม: Document Analyst → Requirements → Architect Consult → UX Lead → Data Lead → Security Lead → Brief Synthesizer

---

## 📁 โครงสร้างไฟล์

```
happy-ai-agent/
├── app.py              ← Streamlit UI (Settings, Home, Running, Done pages)
├── pipeline.py         ← PipelineRunner — orchestrator + retry + TPM watcher
├── agents.py           ← Prompts ของ 17 agents + CONTEXT_MAP
├── auth.py             ← Gemini API key authentication
├── builder.py          ← Build .exe ผ่าน PyInstaller (Python + Web)
├── extractor.py        ← แยก code blocks → ไฟล์
├── file_loader.py      ← Multimodal attachments (image/pdf/word/excel)
├── happy_desktop.py    ← pywebview wrapper (optional desktop mode)
├── HAPPY.spec          ← PyInstaller spec
├── requirements.txt
├── .streamlit/         ← theme config
├── assets/             ← logos
└── sessions/           ← user data (auto-created)
```

---

## 🛠️ Testing scripts (ให้ tester verify)

หลังติดตั้ง รันได้:

```powershell
# Quick health check — syntax + imports + key functions (no API call)
python qa_final.py

# Real e2e backend test — ต้องมี API key set แล้ว, ใช้ quota ~12 API calls (~$0.02)
python test_pipeline_e2e.py
```

---

## 🐛 Troubleshooting

**"ยังไม่ได้เชื่อมต่อ"**
→ ไป ⚙️ Settings → paste API key. ถ้า key ผิด: ลองสร้างใหม่ที่ aistudio.google.com/apikey

**"429 / rate limit"**
→ Settings → เพิ่ม delay เป็น 60+ วินาที. หรือเปลี่ยน model เป็น `gemini-2.5-flash-lite` (RPD 1,000)

**"Pipeline ผิดพลาด: empty response"**
→ Model ส่ง empty (อาจเพราะ safety filter). ระบบ retry 3 ครั้งอัตโนมัติ. ถ้ายังพัง → ลดความซับซ้อนของโจทย์

**Sidebar collapsed แล้วเปิดกลับไม่ได้**
→ ปุ่ม `>>` มุมบนซ้าย (เปลี่ยน CSS แล้วใน Phase A)

**โปรแกรมหน่วงระหว่างรัน**
→ ปกติ — Streamlit rerun ทุก 2 วินาที + cumulative context input ใหญ่. ลด delay หรือเปลี่ยน model ตัวเล็ก

**Build .exe fail**
→ ต้องลง PyInstaller เพิ่ม: `pip install pyinstaller pywebview`. ระบบจะ auto-install ตอนกดปุ่มครั้งแรก

---

## 📊 Quota (Gemini Free tier — gemini-3.1-flash-lite-preview)

| Limit | Value |
|---|---|
| Input token limit | 1,048,576 / request |
| Output token limit | 65,536 / request |
| RPM (requests/นาที) | 15 |
| TPM (tokens/นาที) | 250,000 |
| RPD (requests/วัน) | 500 |

→ 1 session Quick mode = ~15-25 API calls → **รัน ~20-30 sessions/วัน ได้สบาย**

---

## 🎯 Test scenarios (สำหรับเทส)

แนะนำให้ลองทดสอบ:

1. **Simple Python**: `เขียน Python function บวกเลข 2 ตัว มี docstring + 3 test cases`
2. **Web game**: `สร้างเกม Snake ด้วย HTML/JS canvas — ใช้คีย์ลูกศรควบคุม`
3. **HTML calculator**: `เครื่องคิดเลขแบบ single file HTML+CSS+JS ปุ่ม 0-9, +, -, *, /, =, C`
4. **GUI app**: `Password generator ด้วย Python tkinter — slider, checkbox, copy button`
5. **Stop test**: รัน task แล้วกด 🛑 ใน sidebar — pipeline ควรหยุด + status เป็น "stopped"
6. **Download test**: เสร็จ → กดดาวน์โหลด TXT/ZIP — ไฟล์ใน Downloads ปกติ
7. **Build .exe**: ใน Done page กด "🔨 Build .exe" — สำหรับ Python project → ได้ .exe runnable

---

## 📝 Bug reports

ถ้าเจอบัค ส่งกลับมาพร้อม:
- Screenshot
- Browser console error (ถ้ามี)
- `sessions/<session_id>/_meta.json` (มี token_stats + error log)
- `sessions/<session_id>/errors.log` (ถ้ามี)

---

## 🛡️ Privacy & Security

- API key อยู่ที่ `~/.happy/auth.json` (เฉพาะเครื่องของคุณ — ไม่ส่งไปไหน)
- Session output อยู่ใน `sessions/` (local เท่านั้น)
- ไม่มี telemetry / tracking
- `.gitignore` กัน commit credentials

---

🤖 Made with ❤️ — สำหรับคนที่อยากให้ AI หลายตัวทำงานร่วมกันสร้างโค้ดจริง
