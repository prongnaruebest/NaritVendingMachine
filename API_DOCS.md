# Narit Vending Machine — API Documentation

> เอกสารนี้อธิบาย REST API ทั้งหมดของระบบ Narit Vending Machine
> ที่รันอยู่บน Raspberry Pi และสื่อสารกับเครื่องภายนอกผ่านเครือข่าย Wi-Fi หรือ LAN

---

## ข้อมูลการเชื่อมต่อ

| รายการ | ค่า |
|---|---|
| IP Address | `192.168.70.5` |
| Hostname (mDNS) | `http://NaritVendingMachine.local` |
| Port | `80` |
| Base URL | `http://192.168.70.5` |
| Content-Type | `application/json` |

---

## สารบัญ Endpoint

| # | Method | Endpoint | หน้าที่ |
|---|---|---|---|
| 1 | `GET`  | `/api/status` | ดึงสถานะทั้งหมดของบอร์ด |
| 2 | `GET`  | `/api/slots` | ดึงพิกัดช่องเก็บของทั้งหมด |
| 3 | `POST` | `/api/home/<axis>` | สั่ง Home แกน (x, y, z, all) |
| 4 | `POST` | `/api/jog` | สั่งจ๊อกเคลื่อนที่แกน |
| 5 | `POST` | `/api/stop` | สั่งหยุดฉุกเฉิน |
| 6 | `POST` | `/api/slots/<code>/goto` | เคลื่อนที่ไปยังช่องที่ระบุ |
| 7 | `POST` | `/api/slots/<code>` | บันทึกพิกัดช่องใหม่ |
| 8 | `POST` | `/api/slots/<code>/save-current` | บันทึกตำแหน่งปัจจุบันลง Slot |

---

## 1. GET /api/status — ดึงสถานะบอร์ด

ดึงสถานะ realtime ของแกน X/Y/Z, E-Stop, และช่องเก็บของทั้งหมด

### curl
```bash
curl http://192.168.70.5/api/status
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"

resp = requests.get(f"{BASE_URL}/api/status")
data = resp.json()

print("State:", "BUSY" if data["busy"] else "IDLE")
print("E-Stop:", data["status"]["estop"])
print("Last Error:", data["last_error"])
print("X pos:", data["status"]["x"]["position_mm"], "mm")
print("Y pos:", data["status"]["y"]["position_mm"], "mm")
print("Z pos:", data["status"]["z"]["position_mm"], "mm")
```

### ตัวอย่าง Response
```json
{
  "busy": false,
  "last_error": "",
  "slots": {
    "1": { "x_mm": 10.0, "y_mm": 20.0, "z_mm": 5.0 },
    "2": { "x_mm": 30.0, "y_mm": 20.0, "z_mm": 5.0 }
  },
  "status": {
    "estop": false,
    "x": {
      "position_mm": 0.0,
      "position_steps": 0,
      "is_homed": false,
      "head_limit": false,
      "tail_limit": false
    },
    "y": {},
    "z": {}
  }
}
```

---

## 2. GET /api/slots — ดึงพิกัดช่องเก็บของทั้งหมด

### curl
```bash
curl http://192.168.70.5/api/slots
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"

resp = requests.get(f"{BASE_URL}/api/slots")
slots = resp.json()

for code, pos in slots.items():
    print(f"Slot {code}: X={pos['x_mm']} Y={pos['y_mm']} Z={pos['z_mm']}")
```

### ตัวอย่าง Response
```json
{
  "1":  { "x_mm": 10.0, "y_mm": 20.0, "z_mm": 5.0 },
  "2":  { "x_mm": 30.0, "y_mm": 20.0, "z_mm": 5.0 },
  "30": { "x_mm": 290.0, "y_mm": 80.0, "z_mm": 5.0 }
}
```

---

## 3. POST /api/home/\<axis\> — Home แกน

สั่งให้แกนเคลื่อนที่ไปชน Limit Switch (Min) แล้วรีเซ็ตตำแหน่งเป็น 0 mm

| `<axis>` | ความหมาย |
|---|---|
| `x` | Home เฉพาะแกน X |
| `y` | Home เฉพาะแกน Y |
| `z` | Home เฉพาะแกน Z |
| `all` | Home ทุกแกน (X → Y → Z) |

### curl
```bash
# Home เฉพาะแกน X
curl -X POST http://192.168.70.5/api/home/x

# Home ทุกแกน
curl -X POST http://192.168.70.5/api/home/all
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"

# Home ทุกแกน
resp = requests.post(f"{BASE_URL}/api/home/all")
result = resp.json()
if result["ok"]:
    print("Home All สำเร็จ")
else:
    print("Error:", result.get("error"))
```

### ตัวอย่าง Response (สำเร็จ)
```json
{
  "ok": true,
  "result": null,
  "busy": false,
  "last_error": "",
  "status": {},
  "slots": {}
}
```

### ตัวอย่าง Response (ล้มเหลว, HTTP 400)
```json
{
  "ok": false,
  "error": "Limit triggered on X axis",
  "busy": false,
  "last_error": "Limit triggered on X axis"
}
```

---

## 4. POST /api/jog — จ๊อกเคลื่อนที่แกน

เคลื่อนที่แกนใดแกนหนึ่งด้วยระยะทางที่กำหนด (ค่าบวก = ไปข้างหน้า, ค่าลบ = ถอยหลัง)

### JSON Payload

| Field | Type | ตัวอย่าง | ความหมาย |
|---|---|---|---|
| `axis` | `string` | `"x"`, `"y"`, `"z"` | แกนที่ต้องการเคลื่อนที่ |
| `distance_mm` | `float` | `5.0`, `-10.0` | ระยะทาง (mm) บวก=ไปหน้า ลบ=ถอยหลัง |

### curl
```bash
# จ๊อกแกน X ไปหน้า 10 mm
curl -X POST http://192.168.70.5/api/jog \
  -H "Content-Type: application/json" \
  -d "{\"axis\": \"x\", \"distance_mm\": 10.0}"

# จ๊อกแกน Y ถอยหลัง 5 mm
curl -X POST http://192.168.70.5/api/jog \
  -H "Content-Type: application/json" \
  -d "{\"axis\": \"y\", \"distance_mm\": -5.0}"
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"

resp = requests.post(
    f"{BASE_URL}/api/jog",
    json={"axis": "x", "distance_mm": 10.0}
)
result = resp.json()
print("OK:", result["ok"])
print("X pos:", result["status"]["x"]["position_mm"], "mm")
```

---

## 5. POST /api/stop — หยุดฉุกเฉิน

สั่งหยุดการเคลื่อนที่ทั้งหมดทันที

### curl
```bash
curl -X POST http://192.168.70.5/api/stop
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"

resp = requests.post(f"{BASE_URL}/api/stop")
result = resp.json()
print("Stop requested:", result["ok"])
```

### ตัวอย่าง Response
```json
{
  "ok": true,
  "result": "stop requested",
  "busy": false,
  "last_error": "Stop requested"
}
```

---

## 6. POST /api/slots/\<code\>/goto — เคลื่อนที่ไปยังช่อง

สั่งให้บอร์ดเคลื่อนที่ไปยังพิกัดที่บันทึกไว้สำหรับช่องหมายเลข `code` (1–30)

### curl
```bash
# เคลื่อนที่ไปช่องที่ 5
curl -X POST http://192.168.70.5/api/slots/5/goto
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"

slot_code = "5"

resp = requests.post(f"{BASE_URL}/api/slots/{slot_code}/goto")
result = resp.json()

if result["ok"]:
    pos = result["status"]
    print(f"ถึงช่อง {slot_code} แล้ว")
    print(f"X={pos['x']['position_mm']} Y={pos['y']['position_mm']} Z={pos['z']['position_mm']}")
else:
    print("Error:", result.get("error"))
```

---

## 7. POST /api/slots/\<code\> — บันทึกพิกัดช่อง

กำหนดพิกัด X/Y/Z ของช่องเก็บของ แล้วบันทึกลง `machine_config.json` บน Pi

### JSON Payload

| Field | Type | ความหมาย |
|---|---|---|
| `x_mm` | `float` | พิกัดแกน X (mm) |
| `y_mm` | `float` | พิกัดแกน Y (mm) |
| `z_mm` | `float` | พิกัดแกน Z (mm) |

### curl
```bash
curl -X POST http://192.168.70.5/api/slots/3 \
  -H "Content-Type: application/json" \
  -d "{\"x_mm\": 45.0, \"y_mm\": 20.0, \"z_mm\": 5.0}"
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"

resp = requests.post(
    f"{BASE_URL}/api/slots/3",
    json={"x_mm": 45.0, "y_mm": 20.0, "z_mm": 5.0}
)
result = resp.json()
print("Saved:", result["ok"])
```

---

## 8. POST /api/slots/\<code\>/save-current — บันทึกตำแหน่งปัจจุบันลง Slot

บันทึกตำแหน่งปัจจุบันของแกน X/Y/Z ลงในช่องที่ระบุโดยไม่ต้องพิมพ์ค่าเอง (ใช้สำหรับ Calibration)

### curl
```bash
curl -X POST http://192.168.70.5/api/slots/7/save-current
```

### Python requests
```python
import requests

BASE_URL = "http://192.168.70.5"
slot_code = "7"

resp = requests.post(f"{BASE_URL}/api/slots/{slot_code}/save-current")
result = resp.json()

if result["ok"]:
    saved = result["result"]
    print(f"บันทึกช่อง {slot_code}: X={saved['x_mm']} Y={saved['y_mm']} Z={saved['z_mm']}")
```

---

## Python Client สำเร็จรูป (narit_client.py)

```python
"""
narit_client.py
Python client สำหรับควบคุม Narit Vending Machine ผ่าน REST API
"""
import time
import requests

class NaritClient:
    def __init__(self, base_url: str = "http://192.168.70.5", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict:
        resp = requests.get(f"{self.base_url}{path}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict = None) -> dict:
        resp = requests.post(f"{self.base_url}{path}", json=json, timeout=self.timeout)
        return resp.json()

    def get_status(self) -> dict:
        """ดึงสถานะทั้งหมดของบอร์ด"""
        return self._get("/api/status")

    def get_slots(self) -> dict:
        """ดึงพิกัดช่องเก็บของทั้งหมด"""
        return self._get("/api/slots")

    def home(self, axis: str = "all") -> dict:
        """Home แกน: 'x', 'y', 'z', หรือ 'all'"""
        return self._post(f"/api/home/{axis}")

    def jog(self, axis: str, distance_mm: float) -> dict:
        """Jog แกน ระยะทาง mm (บวก=หน้า, ลบ=หลัง)"""
        return self._post("/api/jog", {"axis": axis, "distance_mm": distance_mm})

    def stop(self) -> dict:
        """หยุดฉุกเฉิน"""
        return self._post("/api/stop")

    def goto_slot(self, code: str | int) -> dict:
        """เคลื่อนที่ไปยังช่องที่ระบุ (1-30)"""
        return self._post(f"/api/slots/{code}/goto")

    def save_slot(self, code: str | int, x_mm: float, y_mm: float, z_mm: float) -> dict:
        """บันทึกพิกัดช่อง"""
        return self._post(f"/api/slots/{code}", {"x_mm": x_mm, "y_mm": y_mm, "z_mm": z_mm})

    def save_current_to_slot(self, code: str | int) -> dict:
        """บันทึกตำแหน่งปัจจุบันลงช่อง"""
        return self._post(f"/api/slots/{code}/save-current")

    def is_online(self) -> bool:
        """ตรวจสอบว่าบอร์ดออนไลน์อยู่หรือไม่"""
        try:
            self._get("/api/status")
            return True
        except Exception:
            return False


# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    client = NaritClient("http://192.168.70.5")

    # ตรวจสอบการเชื่อมต่อ
    if not client.is_online():
        print("ไม่สามารถเชื่อมต่อกับบอร์ดได้")
        exit(1)

    # ดูสถานะ
    status = client.get_status()
    print("State:", "BUSY" if status["busy"] else "IDLE")

    # Home ทุกแกน
    print("กำลัง Home All...")
    result = client.home("all")
    print("Home OK:", result["ok"])

    # Jog X ไป 20 mm
    result = client.jog("x", 20.0)
    print("Jog OK:", result["ok"])

    # ไปช่องที่ 5
    result = client.goto_slot(5)
    print("Goto Slot 5 OK:", result["ok"])
```

---

## ตาราง HTTP Status Code

| Code | ความหมาย |
|---|---|
| `200` | สำเร็จ |
| `400` | คำสั่งผิดพลาด (เช่น Limit ชน, E-Stop active) |
| `500` | ข้อผิดพลาดภายในเซิร์ฟเวอร์บน Pi |

---

## Error Handling แบบครบถ้วน

```python
import requests

def safe_call(url, method="get", **kwargs):
    try:
        if method == "get":
            resp = requests.get(url, timeout=10, **kwargs)
        else:
            resp = requests.post(url, timeout=30, **kwargs)
        
        data = resp.json()
        
        if resp.status_code == 200 and data.get("ok", True):
            return data
        else:
            print(f"[Error] {data.get('error', 'Unknown error')}")
            return None

    except requests.ConnectionError:
        print("[Error] ไม่สามารถเชื่อมต่อกับบอร์ดได้ — ตรวจสอบเครือข่าย")
    except requests.Timeout:
        print("[Error] Timeout — บอร์ดไม่ตอบสนอง")
    except Exception as e:
        print(f"[Error] {e}")
    return None
```
