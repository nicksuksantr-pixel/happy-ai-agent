# 🤖 Happy AI Agent

> Multi-Agent AI orchestrator — ใส่โจทย์ → AI 11/18 ตัวประชุมกัน → ได้โค้ดที่รันได้ทันที

ระบบให้ Gemini หลายตัวทำงานต่อเนื่องเป็น "ทีม" (PM → Architect → Coder → Frontend → Tester → Debugger → Judge → DevOps → ...) เพื่อสร้างโครงงานตามโจทย์ที่พิมพ์เข้ามา

UI เป็น **native desktop** ตั้งแต่ v2.0 (CustomTkinter, ไม่มี web server, ไม่ชนพอร์ตกับแอปอื่น)

---

## ✨ Features

- 🎨 **UI native** — CustomTkinter, theme ส้ม-ชมพู, ไม่ต้องเปิด browser
- 🤖 **2 โหมด**: **Quick** (11 phases, ~15-25 นาที) / **Thorough** (18 phases + Kickoff meeting 7 agents)
- ⚖️ **3 quality gates**: Tester (runnable?) → Debugger (clean?) → Judge (score?)
- 🔄 **Auto revision loops** — ถ้า Tester บอก BROKEN หรือ Judge < threshold → loop กลับ Coder แก้
- 💾 **Save per-phase** — phase พังกลางทาง output ที่ทำไปแล้วยังอยู่
- 📜 **Session history** — เก็บทุก session ที่เคยรัน, คลิกกลับมาดูได้
- 🔐 **Gemini API key** (AI Studio, ฟรี) — paste key 1 ครั้ง → save ที่ `~/.happy/auth.json`
- 🛡️ **TPM watcher** — adaptive throttle กัน rate limit
- 📤 **Export** — TXT report / Code ZIP / All-in-one ZIP
- 🔨 **Build .exe** — Python project + Web project (HTML/JS via pywebview wrapper)
- 🛑 **Stop button** — หยุด pipeline กลางคันได้
- 🔄 **Auto-updater** — เช็ค GitHub Releases ทุกครั้งที่เปิดแอป

---

## 🚀 ติดตั้ง (สำหรับคนทั่วไป)

1. ดาวน์โหลด `HappyAIAgent-Setup.zip` จาก [Releases](https://github.com/nicksuksantr-pixel/happy-ai-agent/releases)
2. แตก zip → เข้าโฟลเดอร์ `HappyAIAgent-Setup/`
3. รัน `HappyAIAgent-Setup.exe`
4. ระหว่าง install — paste Gemini API key (ขอฟรีที่ https://aistudio.google.com/apikey)
5. เปิดแอปจาก Start Menu / Desktop shortcut

---

## 🔨 พัฒนา (developer mode)

### ติดตั้ง Python + deps

```powershell
# Python 3.10+ (แนะนำ 3.13)
python -m pip install -r requirements.txt
```

### รัน dev mode

```powershell
python happy_native.py
```

### Build .exe + installer

```powershell
# 1. Build main app
pyinstaller HappyAIAgent.spec --noconfirm --clean
# → dist/HappyAIAgent/HappyAIAgent.exe

# 2. Build installer
python installer/build_installer.py
# → dist/HappyAIAgent-Setup/HappyAIAgent-Setup.exe
# → dist/HappyAIAgent-Setup.zip  (พร้อมแจก)
```

---

## 📂 โครงสร้างไฟล์

```
happy_native.py              ← Native CTk UI
pipeline.py                  ← Pipeline orchestrator
agents.py                    ← 18 agent roles (11 impl + 7 kickoff)
auth.py                      ← Gemini API auth
builder.py                   ← Build user code → .exe
extractor.py                 ← Split code blocks
file_loader.py               ← Multimodal attachments
updater.py                   ← GitHub Releases auto-update
VERSION                      ← Version single source of truth
HappyAIAgent.spec            ← PyInstaller spec
installer/installer.py       ← Custom installer (dark cosmic UI)
installer/build_installer.py ← Build pipeline
assets/                      ← Logo + icons
sessions/                    ← User outputs (gitignored)
```

---

## 🔧 Configuration

- **API key**: `~/.happy/auth.json`
- **Settings**: `~/.happy/settings.json` (model, delay, judge threshold, mode)
- **Sessions**: `~/.happy/sessions/`
- **Crash log**: `~/.happy/crash.log`
- **Updater log**: `%TEMP%/happy-ai-agent-updater.log`

---

## 🧪 Test commands

```powershell
# Unit + integration suite (no API calls)
python -m pytest -q

# Headless end-to-end AI tester (reads ~/.happy/auth.json)
python tools/test_ai_pipeline.py                      # connectivity only (~2 calls)
python tools/test_ai_pipeline.py --quick "<task>"     # full Quick pipeline (11 phases)
# bounded/fast run (lower delay + judge threshold + loops):
python tools/test_ai_pipeline.py --quick "<task>" --delay 6 --judge 80 --loops 2 --project-type html
```

---

## 📜 License

Personal use license. See `LICENSE` (built into installer).

🤖 สร้างด้วย ♥ โดย Nick & Codey (Happy AI Family)
