# Happy AI Agent v2.0.6 — Release Notes

**วันที่:** 2026-05-22
**Distribution:** `HappyAIAgent-Setup.zip` (91 MB)
**Status:** Tested — silent install + GUI install ทำงานครบ

---

## ⭐ ของใหม่ในเวอร์ชันนี้

### 🏷️ Rename ครบทั้งระบบ (ทั้งชื่อทั้งโฟลเดอร์)

| ส่วน | จาก | เป็น |
|---|---|---|
| **Display name** | HAPPY / HAPPY — AI Agent | **Happy AI Agent** |
| **Title bar** | HAPPY — AI Agent v2.0.5 | **Happy AI Agent v2.0.6** (no em-dash) |
| **Main exe** | HAPPY.exe | **HappyAIAgent.exe** |
| **Installer** | HAPPY-Setup.exe | **HappyAIAgent-Setup.exe** |
| **Install folder** | `%LocalAppData%\Programs\HAPPY\` | `%LocalAppData%\Programs\HappyAIAgent\` |
| **Shortcut** | HAPPY.lnk | **HappyAIAgent.lnk** |
| **Registry key** | `HKCU\...\Uninstall\HAPPY` | `HKCU\...\Uninstall\HappyAIAgent` |
| **Setup title** | HAPPY Setup | **Happy AI Agent Setup** |
| **Main spec** | HAPPY.spec | **HappyAIAgent.spec** |
| **Installer spec** | HAPPYSetup.spec | **HappyAIAgentSetup.spec** |
| **Payload zip** | dist/HAPPY.zip | **dist/HappyAIAgent.zip** |
| **Distribution zip** | HAPPY-Setup.zip | **HappyAIAgent-Setup.zip** |
| **User-Agent (updater)** | HAPPY-AI-Agent-Updater | **HappyAIAgent-Updater** |

### 📁 ที่เก็บเดิม (Preserve)

- ✅ `~/.happy/` — API key + sessions + settings เก็บไว้เดิม (backwards compat)
- ✅ Project folder `HAPPY-Ai-Agent/` — เก็บเดิม (Nick's project workspace name)
- ✅ Color theme constants `HAPPY_ORANGE`, `HAPPY_PINK`, etc. — internal naming, ไม่เปลี่ยน

### 📄 Doc files updated

- `README.md` — rewrite ใหม่หมด, ลบ Streamlit description, ใส่ native CTk + auto-updater
- `CLAUDE.md` — Claude onboarding doc updated, ลบ references ของไฟล์เก่า (`app.py`, `happy_desktop.py`)
- `installer/license-en.txt` + `license-th.txt` — ลบ (เป็น orphan จาก Inno Setup era)
- `releases/v2.0.5/` — ลบ (failed release, never shipped)

---

## ✅ Tested

- ✓ Build pipeline: `pyinstaller HappyAIAgent.spec` → `python installer/build_installer.py`
- ✓ Silent install: `HappyAIAgent-Setup.exe --silent --upgrade` → 100% progression in installer log
- ✓ Install layout flat: `%LocalAppData%\Programs\HappyAIAgent\HappyAIAgent.exe`
- ✓ Shortcuts created (Desktop + Start Menu)
- ✓ Registry `HKCU\...\Uninstall\HappyAIAgent` populated correctly
- ✓ App auto-launched with title "Happy AI Agent v2.0.6"
- ✓ crash.log shows clean start (no errors)
- ✓ Auto-update thread fires (silent if no GitHub repo released yet)

---

## 🚀 วิธีใช้

```
1. ดาวน์โหลด HappyAIAgent-Setup.zip (91 MB)
2. แตก zip → ได้โฟลเดอร์ HappyAIAgent-Setup/
3. รัน HappyAIAgent-Setup/HappyAIAgent-Setup.exe
4. ระหว่าง install — paste Gemini API key (ขอฟรีที่ https://aistudio.google.com/apikey)
5. เปิดแอปจาก Start Menu หรือ Desktop shortcut
```

หรือ silent (สำหรับ auto-updater):
```
HappyAIAgent-Setup.exe --silent --upgrade
```

---

## 📦 ขนาด

| | v2.0.5 (HAPPY name) | v2.0.6 (HappyAIAgent name) |
|---|---|---|
| Installer zip | 91 MB | 91 MB (เท่าเดิม) |
| Installed | 125 MB | 125 MB (เท่าเดิม) |
| Main exe | 17 MB | 17 MB (เท่าเดิม) |

(ขนาดเท่าเดิมเพราะแค่ rename, ไม่มี logic change)

---

## 🛠 Diagnostic

- App crash → `~/.happy/crash.log`
- Installer crash → `~/.happy/installer-crash.log`
- Updater errors → `%TEMP%/happy-ai-agent-updater.log`

---

🤖 สร้างด้วย ♥ โดย Nick & Codey (Happy AI Family)
