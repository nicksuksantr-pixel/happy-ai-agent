# Log — v2.8.3 (security: ปิดช่องโหว่ PAT-in-exe)

**วันที่:** 2026-06-04 · **โดย:** Coddy (Claude Code) · ต่อจาก v2.8.2 Tester audit · push ตรง main

## Nick สั่งอะไร
- จาก 2 decision ท้าย v2.8.2 audit → Nick เลือก:
  1. **PAT-in-exe (A3#2): ทำ update-repo เป็น public** (เลือก "A) public ทั้ง repo" — ยอมให้โค้ด+prompt เปิดสาธารณะ เพื่อไม่ต้องฝัง token)
  2. delete-confirm: เก็บ confirm ไว้เฉพาะ delete ที่ลบถาวร → โค้ดเดิมถูกแล้ว (บันทึก memory §F)

## ทำอะไรไป
- **Security scan ก่อนเปิด public:** สแกน git history + tree เต็ม — ไม่มี secret หลุดเลย (credential file ไม่เคย track · ไม่มี Gemini key / GitHub token / private-key ใน diff ไหน · `.env` ไม่เคย track)
- **เปิด repo เป็น PUBLIC:** `gh repo edit --visibility public` → visibility = PUBLIC ✓
- **เอา `.env` ออกจาก bundle:** แก้ `HappyAIAgent.spec` ลบ block ที่ bake `.env` (มีแค่ `HAPPY_AI_UPDATE_TOKEN`) → build ใหม่ไม่ฝัง token · updater ทำงาน token-less (มี fallback `browser_download_url` + public API)
- bump VERSION 2.8.2 → **2.8.3** → build + release

## ผล / ผลกระทบ
| ประเด็น | ผล |
|--------|-----|
| ช่องโหว่ PAT-in-exe | ✅ ปิด — repo public แล้ว token ที่เคย ship (v2.8.2-) **ไร้ค่า** (ให้สิทธิ์แค่ public read ที่ใครก็เข้าได้) |
| client เก่า (v2.8.2-) | ✅ ไม่พัง — token ยัง valid บน public repo (แค่ไร้ค่า) อัปเดตได้ปกติ |
| client ใหม่ (v2.8.3+) | ✅ ไม่ฝัง token เลย — updater no-token path (public) |
| โค้ด + prompt | ⚠️ เปิดสาธารณะแล้ว (Nick ยอมรับ — เลือก A) |

## ⚠️ สำคัญ — อย่าเพิ่ง revoke PAT เก่า
- token เก่ายัง valid อยู่ดีกว่า **อย่า revoke ตอนนี้** — ถ้า revoke client เก่า (v2.8.2-) ที่ยังส่ง `Bearer <token>` จะโดน GitHub ตอบ **401** (invalid token ถูกปฏิเสธก่อนเช็ค public-access) → updater เก่าเงียบ ไม่ได้อัปเดต
- รอจน user ส่วนใหญ่ย้ายไป v2.8.3+ (ไม่ส่ง token แล้ว) ค่อย revoke ได้

## 🚀 Release
→ build token-free .exe + installer → tag `v2.8.3` + GitHub Release + `HappyAIAgent-Setup.zip` + SHA256 ใน body · URL ดู `memory/MEMORY.md` §G
