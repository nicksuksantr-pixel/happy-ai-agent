# Workie Notes — HAPPY Project

> **Workie's running notebook** for the HAPPY AI Agent project.  
> Started: 2026-05-14 14:01  
> Source of truth: `HANDOFF.md` (อ่านก่อนทำงานทุกครั้ง)

---

## 📌 Quick context (1-min refresher)

- **โปรเจกต์**: HAPPY — Streamlit app ที่ orchestrate Gemini agents หลายตัวให้ "ประชุม" แล้วเขียนโค้ดส่ง user
- **เทค**: Python 3.13 + Streamlit 1.57 + google-genai + pywebview + PyInstaller
- **ไฟล์หลัก**: `app.py` (80 KB), `pipeline.py`, `agents.py`, `happy_desktop.py`
- **Auth**: Gemini AI Studio API key เก็บที่ `~/.happy/auth.json` (**ห้าม** กลับไปแนะ Vertex AI กับนิก)

## 🚨 Rules Workie ต้องจำ (จาก handoff)

1. **ห้ามแนะนำ Vertex AI** — นิกเพิ่งปิด GCP project, เสียเงิน ฿334 ไปแล้ว
2. **ภาษาไทยทั้งหมด** — UI + error messages + log
3. **Tables ดีกว่า bullet ยาวๆ** — นิกชอบ visual
4. **Single-click delete** — อย่าใส่ 2-step confirm
5. **Backup .bak ก่อนแก้ไฟล์สำคัญ**
6. **Default judge_threshold = 100, delay = 60s** (สำคัญสำหรับ free tier 5 RPM)

## ⚡ งานชิ้นถัดไป (จาก handoff)

| Priority | งาน | ไฟล์ |
|---|---|---|
| 🥇 1 | Verify download bridge ใน HAPPY.exe | `happy_desktop.py` |
| 🥈 2 | แก้โปรแกรมหน่วง (ใช้ `@st.fragment`) | `app.py` page_running |
| 🥉 3 | Performance opt (`@st.cache_data`, lazy-load) | `pipeline.py`, sidebar |
| 🏅 4 | Deploy เป็น Streamlit Cloud (optional) | git init + push |

## 📓 Workie's activity log

### 2026-05-14 14:01 — Project handed off
- โค้ดดี้สร้าง HANDOFF.md (270 บรรทัด / 19.9 KB)
- เวิร์คกี้ mount โฟลเดอร์ `C:\Users\NickSuksanTr\Desktop\happy-ai-agent` เข้า Cowork
- เริ่ม WORKIE_NOTES.md (ไฟล์นี้)
- รอนิกตัดสินใจว่าจะทำ priority 1 ก่อนเลย หรือพักก่อน
