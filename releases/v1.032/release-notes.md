# HAPPY v1.032 — Release Notes

**วันที่:** 2026-05-16
**Installer:** `HAPPY-Setup-1.032.exe` (101 MB compressed, 330 MB installed)
**Status:** ✅ Tested

---

## 🎁 อะไรใหม่ในเวอร์ชันนี้

### ✨ Installer แบบโปร (ใหม่ทั้งหมด)
- 🌐 **Language picker** — เลือก ไทย / English ก่อนติดตั้ง
- 📦 ติดตั้งใน `%LocalAppData%\Programs\HAPPY` — **ไม่ต้องใช้ admin**
- 📋 มี Start Menu shortcut + Desktop shortcut (เลือก)
- 🗑️ ถอนการติดตั้งจาก Settings > Apps ได้ครบ
- 🚀 Auto-start เมื่อ boot Windows (optional)
- 🎨 Brand colors ส้ม-ชมพู + HAPPY mascot

### 🐛 Bug fixes ตั้งแต่เวอร์ชันก่อน
- ✅ **Bug A** Download buttons ใน HAPPY.exe ทำงาน (patch `HTMLAnchorElement.prototype.click`)
- ✅ **Bug B** Build .exe button ทำงาน (fix `sys.executable` ใน frozen mode)
- ✅ **Bug C** .exe ที่ build ออกมาไม่มี console ดำๆ ขึ้น (`--windowed` + runtime hook)
- ✅ **Bug D** ชื่อไฟล์ดาวน์โหลดถูก (parse Content-Disposition header)
- ✅ Sessions เก็บที่ `~/.happy/sessions/` (เดิม relative path → fragile)

### 🔧 Pipeline improvements (committed, ยังไม่ verify)
- Bug 17 — Coder no-preamble directive (กัน truncation)
- Bug 18 — Judge hard verification (กัน fluff false PASS)
- Bug 19 — `detect_project_type` prefer HTML when > 2x .py size
- Bug 21 — Capacity-aware retry (CAPACITY_DELAYS for 503)

---

## 🚀 วิธีใช้

```
1. Double-click HAPPY-Setup-1.032.exe
2. เลือกภาษา (ไทย/English)
3. กด Next → Accept license → Choose location → Install
4. รอ ~30 วินาที
5. กด "Launch HAPPY now" → เปิดได้เลย
6. ใส่ Gemini API key (ขอที่ aistudio.google.com/apikey ฟรี)
7. เริ่มพิมพ์โจทย์ → กดเริ่ม
```

## 📋 System Requirements

- Windows 10 / 11 (64-bit)
- RAM 4 GB+ (8 GB แนะนำ)
- Internet (สำหรับ Gemini API)
- พื้นที่ว่าง ~400 MB

## 🤝 Support

- ส่งกลับให้คนที่ส่ง .exe มา ถ้าเจอบัค
- ระบุ: Windows version + error message (screenshot ได้)

## 📝 Known limitations

- Pipeline output quality ขึ้นกับ Gemini model — Lite Preview อาจ truncate ที่ 4K tokens (Bug 17 fix prompt-side แล้ว, แต่ root cause = model cap)
- ถ้าโจทย์ซับซ้อน 8+ pages → แนะนำใช้ `gemini-2.5-pro` หรือ `gemini-3.1-pro-preview`

---

🤖 Built with HAPPY's own toolchain + Claude Code session
