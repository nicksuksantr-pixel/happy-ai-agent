# 🤖 HAPPY / AI Agent

> Multi-Agent AI Pipeline ที่มี UI สวยๆ — ใช้งานง่าย ดูสถานะ agent เรียลไทม์

ระบบให้ AI หลายตัวทำงานร่วมกัน (PM → Architect → Coder → Frontend → Judge → Tester → DevOps → ...) เพื่อสร้างโครงงานตามโจทย์ที่ผู้ใช้พิมพ์

## ✨ Features

- 🎨 UI สดใส น่ารัก ใช้งานง่าย (Streamlit)
- 🤖 11 phases ของ AI agents ทำงานต่อกัน
- ⚖️ Judge loop — วน revise โค้ดจนผ่านเกณฑ์
- 💾 เซฟไฟล์แยกตาม phase (พังกลางทางไม่หาย)
- 📜 เก็บประวัติ session
- 🔐 Hybrid auth — ADC + Service Account JSON
- 🔧 ปรับ model, delay, threshold ได้ใน Settings
- 📤 Export TXT / Code zip / All-in-one zip

---

## 🚀 ติดตั้ง

### 1. แตกไฟล์และเข้าโฟลเดอร์

```bash
cd ~
unzip happy-ai-agent.zip
cd happy-ai-agent
```

### 2. ติดตั้ง dependencies

```bash
pip install -r requirements.txt --break-system-packages
```

### 3. เปิดใช้งาน

```bash
streamlit run app.py --server.port=8080
```

### 4. เปิดเว็บ

- ใน **Cloud Shell** — กดปุ่ม **Web Preview** (👁️ มุมขวาบน) → **Preview on port 8080**
- ใน **local** — เปิด browser ไปที่ `http://localhost:8080`

---

## 📖 วิธีใช้

1. เปิดเว็บแล้วระบบจะเช็คเชื่อมต่อ Google Cloud อัตโนมัติ
   - ถ้าใช้ Cloud Shell → ใช้ ADC อัตโนมัติ
   - ถ้ารัน local → ไป ⚙️ Settings → อัป Service Account JSON

2. หน้า **Home** → พิมพ์โจทย์ → กด **▶️ ให้น้องช่วยทำ!**

3. ระบบจะรัน 11 phases — ดูสถานะ + output ของแต่ละ agent ได้

4. เสร็จ → ดาวน์โหลด TXT / Code / All-in-one

---

## ⚙️ Settings ที่ปรับได้

| Setting | Default | คำอธิบาย |
|---------|---------|---------|
| 🤖 Model | gemini-2.5-pro | เปลี่ยน Gemini model ได้ตลอด |
| ⏱ Delay | 10 วินาที | หน่วงระหว่าง agent (กัน rate limit) |
| ⚖️ Judge Threshold | 85/100 | คะแนนผ่าน |
| 🔁 Max Judge Loops | 5 | จำนวนรอบ revise สูงสุด |
| 📍 Project ID | จาก ADC | Google Cloud Project |
| 🌏 Region | us-central1 | Vertex AI region |

---

## 📁 โครงสร้าง

```
happy-ai-agent/
├─ app.py              ← Streamlit UI
├─ pipeline.py         ← Orchestrator
├─ agents.py           ← Prompts ของ agents
├─ extractor.py        ← แยก code → ไฟล์
├─ auth.py             ← Hybrid auth
├─ requirements.txt
├─ .gitignore
├─ assets/happy_logo.png
└─ sessions/           ← ประวัติ
```

---

## 🛡 ความปลอดภัย

- Service Account JSON อยู่ใน RAM เท่านั้น (ไม่บันทึกดิสก์)
- `.gitignore` กัน push credentials
- Error message ปกปิดข้อมูลละเอียดอ่อน

---

## ⚠️ ข้อจำกัดที่ควรรู้

- Streamlit ไม่หยุด pipeline กลางรันแบบทันที — รอ phase ปัจจุบันจบก่อน
- Cloud Shell ตัดเชื่อมต่อหลัง 60 นาทีไม่ใช้
- Quota Vertex AI จำกัด — ถ้าเจอ rate limit เพิ่ม delay

---

## 🐛 Troubleshooting

**"ยังไม่ได้เชื่อมต่อ"**
→ ไป ⚙️ Settings → อัป Service Account JSON หรือรัน `gcloud auth application-default login`

**"quota exceeded"**
→ เพิ่ม delay เป็น 30+ วินาที ใน Settings

**Judge วน loop ไม่จบ**
→ ลด Threshold เหลือ 75-80 หรือลด Max Loops เหลือ 3

**Port 8080 ใช้ไม่ได้**
→ ลอง port อื่น: `streamlit run app.py --server.port=8501`

---

🤖 Made with ❤️ — สำหรับคนที่อยากให้ AI หลายตัวทำงานร่วมกัน
