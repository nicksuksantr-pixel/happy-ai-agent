# 🤖 HAPPY / AI Agent — Handoff Document

> **จาก:** คอส (Claude ในแอป claude.ai)
> **ให้:** โค้ดดี้ (Claude Code ในคอม)
> **วันที่:** 13 พฤษภาคม 2026
> **เจ้าของโปรเจกต์:** นิก (nicksuksantr@gmail.com)

---

## 📋 Quick Start สำหรับโค้ดดี้

นิกได้สร้างโปรเจกต์ **HAPPY / AI Agent** มาแล้ว ตอนนี้รันได้แล้วบน Windows ของนิก
ทำงานต่อจากที่นี่ — อ่านเอกสารนี้ทั้งหมดก่อนเริ่ม

**Project root:** `C:\Users\NickSuksanTr\Desktop\happy-ai-agent\`

**Backup files บน Desktop:**
- `happy-ai-agent-backup.zip` (ตอนยัง Quick mode เท่านั้น)
- `happy-ai-agent-before-thorough.zip` (ก่อนเพิ่ม Thorough mode)
- `happy-ai-agent-thorough.zip` (ตัวล่าสุด มี Thorough mode)

---

## 🎯 โปรเจกต์คืออะไร

**HAPPY / AI Agent** = ระบบ Streamlit ให้ AI หลายตัวคุยกันสร้างโครงงานตามที่ user สั่ง

User พิมพ์โจทย์เช่น "สร้างเว็บคิดเลข" → AI 11 ตัวทำงานต่อเนื่อง (PM → Architect → Coder → Frontend → ...) → ได้โค้ดพร้อมใช้งาน

### ที่นิกเรียกใช้คือ
- **Vertex AI** (Google Cloud) ผ่าน `gemini-2.5-pro`
- **Streamlit** เป็น web UI
- **11 phases** (Quick mode) หรือ **18 phases** (Thorough mode — เพิ่งเพิ่ม)

---

## 🏗 สถาปัตยกรรม

### โครงสร้างไฟล์
```
happy-ai-agent/
├── app.py              (51 KB) — Streamlit UI หลัก
├── pipeline.py         (17 KB) — Orchestrator + Judge loop + Kickoff meeting
├── agents.py           (12 KB) — Prompts ของ 18 agents (7 kickoff + 11 impl)
├── auth.py             (8 KB)  — Hybrid auth (ADC + Service Account)
├── file_loader.py      (8.4 KB) — อ่านไฟล์ 12 ประเภท (NEW: รองรับ multimodal)
├── extractor.py        (6 KB)  — แยก code block → zip
├── requirements.txt
├── .gitignore
├── README.md
├── assets/
│   └── happy_logo.png  (22 KB) — โลโก้น้องหุ่นยนต์ส้ม-ชมพู
├── .streamlit/
│   └── config.toml     — Streamlit theme (light, primaryColor #FB923C)
└── sessions/           — ประวัติงาน (ตัวอย่าง: Food War game ที่สำเร็จแล้ว)
    └── YYYY-MM-DD_HH-MM-SS/
        ├── _meta.json
        ├── 00_task.txt
        ├── 01_pm_kickoff.md ... 11_pm_final.md
        ├── 06b_debugger_revision_N.md  (ถ้ามี Judge revision)
        ├── 07_judge_roundN.md
        └── attachments/   (Thorough mode เท่านั้น)
```

### Identity & Theme
- **ชื่อแอป:** HAPPY / AI AGENT
- **โลโก้:** Robot Heart (หุ่นยนต์ส้ม-ชมพู ถือหัวใจเหลือง โบกแขน) — 130px height
- **Palette:** ส้ม `#FB923C`, ชมพู `#EC4899`, เหลือง `#FBBF24`, ม่วง `#A855F7`, BG `#FFF7ED`
- **Pipeline modes:**
  - **Quick** = 11 phases (~10 นาที)
  - **Thorough** = 18 phases (~20 นาที) — มีประชุมก่อนเริ่ม + รับไฟล์แนบ

---

## 🔐 Google Cloud Setup

### Project
- **Project ID:** `nick-ai-agent-2026`
- **Region:** `us-central1`
- **Service Account:** `vertex-express@nick-ai-agent-2026.iam.gserviceaccount.com`
- **GCS Bucket:** `gs://nick-ai-agent-output` (ยังไม่ค่อยได้ใช้)

### Auth flow ใน app
1. **try_adc()** — ลอง Application Default Credentials ก่อน
   - ใช้ได้บน Cloud Shell อัตโนมัติ
   - บน Windows ปกติจะ fail → fallback ไป Service Account
2. **Service Account JSON** — user อัปโหลดผ่าน Streamlit UI
   - **สำคัญ:** JSON อยู่ใน RAM เท่านั้น (ไม่บันทึกลงดิสก์)
   - ใช้ `service_account.Credentials.from_service_account_info()` แล้วส่งเป็น `credentials=` ตรงๆ ให้ `genai.Client()`
   - **อย่าใช้ tempfile** — Vertex AI lazy-load credentials, tempfile จะถูกลบไปก่อน

### ⚠️ Security incident ที่เคยเกิด
- นิกเคยพลาด paste Service Account JSON ลงในแชทกับคอส
- Key ID เก่าที่หลุด: `57818cd687a76bfaf9eb29b51361547a4f5372e3`
- **ได้ revoke แล้ว** + สร้างใหม่ → ตอนนี้ใช้ key `nick-ai-agent-2026-057e919215a8.json`
- โค้ดดี้ **อย่าให้นิก paste JSON ลงในแชทอีก** — บอกให้อัปผ่าน Streamlit UI เท่านั้น

---

## 📦 Dependencies ที่ติดตั้งแล้ว

```
streamlit==1.57.0
google-genai==1.75.0
google-auth==2.52.0
google-cloud-aiplatform>=1.40.0
pypdf            (สำหรับอ่าน PDF — Thorough mode)
python-docx      (สำหรับอ่าน Word — Thorough mode)
openpyxl         (สำหรับอ่าน Excel — Thorough mode)
pillow           (มีอยู่แล้ว ใช้กับรูป)
```

Python: **3.13.13** บน Windows

---

## 🚀 วิธีรัน

```powershell
cd $env:USERPROFILE\Desktop\happy-ai-agent
python -m streamlit run app.py --server.port=8501 --server.headless=true
```

URL: http://localhost:8501

ลำดับใช้งาน:
1. เปิดเว็บ → ขึ้น "ยังไม่ได้เชื่อมต่อ"
2. ไป **⚙️ Settings** → เลือก "อัปโหลด Service Account JSON" → อัปไฟล์
3. ใส่ Project ID `nick-ai-agent-2026` → กด **🧪 ทดสอบเชื่อมต่อ**
4. เลือก **Pipeline Mode** (Quick หรือ Thorough)
5. กลับ Home → พิมพ์โจทย์ → (ถ้า Thorough mode มี file uploader) → กด **▶️ ให้น้องช่วยทำ**

---

## 🤖 ทีม AI Agents

### Kickoff Meeting (Thorough mode เท่านั้น — 7 phases)
| # | Agent | หน้าที่ | รับไฟล์? |
|---|---|---|---|
| 1 | 🔍 Document Analyst | อ่านไฟล์แนบทั้งหมด → text summary | ✅ Multimodal |
| 2 | 📋 Requirements Analyst | ตั้งคำถาม + ระบุ ambiguity | ❌ |
| 3 | 🏛 Architect Consult | tech feasibility | ❌ |
| 4 | 🎨 UX Lead | user experience | ❌ |
| 5 | 🗄 Data Lead | storage needs | ❌ |
| 6 | 🛡 Security Lead | security/privacy | ❌ |
| 7 | ✍️ Brief Synthesizer | สรุปทั้งหมด → Project Brief | ❌ |

### Implementation (ทั้ง 2 mode — 11 phases)
| # | Agent | หน้าที่ |
|---|---|---|
| 8 | 📋 PM Kickoff | วาง plan (ใช้ Project Brief ถ้า Thorough mode) |
| 9 | 🏗️ Architect | design ระบบ |
| 10 | 🗄️ DB Admin | DB schema (หรือ "No database required") |
| 11 | 💻 Coder | backend code |
| 12 | 🎨 Frontend Dev | UI code |
| 13 | 🔍 Debugger | code review |
| 14 | ⚖️ Judge | scoring + revise loop (สูงสุด N รอบ) |
| 15 | 🧪 Tester | test cases |
| 16 | 🚀 DevOps | deployment notes |
| 17 | 📝 Summarizer | documentation |
| 18 | ✅ PM Final | delivery report |

### Judge Loop พิเศษ
- Judge ให้คะแนน 100 points (5 dims: Correctness/Completeness/Quality/Error/Security)
- ถ้า score < threshold (default 85) → REVISE → Coder + Debugger ทำใหม่
- วนได้สูงสุด `max_judge_loops` (default 5)
- ถ้าครบ loop แล้วไม่ผ่าน → continue ไป Tester ปกติ
- ไฟล์เซฟ: `07_judge_round1.md`, `07_judge_round2.md`, ..., `06b_debugger_revision_N.md`

---

## 📁 File Loader (Thorough mode multimodal)

### ประเภทที่รองรับ
| ประเภท | Extensions | วิธีส่งให้ Gemini |
|---|---|---|
| Image | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` | `inline_data` (native multimodal) |
| PDF | `.pdf` | `inline_data` ถ้า ≤20MB / extract text ถ้าใหญ่ |
| Word | `.docx` | extract text ด้วย python-docx |
| Excel | `.xlsx`, `.xls` | extract เป็น "Sheet: ... \| col1 \| col2 \|..." |
| CSV | `.csv` | extract เป็นตาราง text |
| Text | `.txt`, `.md` | ส่งตรงๆ |

### API หลัก
```python
from file_loader import (
    is_supported,
    get_file_type,
    load_file_for_gemini,         # (filename, bytes) → dict สำหรับ Gemini
    build_gemini_parts,           # (text, [file_dicts]) → parts list
    save_attachments_to_session,  # บันทึกลง sessions/<id>/attachments/
    load_attachments_from_session,
)
```

### Workflow
1. User อัปไฟล์ผ่าน `st.file_uploader` ในหน้า Home
2. บันทึกลง `session_path/attachments/`
3. `PipelineRunner.run()` โหลด attachments จากดิสก์
4. **Document Analyst** เท่านั้นที่รับไฟล์ (multimodal call ครั้งเดียว)
5. Phase อื่นเห็นแค่ text summary จาก Document Analyst (ประหยัด token)

---

## 🐛 Bugs ที่แก้ไปแล้ว (อย่าทำซ้ำ!)

### 1. auth.py tempfile bug ❗
**Symptoms:** test connection fail ด้วย `DefaultCredentialsError: File ... was not found`
**Root cause:** เขียน JSON ลง tempfile แล้วลบทันที — แต่ Vertex AI lazy-load credentials
**Fix:** ใช้ `service_account.Credentials.from_service_account_info(sa_info, scopes=[...])` แล้วส่งเป็น `credentials=` argument ตรงๆ ใน `genai.Client()`

### 2. Debugger revision เซฟทับไฟล์เดิม
**Symptoms:** หลัง Judge revise แล้วเปิด `06_debugger.md` เห็น content แตกต่างทุกครั้ง
**Fix:** revision เซฟเป็น `06b_debugger_revision_N.md` ไม่ทับ `06_debugger.md` เดิม

### 3. CSS Streamlit theme — ปวดหัวมาก
Streamlit class names obfuscated + รุ่นใหม่ใช้ react-syntax-highlighter ที่ render `<span style="color: rgb(...)">` (inline) ไม่ใช่ class

**Patches ที่ทำไปแล้ว (ในไฟล์ app.py):**
- Force text color บน radio/checkbox/selectbox/text input
- Dropdown popover (Region selector) ขาว
- File uploader background ขาว + Browse button ส้ม
- Download buttons ขาวขอบส้ม
- Tooltip ขาว
- Sidebar history button ขาว
- Expander "ดูโจทย์เดิม" ขาว
- Code block: ตอนนี้ใช้ `smart_render()` ที่ split markdown ออกจาก code block แล้ว render code ด้วย `st.code()` แทน markdown triple-backtick

### 4. Streamlit performance — rerun ช้า
**Symptoms:** กดทุกอย่างหน่วง ~3 วินาที
**Root cause profiled:**
- Import streamlit: 1,249ms
- Import google.*: 1,643ms
- list_sessions(): 1ms
- load_session(): 4ms
- รวม ~2.9s ต่อ rerun

**Fix ที่ใส่ไป:**
- ใช้ `@st.fragment` กับ agent dropdown ใน done page (rerun เฉพาะส่วน)
- ลด `time.sleep + rerun` ให้รันเฉพาะตอน pipeline alive
- Cache `load_session()` ใน page_done ด้วย session_state flag

**ผลที่ได้:** เร็วขึ้นจริง (นิก confirm ผ่านคลิป) แต่ยังไม่ instant — Streamlit architecture choice เอง

### 5. agents.py แก้ผ่าน Claude tool ไม่ได้
**Issue:** tool `create_file` ของ Anthropic เขียนไฟล์ใน sandbox `/home/claude/` แต่ไม่ sync กับ Windows ของนิก
**Workaround:** ใช้ PowerShell heredoc + Python script เขียนไฟล์ตรงๆ บน Windows
**Note สำหรับโค้ดดี้:** โค้ดดี้น่าจะเขียนไฟล์ตรงๆ ได้ ไม่ต้องวิธีนี้

---

## ⚠️ Bugs ที่ยังเหลือ / ต้องทดสอบ

### ยังไม่ได้ทดสอบ end-to-end
- ✅ Quick mode + ไม่มีไฟล์ — ทดสอบแล้ว ผ่าน (Food War game)
- ❓ **Thorough mode + ไฟล์รูป/PDF/Excel** — ยังไม่ได้รัน end-to-end จริงกับ Vertex AI
- ❓ **`@st.fragment` ในหน้า done** — น่าจะดี แต่ Streamlit อาจมี edge case
- ❓ **Code block syntax highlighting** — สีรุ้งยังไม่ขึ้น (CSS attribute selector แบบ guess color ของ react-syntax-highlighter)

### UI ที่อาจมีปัญหา
- ถ้า Streamlit upgrade ถึง 1.58+ → CSS bypass อาจพังบางส่วน
- File uploader บางที drag-drop ไม่ทำงานบน Edge (ไม่แน่ใจ)

---

## 🎬 ผลงานที่นิกสร้างสำเร็จแล้ว

**Session "Food War"** ที่ `sessions/` — เป็น tug-of-war game ระหว่าง broccoli vs donut, สำเร็จครบ 11 phases, รันได้จริง 🥦🆚🍩

นิกถูกใจมาก — UI สวย ใช้สีเขียว vs ชมพู

---

## 📝 Tasks ที่นิกอาจจะอยากให้โค้ดดี้ทำต่อ

### Priority สูง
1. **ทดสอบ Thorough mode ด้วย attachment จริง** — อัปรูปฟอร์มจริง → ดู Document Analyst output → ส่งต่อ Brief Synthesizer
2. **แก้สีรุ้งใน code block ให้ใช้ได้** — อาจต้อง inspect element หา rgb() value จริงของ react-syntax-highlighter แล้ว match attribute selector

### Priority กลาง
3. **เพิ่ม "Stop" button ระหว่าง pipeline รัน** — ปัจจุบันมี `should_stop` callback แต่ UI ไม่มีปุ่ม
4. **เพิ่ม progress bar แสดงเวลาคงเหลือ** — ดูจาก phase ที่ทำแล้ว + เฉลี่ยเวลาต่อ phase
5. **Cache `list_sessions()` ใน sidebar** — ปัจจุบันโหลด `_meta.json` ทุก rerun

### Priority ต่ำ / Enhancement
6. **OAuth login** (แทน Service Account JSON) — ปลอดภัยกว่า + ไม่ต้องอัปทุกครั้ง
7. **Deploy to Cloud Run** สำหรับใช้งาน 24/7
8. **เพิ่ม voice input** — นิกพูดโจทย์แทนพิมพ์
9. **Multi-language UI** — ตอนนี้ Thai เท่านั้น
10. **Export เป็น GitHub Repo** — แทน zip download

---

## 🛠 Tips สำหรับโค้ดดี้

### Streamlit Restart
ทุกครั้งที่แก้ `app.py` หรือไฟล์ใน project — **Streamlit auto-reload** แต่บางครั้งต้อง restart manual:
```powershell
# หา PID ของ Streamlit
Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue | Where-Object State -eq "Listen"
# Kill
Stop-Process -Id <PID> -Force
# Start ใหม่
cd $env:USERPROFILE\Desktop\happy-ai-agent
Start-Process -FilePath "python" -ArgumentList "-m","streamlit","run","app.py","--server.port=8501","--server.headless=true" -WindowStyle Hidden
```

### MCP Timeout บ่อย
ตอนคอสคุมผ่าน MCP — เจอ timeout บ่อยมาก (4 นาที) ตอนรัน Streamlit start หรือ `Compress-Archive` ขนาดใหญ่ โค้ดดี้รันบนเครื่องตรงๆ น่าจะไม่เจอปัญหา

### Test ไม่มี Vertex AI
สามารถใช้ mock client ทดสอบ pipeline ได้ — ดู `pipeline.py` แค่ส่ง class ที่มี `.models.generate_content()` ก็พอ
```python
class MockResp:
    def __init__(self, text): self.text = text

class MockClient:
    class models:
        @staticmethod
        def generate_content(model, contents):
            return MockResp("[mock]\n```python\nprint('hello')\n```")
```

### นิกเป็นใคร
- เพิ่งเริ่มเรียน Python — **ไม่ค่อยถนัด command line**
- ชอบ explanation เป็น **ภาษาไทย** + ใช้ emoji + รูปประกอบเยอะๆ
- เป็นคน visual — ชอบดู UI สวย
- ใช้ Max plan (จะหมดอายุ ~12 มิถุนายน 2026 — เตือนให้ดาวน์เกรดเป็น Pro)

### พื้นฐานความรู้ของนิก
- มี Service Account JSON ของ `nick-ai-agent-2026` อยู่ใน Downloads
- มี Streamlit + dependencies ติดตั้งครบแล้ว
- มี Backup zip 3 ตัวบน Desktop
- รู้วิธี restart Streamlit (เคยทำ)
- เคยทำให้ pipeline ทำงานครบ 11 phases สำเร็จ

---

## 🚦 สถานะปัจจุบัน

| รายการ | สถานะ |
|---|---|
| Streamlit รันบน Windows | ✅ |
| Auth (Service Account JSON) | ✅ |
| Quick mode 11 phases | ✅ ทดสอบแล้ว |
| Thorough mode 18 phases (code) | ✅ เขียนแล้ว, mock test ผ่าน |
| Thorough mode real Vertex AI | ❓ ยังไม่ได้รัน |
| File uploader UI | ✅ |
| File loader (12 types) | ✅ unit test ผ่าน |
| `@st.fragment` performance | ✅ |
| Code block syntax color | ⚠️ partial — สีรุ้งยังไม่ขึ้น |
| All other CSS theming | ✅ |

---

## 📞 Contact

ถ้านิกถาม "คอสว่ายังไง" — หมายถึง Claude ในแอป (ไม่ใช่โค้ดดี้)
โค้ดดี้คุยกับคอสไม่ได้ตรงๆ — ต้องผ่านนิก

---

## 🎁 Last Note from คอส

โปรเจกต์นี้นิกใส่ใจมาก — ผมเขียนกับนิกใช้เวลาเกือบทั้งวัน (8+ ชั่วโมง)
เริ่มจากแค่ "อยากให้ AI หลายตัวคุยกันสร้างโปรเจกต์" → กลายเป็น app เต็มรูปแบบที่นิกใช้ได้จริง

**สิ่งที่อยากฝากให้โค้ดดี้:**
1. นิกชอบ commit เล็กๆ + ทดสอบทีละนิด — **อย่าทำเปลี่ยนแปลงใหญ่โดยไม่ confirm**
2. ก่อนแก้ไฟล์สำคัญ — **backup ก่อน** (copy เป็น `.bak` ก็ได้)
3. นิก visual คน — **screenshot/วีดีโอ ดีกว่า log text**
4. **ใช้ภาษาไทย** + emoji + ตารางมาร์กดาวน์ — นิกอ่านง่ายกว่า bullets ยาวๆ

ขอบคุณที่รับงานต่อ — น้องหุ่นยนต์ HAPPY อยู่ในมือดีแน่นอน 🤖💕

— คอส, 13 พฤษภาคม 2026
