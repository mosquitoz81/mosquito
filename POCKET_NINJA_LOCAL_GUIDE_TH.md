# Pockie Ninja Offline Server - Local Guide

## Overview / ภาพรวม

This guide covers running Pockie Ninja as a single-player offline game on Windows.

คู่มือนี้สำหรับเล่น Pockie Ninja แบบ offline คนเดียวบน Windows

---

## Prerequisites / สิ่งที่ต้องมี

| Component         | Version | Notes |
|-------------------|---------|-------|
| Windows           | 10/11   | |
| Python            | 3.8+    | ต้อง add to PATH |
| MySQL             | 5.x/8.x| XAMPP หรือ standalone |
| Flash Browser     | -       | Chrome/Edge ปกติ ใช้ไม่ได้ |
| Java 6 portable   | 1.6     | อยู่ใน `local\jdk6\` |
| Game files         | -       | อยู่ใน `work\Pockie\` |

---

## Directory Structure / โครงสร้างไฟล์

```
srv-offline/
├── local/                       # Scripts & tools
│   ├── start-local.bat          # Start all services (double-click)
│   ├── stop-local.bat           # Stop all services
│   ├── start-local.ps1          # PowerShell start script
│   ├── stop-local.ps1           # PowerShell stop script
│   ├── local_web.py             # Web server (port 8080)
│   ├── socket_proxy.py          # Flash-to-DmEnter proxy (port 7001)
│   ├── flash_policy.py          # Flash policy server (port 843)
│   ├── debug_connection.py      # Connection debugger
│   ├── gmcmd.bat                # GM command helper
│   ├── thai_patch.py            # Indonesian -> Thai/English translator
│   ├── thai-patch.ps1           # Translation wrapper
│   ├── jdk6/                    # Java 6 portable
│   └── logs/                    # Log files
├── work/
│   └── Pockie/                  # Game files
│       ├── app/bin/             # Game server + DmEnter
│       ├── apache/sever         # Server list config
│       ├── backupdb/            # Database backups
│       └── source/              # Flash resources
└── POCKET_NINJA_LOCAL_GUIDE_TH.md
```

---

## Port Map / แผนผัง Port

```
Flash Browser
    │
    ├──[HTTP 8080]──→  local_web.py (web server)
    │                    ├── Game resources (SWF, JS)
    │                    ├── CAS authentication
    │                    ├── xrconfig (server config)
    │                    └── Admin panel
    │
    ├──[TCP 843]────→  flash_policy.py
    │                    └── Cross-domain policy XML
    │
    └──[TCP 7001]───→  socket_proxy.py
                         │  (filters Flash policy requests)
                         │
                         └──[TCP 7101]──→  DmEnter.exe (gateway)
                                            │
                                            └──[TCP 8001]──→  java game01 (game server)
                                                                │
                                                                └──[TCP 3306]──→  MySQL
```

---

## Quick Start / เริ่มต้นเร็ว

### 1. Start MySQL
- XAMPP: เปิด XAMPP Control Panel -> Start MySQL
- หรือ: `net start mysql`

### 2. Start Game Server
```powershell
.\local\start-local.bat
# หรือ
powershell -ExecutionPolicy Bypass -File .\local\start-local.ps1
```

### 3. Verify Ports / เช็ก Port
```powershell
netstat -ano | findstr ":7001 :7101 :8001 :8080 :843"
```
ทุก port ต้อง LISTENING

### 4. Open Game / เปิดเกม
เปิด **Flash Browser** (ห้ามใช้ Chrome/Edge ปกติ) แล้วไปที่:
```
http://127.0.0.1:8080/littleninjasclient.html?nocache=3
```

### 5. Stop Server / ปิดเซิร์ฟเวอร์
```powershell
.\local\stop-local.bat
```

---

## Accounts / บัญชี

### Default Account
| Field    | Value |
|----------|-------|
| Email    | localadmin@local |
| Password | localadmin |
| GM Level | 1 (admin) |
| Gold     | 999999 |

### Original GM Accounts (from backup)
| Email | Password |
|-------|----------|
| augustine@gameweb.co.id | qwerty789 |
| benjamin@gameweb.co.id  | giladannormal |
| bishop@gameweb.co.id | bishop@gameweb.co.id |
| clea@gameweb.co.id | cl34clea |

---

## Admin Panel / แผงควบคุม

เปิด browser ไปที่: `http://127.0.0.1:8080/admin.html`

Features:
- Server status check (ดูสถานะ service)
- Account management (จัดการบัญชี)
- GM commands (คำสั่ง GM)
- CAS format switcher (ปรับ format CAS)
- Login ticket generator (สร้าง ticket)

---

## GM Commands / คำสั่ง GM

### Method 1: Admin Panel (Web)
เปิด `http://127.0.0.1:8080/admin.html` แล้วใช้ GM Commands section

### Method 2: Command Line
```
.\local\gmcmd.bat
```
มีเมนูให้เลือก: Add Gold, Add Coin, Add EXP, Add Item, Set Level, etc.

### Method 3: Direct URL
```
http://127.0.0.1:8080/gmcmd.php?cmd=addgold&arg1=999999&uid=1
http://127.0.0.1:8080/gmcmd.php?cmd=max_gold&uid=1
http://127.0.0.1:8080/gmcmd.php?cmd=max_level&uid=1
http://127.0.0.1:8080/gmcmd.php?cmd=list_accounts
```

### Method 4: In-Game GM Commands
เมื่อเข้าเกมได้แล้ว (gmlevel=1) ใช้คำสั่งในเกมตาม gm.ini

---

## Translation Patch / แปลภาษา

### Scan (preview)
```powershell
.\local\thai-patch.ps1 scan
# หรือ
python .\local\thai_patch.py --game-root .\work\Pockie --mode scan -v
```

### Apply
```powershell
.\local\thai-patch.ps1 apply
```
ระบบจะ backup ไฟล์เดิมเป็น `.bak_indo` ก่อนแก้

### Revert
```powershell
.\local\thai-patch.ps1 revert
```

---

## Troubleshooting / แก้ปัญหา

### Green Screen after 100% Loading / จอเขียวค้างหลังโหลด 100%

**Step 1: Run debug tool**
```powershell
python .\local\debug_connection.py
```

**Step 2: Check which port Flash is connecting to**
```powershell
netstat -ano | findstr "ESTABLISHED" | findstr ":7001 :8001"
```

- ถ้า Flash ต่อ **8001** = config ยังเก่า -> ปิด Flash Browser ทั้งโปรแกรม แล้วเปิดใหม่
- ถ้า Flash ต่อ **7001** = proxy ทำงาน -> ดู step 3

**Step 3: Check DmEnter**
```powershell
# ดู DmEnter error logs
Get-ChildItem '.\work\Pockie\app\bin\' -Filter "ERROR*" | ForEach-Object { Get-Content $_.FullName -Tail 20 }
Get-Content .\local\logs\dmenter01.err.log -Tail 50
```

- ถ้า DmEnter crash (ACCESS_VIOLATION) = อาจมี protocol issue
- ถ้า DmEnter ไม่ crash = ดู step 4

**Step 4: Check CAS format**
```powershell
# ดู web server log ว่า DmEnter เรียก CAS อะไร
Get-Content .\local\logs\web.log -Tail 50 | Select-String "CAS"
```

ถ้า DmEnter เรียก CAS แล้วไม่ยอมรับ response:
1. เปิด `http://127.0.0.1:8080/admin.html`
2. ไปที่ "CAS Format" section
3. ลองเปลี่ยน format: pipe, json, simple_uid, simple_ok, xml_cas
4. ปิด Flash Browser ทั้งโปรแกรม แล้วเปิดใหม่

**Step 5: Check game01 logs**
```powershell
Get-Content '.\work\Pockie\app\bin\log\game01+.log' -Tail 120
```

### DmEnter Crash / DmEnter หยุดทำงาน

ถ้า DmEnter.exe crash ด้วย ACCESS_VIOLATION:
1. ตรวจสอบว่า proxy ทำงาน (port 7001)
2. ตรวจสอบ DmEnter01.ini:
   ```ini
   port = 7101
   GamePort = 8001
   ```
3. ตรวจสอบ `work\Pockie\apache\sever`:
   ```
   2 127.0.0.1 7001 http://127.0.0.1:8080/cas.php?server=s1 http://127.0.0.1:8080/game/xrconfig
   ```
4. proxy จะกัน Flash policy request ไม่ให้ถึง DmEnter

### Resource 404

ถ้า Flash ขอ resource แล้ว 404:
1. ดู web.log ว่า URL อะไร 404
2. หา file ใน `work\Pockie\source\`:
   ```powershell
   Get-ChildItem -Recurse '.\work\Pockie\source\' -Filter "*keyword*"
   ```
3. เพิ่ม mapping ใน `local\resource_map.json`:
   ```json
   {
     "/URL_PATH": "source/actual/path/file.swf"
   }
   ```

### Port Already in Use / Port ถูกใช้อยู่

```powershell
# หา process ที่ใช้ port
netstat -ano | findstr ":7001"
# Kill process ด้วย PID
taskkill /PID <pid> /F
```

---

## Configuration Files / ไฟล์ Config สำคัญ

| File | Purpose |
|------|---------|
| `work\Pockie\app\bin\DmEnter01.ini` | DmEnter gateway config (port 7101, GamePort 8001) |
| `work\Pockie\apache\sever` | Server list (IP, port, CAS URL, xrconfig URL) |
| `work\Pockie\app\code\props\serv\game\Resource\gm\gm.ini` | GM config (sel=1 enables GM) |
| `local\resource_map.json` | Extra URL-to-file mappings (create if needed) |

---

## Useful Commands / คำสั่งที่ใช้บ่อย

```powershell
# ดูสถานะ port
netstat -ano | findstr ":7001 :7101 :8001 :8080 :843"

# ดู process ที่เกี่ยวข้อง
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe','DmEnter.exe','java.exe','mysqld.exe')
} | Select-Object ProcessId,Name,CommandLine

# ดู log ล่าสุด
Get-Content .\local\logs\web.log -Tail 50
Get-Content .\local\logs\socket_proxy.log -Tail 50
Get-Content .\local\logs\web.err.log -Tail 50
Get-Content .\local\logs\socket_proxy.err.log -Tail 50
Get-Content '.\work\Pockie\app\bin\log\game01+.log' -Tail 120

# Debug connection
python .\local\debug_connection.py
```

---

## Important Notes / ข้อควรระวัง

1. **ห้ามใช้ Chrome/Edge ปกติ** - Flash ไม่ทำงาน ต้องใช้ Flash Browser หรือ Flash Player projector
2. **ปิด Flash Browser ทั้งโปรแกรม** ก่อนเปิดใหม่ เพราะ cache socket/config หนักมาก
3. **Java 6** - Game server ต้องใช้ Java 6 (`local\jdk6\bin\java.exe`)
4. **Port 843** - ต้อง Run as Administrator ถ้า bind ไม่ได้ (port < 1024)
5. **Encoding** - อย่าแปลง encoding ของไฟล์ถ้าไม่จำเป็น PowerShell อาจแสดงภาษาไทยเพี้ยน แต่ไฟล์อาจเป็น UTF-8 อยู่
