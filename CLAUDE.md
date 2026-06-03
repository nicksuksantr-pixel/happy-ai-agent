# Happy AI Agent — Claude Onboarding

> Auto-loaded when this folder is opened in Cowork/Claude Code.

## 🤖 What is Happy AI Agent?

**Happy AI Agent** = Multi-agent code generator (CustomTkinter native desktop + Gemini AI Studio API)

User inputs a prompt → **11–18 AI agents** collaborate in sequence (PM → Architect → DB Admin → Coder → Frontend → Tester → Debugger → Judge → DevOps → Summarizer → PM Final) → produces working Python/HTML/JS code that runs immediately.

UI is a **native CustomTkinter desktop app**. No localhost port, no HTTP server.

---

## 📂 Key files

```
happy_native.py             ← Thin entry: crash log + single-instance mutex + ui.app.main()
core/                       ← config.py + persistence.py + quotas.py (settings, window_state, per-model quota table)
ui/                         ← All UI (theme + 6 pages + components + modals)
  ├── app.py                ← HappyApp, AppState, pipeline drain, auto-update flow
  ├── sidebar.py            ← Logo + 4-nav + auth pill + update pill
  ├── theme.py              ← Dark palette + 4-px spacing grid + fonts
  ├── components/           ← logo, page_header, section_card, pill, status_dot, output_view
  ├── modals/dark_modal.py  ← Borderless dark CTkToplevel
  └── pages/                ← home, runs, stats, settings, running, done
pipeline.py                 ← PipelineRunner — orchestrator + retry + TPM watcher
agents.py                   ← All 17 agent prompts + CONTEXT_MAP
auth.py                     ← Gemini API key (~/.happy/auth.json)
builder.py                  ← Build user code → .exe via PyInstaller (Python + Web)
extractor.py                ← Split code blocks → files
file_loader.py              ← Multimodal attachments (image/pdf/word/excel)
updater.py                  ← GitHub Releases auto-updater (private repo + PAT)
VERSION                     ← Plain-text version (single source of truth)
HappyAIAgent.spec           ← PyInstaller spec — main app
tools/make_icon.py          ← Multi-res .ico generator
tools/test_ai_pipeline.py   ← Headless AI pipeline tester (connectivity / --quick / --thorough)
installer/installer.py      ← Custom Python installer (dark cosmic UI, 3-phase, sparkles)
installer/build_installer.py← Build pipeline (zip payload + PyInstaller installer)
installer/HappyAIAgentSetup.spec  ← Installer PyInstaller spec
```

---

## ⚙️ Pipeline modes

| Mode | Agents | Time | Use case |
|------|--------|------|----------|
| **Quick** | 11 phases | ~15-25 min | General tasks |
| **Thorough** | 18 phases | ~30-40 min | Complex, needs deep analysis |

**Quality gates:** Tester (runnable?) → Debugger (clean?) → Judge (0-100 score, threshold=100) → auto-loop back to Coder if fails.

**Project type** (Home selector, v2.7.0): `html` (default — single-folder web, double-click `index.html`) or `desktop_installer` (Python CTk + PyInstaller `.exe`). The choice injects `agents.PROJECT_TYPE_DIRECTIVES` into every phase's context so the whole team targets the same deliverable shape. Snapshotted at run start (not live like model).

---

## 🤝 Team roles (Multi-Perspective system)

| Person | Role |
|--------|------|
| 🧑 **Nick** | Owner — call by name, not boss |
| 💻 **Coddy** | Claude Code CLI coder — edits files, runs builds |
| 🧠 **Coss** | Cowork strategy/reconciliation — analysis only, never edits code |
| 🎛️ **เวิร์คกี้** | Orchestrator — dispatches, manages tabs |

---

## 🛑 Don't do

- ❌ Don't recommend Vertex AI (Nick closed GCP, lost ฿334)
- ❌ Don't edit code if acting as Coss — analysis only
- ❌ Don't change phase delay default without asking (v2.4.7 lowered min to 5s per Nick; default still favors free-tier safety)
- ❌ Don't bring back Streamlit / HTTP server / localhost port — native CTk only
- ❌ Don't reference `backups/happy_native_v2.0.6_pre_ui_rewrite.py` — deleted 2026-05-23 (was pre-`core/`+`ui/` split, caused stale audit confusion)

---

## 🚀 How to run (dev mode)

```powershell
cd C:\Users\NickSuksanTr\Documents\Projects\HAPPY-Ai-Agent
python happy_native.py
```

First run: Settings → paste Gemini API key → Save.

---

## 🔨 How to build

```powershell
# 1. Build main app
pyinstaller HappyAIAgent.spec --noconfirm --clean
# → dist/HappyAIAgent/HappyAIAgent.exe

# 2. Build installer (zips payload + bundles into single .exe folder)
python installer/build_installer.py
# → dist/HappyAIAgent-Setup/HappyAIAgent-Setup.exe
# → dist/HappyAIAgent-Setup.zip  (for distribution)
```

---

## 📊 Gemini Free tier quotas (gemini-3.1-flash-lite-preview)

| Limit | Value |
|-------|-------|
| RPM | 15 |
| TPM | 250,000 |
| RPD | 500 |

→ ~20-30 Quick sessions/day safely.

---

## 📁 Project location

- **Source code**: `C:\Users\NickSuksanTr\Documents\Projects\HAPPY-Ai-Agent\`
- **Installed binary**: `%LocalAppData%\Programs\HappyAIAgent\HappyAIAgent.exe`
- **User config**: `~/.happy/auth.json` + `~/.happy/settings.json` + `~/.happy/sessions/`
- **Crash log**: `~/.happy/crash.log` (frozen-build diagnostics)
- **Updater log**: `%TEMP%/happy-ai-agent-updater.log`

## 🗂️ Workflow folders (Nick's command_pattern)

- `memory/MEMORY.md` — onboarding snapshot (read first; written from MASTER §5)
- `log/` · `bug/` · `V-Log.md` — per-version conversation log / bug log / version timeline
- `_trash/` — archived/unused files (git-ignored; move here, never delete). Stale Streamlit-era docs were archived here in v2.8.1.
- `user/` — user-facing exports (screenshots, mockups), not app source
- `tools/test_ai_pipeline.py` — headless end-to-end AI pipeline tester
