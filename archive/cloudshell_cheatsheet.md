# 📚 คู่มือคำสั่ง Cloud Shell / Linux ฉบับใช้จริง

> สำหรับมือใหม่ — เน้นใช้บ่อย เน้นเข้าใจง่าย ไม่ต้องท่อง

---

## 🗺️ 1. เคลื่อนที่และดูไฟล์ (ใช้บ่อยสุด)

| คำสั่ง | ความหมาย | ตัวอย่าง |
|---|---|---|
| `pwd` | ดูว่าตอนนี้อยู่โฟลเดอร์ไหน | `pwd` |
| `ls` | ดูไฟล์ในโฟลเดอร์ปัจจุบัน | `ls` |
| `ls -lh` | ดูไฟล์แบบละเอียด + ขนาดอ่านง่าย | `ls -lh` |
| `ls -la` | ดูไฟล์ทุกตัวรวมไฟล์ซ่อน | `ls -la` |
| `cd ชื่อโฟลเดอร์` | เข้าโฟลเดอร์ | `cd project` |
| `cd ..` | ออกไปโฟลเดอร์ก่อนหน้า | `cd ..` |
| `cd ~` | กลับ home | `cd ~` |
| `cd /` | ไป root สุด | `cd /` |

> 💡 **เคล็ดลับ:** กด `Tab` = autocomplete ชื่อไฟล์/โฟลเดอร์ ไม่ต้องพิมพ์เต็ม!

---

## 📖 2. อ่านไฟล์

| คำสั่ง | ความหมาย |
|---|---|
| `cat ไฟล์` | แสดงทั้งไฟล์ |
| `head ไฟล์` | แสดง 10 บรรทัดแรก |
| `head -20 ไฟล์` | แสดง 20 บรรทัดแรก |
| `tail ไฟล์` | แสดง 10 บรรทัดสุดท้าย |
| `tail -50 ไฟล์` | แสดง 50 บรรทัดสุดท้าย |
| `less ไฟล์` | เปิดดูแบบเลื่อนได้ (กด `q` ออก) |
| `wc -l ไฟล์` | นับจำนวนบรรทัด |

---

## ✏️ 3. แก้ไขไฟล์

| คำสั่ง | ความหมาย |
|---|---|
| `nano ไฟล์` | เปิดแก้ไข แบบง่ายสุด |
| `vim ไฟล์` | เปิดแก้ไข แบบ pro (ยาก) |
| `cloudshell edit ไฟล์` | เปิดใน Cloud Shell Editor (GUI สวย) ← **แนะนำ** |

**ใน nano:**
- `Ctrl+O` = save
- `Ctrl+X` = ออก
- `Ctrl+W` = ค้นหา

---

## 📁 4. จัดการไฟล์/โฟลเดอร์

| คำสั่ง | ความหมาย |
|---|---|
| `mkdir ชื่อ` | สร้างโฟลเดอร์ |
| `touch ไฟล์.txt` | สร้างไฟล์เปล่า |
| `cp ต้นทาง ปลายทาง` | คัดลอกไฟล์ |
| `cp -r โฟลเดอร์ ปลายทาง` | คัดลอกทั้งโฟลเดอร์ |
| `mv ต้นทาง ปลายทาง` | ย้าย/เปลี่ยนชื่อ |
| `rm ไฟล์` | ลบไฟล์ ⚠️ ลบแล้วลบเลย ไม่มี recycle bin |
| `rm -r โฟลเดอร์` | ลบทั้งโฟลเดอร์ ⚠️ |
| `rm -rf โฟลเดอร์` | ลบไม่ถาม ⚠️⚠️ ระวังพิมพ์ผิด! |

> 🛡️ **กฎเหล็ก:** ก่อน `rm` ดูให้แน่ใจด้วย `ls` ก่อนเสมอ

---

## 🔍 5. ค้นหา (สำคัญมาก)

| คำสั่ง | ความหมาย |
|---|---|
| `grep "คำ" ไฟล์` | หาคำในไฟล์ |
| `grep -n "คำ" ไฟล์` | หาคำพร้อมเลขบรรทัด |
| `grep -r "คำ" โฟลเดอร์` | หาคำในทุกไฟล์ในโฟลเดอร์ |
| `find . -name "*.py"` | หาไฟล์ทั้งหมดที่ลงท้าย .py |
| `find . -name "test*"` | หาไฟล์ที่ขึ้นต้นด้วย test |

**ตัวอย่างใช้จริง:**
```bash
grep -n "MODEL" pipeline_v3.py    # หาคำว่า MODEL ในไฟล์
find ~ -name "*.txt"               # หาไฟล์ .txt ทั้งหมดใน home
```

---

## 🐍 6. รัน Python

| คำสั่ง | ความหมาย |
|---|---|
| `python ไฟล์.py` | รันสคริปต์ Python |
| `python3 ไฟล์.py` | ระบุ Python 3 (บางเครื่องต้องใช้) |
| `python -c "print('hi')"` | รันโค้ดสั้นๆ บรรทัดเดียว |
| `pip install ชื่อ` | ติดตั้ง library |
| `pip list` | ดู library ที่ติดตั้งไว้ |

---

## ☁️ 7. Google Cloud (เฉพาะ Cloud Shell)

| คำสั่ง | ความหมาย |
|---|---|
| `gcloud config list` | ดูการตั้งค่าปัจจุบัน (project ฯลฯ) |
| `gcloud auth list` | ดู account ที่ login |
| `gcloud projects list` | ดูทุก project ที่มีสิทธิ์ |
| `gcloud config set project XXX` | เปลี่ยน project |
| `cloudshell download ไฟล์` | ดาวน์โหลดไฟล์ลงเครื่อง |
| `cloudshell edit ไฟล์` | เปิดด้วย Cloud Shell Editor |
| `gcloud storage ls gs://bucket` | ดูไฟล์ใน GCS bucket |
| `gcloud storage cp ไฟล์ gs://bucket/` | อัปไฟล์ขึ้น GCS |

---

## 📦 8. ZIP / Compress

| คำสั่ง | ความหมาย |
|---|---|
| `zip ผลลัพธ์.zip ไฟล์1 ไฟล์2` | บีบหลายไฟล์ |
| `zip -r ผลลัพธ์.zip โฟลเดอร์` | บีบทั้งโฟลเดอร์ |
| `unzip ไฟล์.zip` | แตก zip |
| `tar -czf out.tar.gz โฟลเดอร์` | บีบ tar.gz |
| `tar -xzf ไฟล์.tar.gz` | แตก tar.gz |

---

## 🎯 9. คำสั่งทั่วไปที่ช่วยชีวิต

| คำสั่ง | ความหมาย |
|---|---|
| `clear` หรือ `Ctrl+L` | ล้างหน้าจอ |
| `Ctrl+C` | หยุดโปรแกรมที่รันอยู่ |
| `Ctrl+D` | ออกจาก python REPL / shell |
| `↑ ↓` | เรียกคำสั่งเก่าที่เคยพิมพ์ |
| `history` | ดูคำสั่งทั้งหมดที่เคยพิมพ์ |
| `!!` | รันคำสั่งล่าสุดอีกครั้ง |
| `man คำสั่ง` | อ่านคู่มือ (กด `q` ออก) |

---

## 🛠️ 10. Trick ขั้นเทพ

### Redirect (เก็บผลลัพธ์ลงไฟล์)

```bash
ls > files.txt                  # เซฟผล ls ลงไฟล์ (เขียนทับ)
ls >> files.txt                 # เซฟต่อท้าย ไม่ทับ
python app.py > log.txt 2>&1    # เซฟทั้ง output + error
```

### Pipe (ส่งผลลัพธ์เข้าคำสั่งต่อไป)

```bash
ls | grep ".py"                 # ls แล้วกรองเฉพาะ .py
cat ไฟล์ | head -20             # อ่านไฟล์ แสดง 20 บรรทัดแรก
history | grep "python"         # หาคำสั่ง python ในประวัติ
```

### รันหลายคำสั่งทีเดียว

```bash
mkdir test && cd test && touch a.txt    # ทำทีละขั้น หยุดถ้าพัง
mkdir test ; cd test ; touch a.txt      # ทำทุกขั้น ไม่ว่าจะพังมั้ย
```

### แก้คำในไฟล์อัตโนมัติด้วย sed

```bash
sed -i 's|ของเก่า|ของใหม่|g' ไฟล์      # แทนที่ทุกที่ในไฟล์
sed -i 's|MODEL = ".*"|MODEL = "gemini-2.5-pro"|' pipeline_v3.py
```

---

## 🚨 คำสั่งที่ต้องระวัง

```bash
rm -rf /              # ⚠️ ลบทั้งเครื่อง! ห้ามรันเด็ดขาด
rm -rf *              # ⚠️ ลบทุกอย่างในโฟลเดอร์ปัจจุบัน
sudo คำสั่ง           # รันแบบ admin (Cloud Shell ส่วนใหญ่ไม่ต้องใช้)
> ไฟล์ที่มีอยู่         # ⚠️ จะทำให้ไฟล์ว่างเปล่าทันที (ใช้ >> ถ้าไม่อยากให้ทับ)
```

---

## 🎓 Workflow ตัวอย่าง (จริงจังเลย)

**สมมติอยากรัน pipeline แล้วเซฟผลแยกๆ:**

```bash
# 1. ดูว่ามีไฟล์อะไรบ้าง
ls -lh

# 2. ย้าย output เก่าออก (เผื่ออยากเก็บ)
mv output_v3.txt output_v3_backup.txt

# 3. รัน pipeline
python pipeline_v3.py

# 4. ดูขนาดผลลัพธ์
ls -lh output_v3.txt

# 5. ดู 20 บรรทัดแรก
head -20 output_v3.txt

# 6. หาคำว่า "ERROR" ในผล
grep -n "ERROR" output_v3.txt

# 7. zip ทั้งหมดเตรียมดาวน์โหลด
zip result.zip output_v3.txt pipeline_v3.py

# 8. ดาวน์โหลด
cloudshell download result.zip
```

---

## 💡 5 เคล็ดลับที่ควรจำ

1. **Tab autocomplete** — พิมพ์ครึ่งคำแล้วกด Tab ระบบจะเติมให้
2. **ปุ่ม ↑** — เรียกคำสั่งเก่า ไม่ต้องพิมพ์ใหม่
3. **`man คำสั่ง`** — อ่านคู่มือเอง (เช่น `man ls`)
4. **`คำสั่ง --help`** — ดูวิธีใช้แบบสั้นๆ (เช่น `ls --help`)
5. **ก่อนลบ ดูก่อน** — `ls` หรือ `cat` ก่อน `rm` เสมอ

---

## 📝 คำสั่งสำหรับ pipeline_v3.py โดยเฉพาะ

### เช็คโมเดลที่ใช้
```bash
grep "MODEL = " pipeline_v3.py
```

### เปลี่ยนโมเดล
```bash
sed -i 's|MODEL = ".*"|MODEL = "gemini-2.5-pro"|' pipeline_v3.py
```

### ลด sleep ให้รันเร็วขึ้น
```bash
sed -i 's|time.sleep(120)|time.sleep(10)|g' pipeline_v3.py
```

### ดูรายชื่อโมเดลที่ใช้ได้
```bash
python -c "
from google import genai
client = genai.Client(vertexai=True, project='nick-ai-agent-2026', location='us-central1')
for m in client.models.list():
    print(m.name)
"
```

### Backup output ก่อนรันรอบใหม่
```bash
mv output_v3.txt output_v3_$(date +%Y%m%d_%H%M%S).txt
```

---

## 📤 วิธีดาวน์โหลด / อัปขึ้น Drive

### ดาวน์โหลดจาก Cloud Shell ลงเครื่อง
```bash
cloudshell download ชื่อไฟล์
```

### อัปขึ้น Cloud Storage (GCS)
```bash
gcloud storage cp ไฟล์ gs://nick-ai-agent-output/
```

### อัปขึ้น Google Drive (วิธีง่ายสุด)
1. `cloudshell download ไฟล์`  → ดาวน์โหลดลงเครื่อง
2. เปิด drive.google.com  → ลากไฟล์เข้า

---

*คู่มือนี้ออกแบบมาเพื่อใช้งานจริง ไม่ต้องท่อง แค่เปิดดูตอนใช้*
