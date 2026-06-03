# V-Log — Happy AI Agent (version timeline)

> ประวัติเวอร์ชัน (ย่อ) ตั้งแต่ rewrite เป็น native จนถึงปัจจุบัน
> ฉบับละเอียดต่อเวอร์ชันดูได้ที่ `log/` + `bug/` + git history

| Version | สรุป |
|---|---|
| **v2.8.1** | **Tester audit (3-agent)** — แก้ P0 Running-page crash (5-field NamedTuple unpack) + drain-ticker hardening · extractor round-order · auth-gate refresh · attachments-in-Quick · Settings-reset desync · +4 regression tests (133 passed) · archive stale docs → `_trash/` · +headless AI tester (`tools/test_ai_pipeline.py`) |
| v2.8.0 | Cos audit v2.5.0 sprint — ปิด 24 bugs รอบเดียว (atomic writes, NamedTuple agent rows, public TPM accessors, drain-msg defensive, async auth/model calls) |
| v2.7.3 | fix built .exe Tcl-data error (`--collect-all tkinter` + env scrub) |
| v2.7.2 | bundled Python มี tkinter (PBS + install-wipe) |
| v2.7.1 | fix Build .exe — subdir extraction + auto-install user deps |
| v2.7.0 | bundled Python + **project-type selector** (html / desktop_installer) + per-type agent directives |
| v2.5.x | per-model quotas (`core/quotas.py`) · live model swap กลางรัน |
| v2.4.x | phase-delay min 5s · edit-mode auth card |
| v2.0.x | **rewrite เป็น native CustomTkinter** (เลิก Streamlit/pywebview/HTTP) — แยก `core/` + `ui/` |
| v1.032 | (legacy) Streamlit + pywebview + Inno Setup installer — docs ยุคนี้ถูก archive ไป `_trash/` แล้ว |

— อัปเดตล่าสุด: 2026-06-04 (v2.8.1, Coddy) · git log = ฉบับ authoritative
