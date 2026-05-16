# 📦 HAPPY Releases

โฟลเดอร์เก็บ deliverables ที่ส่งเพื่อนได้ — แต่ละเวอร์ชันมีโฟลเดอร์ของตัวเอง

## โครงสร้าง

```
releases/
├── README.md           ← ไฟล์นี้
├── v1.032/             ← เวอร์ชันที่ build เสร็จแล้ว
│   ├── HAPPY-Setup-1.032.exe       ← installer พร้อมส่งเพื่อน (~100 MB)
│   └── release-notes.md            ← เปลี่ยนแปลงอะไร, bug ที่แก้
├── v1.033/             ← เวอร์ชันถัดไป (ยังไม่มี)
└── ...
```

## หลักการ

- **เก็บ release ที่ pass test** — installer ที่ verify แล้วว่า install/uninstall ครบ
- **release-notes.md** — บอกว่า version นี้แก้ bug อะไร, ฟีเจอร์ใหม่อะไร
- **ห้ามแก้ไฟล์ใน release** — ถ้าจะแก้ → bump version → build ใหม่ → folder ใหม่
- **gitignore** — installer .exe ใหญ่ ไม่ commit เข้า git (จะเพิ่ม `releases/*/*.exe` ใน .gitignore)

## วิธีส่งเพื่อน

```
1. เปิด releases/v<latest>/HAPPY-Setup-<version>.exe
2. ส่งผ่าน Google Drive / OneDrive / Line / email
3. แนบ release-notes.md ถ้าอยากให้เพื่อนเข้าใจ
```

## วิธี build รุ่นใหม่

```powershell
# 1. แก้ version ใน installer/HAPPY.iss → #define MyAppVersion "1.033"
# 2. Rebuild HAPPY.exe
cd C:\Users\NickSuksanTr\Desktop\happy-ai-agent
pyinstaller HAPPY.spec --noconfirm

# 3. Compile installer
cd installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" HAPPY.iss

# 4. Copy to releases/
mkdir ..\releases\v1.033
copy output\HAPPY-Setup-1.033.exe ..\releases\v1.033\

# 5. เขียน release-notes.md
```
