# NARIT Vending — Current Handoff

วันที่ส่งต่อ: 3 กันยายน 2026  
อ่านไฟล์นี้ก่อน แล้วอ่าน [ARCHITECTURE_TH.md](ARCHITECTURE_TH.md)

## เป้าหมายงาน

รับช่วงระบบ Vending ที่ใช้ IRIV PiControl + IRIV IO + NUCLEO-F439ZI ให้ถึงขั้น
commission motion อย่างปลอดภัย โดยรักษา HMI/API/Controller architecture ปัจจุบัน
และไม่เริ่มออกแบบใหม่จากศูนย์

## สิ่งที่พร้อมใช้งาน

- HMI/API บน `http://iriv.local/`
- Controller/Web systemd services active
- IRIV IO Modbus TCP online ที่ `10.0.0.10:502`
- Nucleo USB health link online และ LAN `192.168.70.81` ping ได้
- IRIV DI mapping ล่าสุด deploy แล้ว
- E-stop polarity guard deploy แล้ว: polarity ไม่ยืนยันจะ block motion
- STM32 pin source ปรับเป็น PA8/PB0, PA9/PB1, PA5/PB2 แล้ว
- Motion candidate v2 build ผ่าน แต่ยังไม่ flash
- Unit tests ชุด safety/config/link ล่าสุดผ่าน 16 tests

## สิ่งที่ยังไม่พร้อม

- เครื่องอยู่ `E_STOP`; X/Y/Z ยังไม่ Home
- DI10 E-stop polarity ยังไม่ผ่าน two-state commissioning
- 24 V ของ Z/DM542 ยังไม่ถูก safety relay/KM1 ตัดตาม wiring ล่าสุด
- Controller ยังไม่มี production Nucleo motion backend
- Z Home DI6 ยังไม่ได้แยกเข้า homing logic จาก Z Min DI4
- DI7–DI9 ยังไม่มี dispense/product verification sequence
- firmware candidate ยังไม่ผ่าน scope/dummy-load/driver-disconnected test

## กฎบังคับสำหรับผู้รับช่วง

1. ห้ามใช้ `git reset --hard`, `git clean` หรือ checkout ทับ dirty worktree
2. ห้าม flash candidate หรือส่ง `ARM SAFE`/`MOVE` ก่อน production gate ผ่าน
3. ห้ามเอา `NaritVendingV1/narit_vending/nucleo_io.py` มาใช้ เพราะเป็น prototype ที่ไม่ครบ safety
4. ห้ามเปลี่ยน `polarity_verified=false` โดยไม่มีค่า DI10 ตอนกดและปล่อย
5. ห้าม auto-home/move ใน deployment, startup, test หรือ health check
6. ห้ามเปิดเผย `/etc/narit-vending.env` หรือ credential ใด ๆ
7. สำรอง local/remote ก่อนแก้ config, runtime หรือ firmware ทุกครั้ง

## จุดเริ่มงานรอบถัดไป

### A. DI10 commissioning — ทำก่อนและไม่ขยับมอเตอร์

1. ตรวจว่าไม่มี active command และเครื่องอยู่ E_STOP
2. ให้ผู้ปฏิบัติงานปล่อย E-stop อ่าน `io.raw_inputs.DI10`
3. ให้ผู้ปฏิบัติงานกด E-stop อ่านค่าอีกครั้ง
4. ค่าต้องเปลี่ยนคนละสถานะ; ถ้าไม่เปลี่ยนให้ตรวจสาย/relay ห้ามแก้ software ชดเชย
5. ตั้ง `active_state` ให้หมายถึง unsafe และเปลี่ยน `polarity_verified=true`
6. restart services แล้วพิสูจน์ว่ากด E-stop ทำให้ state เป็น E_STOP ทุกครั้ง

### B. Hardwired safety

ให้ช่างไฟแก้ KM1/safety enable path ให้หยุด X/Y/Z ครบ และทดสอบโดยไม่พึ่ง Pi/Nucleo
ก่อนทำ firmware scope test

### C. Software integration

สร้าง production Nucleo backend ใหม่ภายใต้ Controller owner เดียว:

- serial transaction lock และ strict JSON/protocol validation
- state: disconnected/disarmed/armed/moving/fault
- SAFE heartbeat มาจาก fresh IRIV IO state เท่านั้น
- communication/polarity/limit fault ส่ง UNSAFE/STOP ทันที
- no automatic re-arm หลัง reconnect/reset
- bounds validation ซ้ำทั้ง Pi และ STM32
- status/audit/command correlation ผ่าน CommandBus
- unit tests ใช้ fake serial เท่านั้น

## Verification baseline

```powershell
cd C:\Users\Naruebest\OneDrive\Documents\NaritVending
.\.venv\Scripts\python.exe -m unittest tests.test_iriv_io tests.test_config_foundation tests.test_nucleo -v
ssh pi@iriv.local "systemctl is-active narit-vending-controller-iriv.service narit-vending-web-iriv.service"
ssh pi@iriv.local "curl -fsS http://127.0.0.1/api/status"
ssh pi@iriv.local "curl -fsS http://127.0.0.1/health/ready"
ssh pi@iriv.local "ping -c 2 192.168.70.81"
```

Expected baseline:

- services `active`
- IRIV IO และ Nucleo `communication_ok=true`
- Nucleo protocol `1`, `safe=true`
- `machine_state=E_STOP`, `machine_ready=false`
- DI0–DI9 OFF และ DI10 ON ตาม snapshot ล่าสุด แต่อย่าใช้ค่าครั้งเดียวตัดสิน polarity

## ไฟล์หลัก

| File | ใช้สำหรับ |
|---|---|
| `docs/ARCHITECTURE_TH.md` | architecture, state, safety gate, deployment |
| `docs/IRIV_WIRING_TH.md` | DI/DO/network/wiring summary |
| `docs/STM32_NMOS_CURRENT_WIRING_TH.md` | STM32 connector และ NMOS details |
| `hardware_config.iriv.json` | source config ระดับ repository |
| `NaritVendingV1/hardware_config.iriv.json` | deployable IRIV profile |
| `narit_vending/iriv_io.py` | Modbus backend และ polarity guard |
| `narit_vending/nucleo.py` | safe health-only link |
| `NaritVendingV1/stm32/Src/nucleo_motion.c` | timer/STEP/DIR/watchdog source |
| `NaritVendingV1/stm32/Src/nucleo_serial_link.c` | protocol v2 source |
| `firmware/nucleo_f439zi/README.md` | image identity/hash/status |

## Backups และ artifacts

| รายการ | ตำแหน่ง |
|---|---|
| Remote config backup ก่อน DI remap | `/home/admin/NaritVending_backups/config_20260903_0413/` |
| Full Nucleo flash backup | `backups/nucleo/nucleo_f439zi_flash_before_serial_20260902_093645.bin` |
| Full flash backup บน Pi | `/home/admin/NaritVending_backups/nucleo/nucleo_f439zi_flash_before_serial_20260902_093645.bin` |
| Cube source backup ก่อน motion build | `backups/nucleo/cube_project_before_motion_20260903_0415/` |
| Motion candidate | `firmware/nucleo_f439zi/nucleo_f439zi_motion_candidate_v2.bin` |

Hashes:

```text
Full flash backup:
8af1dd070799844271c25ea3206333722750606e8c2fbdb984c26e5e26e4aef7

Deployed safe-link image:
d1e82b1504a341c833fb9b2ac656db85e0901158683035485e7f6bcab34dfda8

Unflashed motion candidate v2:
7d0575a0a32cf320cd30547a1f8bd8044735db32dd6bf32114a41fa116270944
```

## Git/worktree note

worktree มี modified และ untracked files จำนวนมากจากงาน HMI, controller, health,
Nucleo, wiring และ configuration อย่าเหมารวมว่าเป็นไฟล์ขยะ และอย่า commit ทั้งหมดก้อนเดียว
ให้ review diff แล้วแบ่งอย่างน้อยเป็น:

1. controller/health/HMI changes
2. IRIV IO mapping และ polarity guard
3. Nucleo health link
4. STM32 motion candidate
5. wiring/architecture/handoff documentation

ก่อน commit ให้ตรวจ profile copies (`root`, `NaritVendingV1`, `NaritVendingMOCKUP`)
ว่าตรงตาม scope และไม่มี config ของคนละเครื่องปะปนกัน

## Definition of done สำหรับ motion commissioning

- hardwired E-stop หยุด driver ทั้งสามแกนโดยไม่พึ่ง software
- DI10, limit หกตัว, Z Home และ product sensors มี polarity record
- USB disconnect/watchdog/STM32 reset ทำให้ disarm และไม่ auto-resume
- pulse count/frequency/direction ผ่าน scope test
- 10 mm low-speed test ตรงทิศและระยะทุกแกน
- physical limit หยุดได้ระหว่างเคลื่อน
- Home, Jog, Stop, E-stop และ power-cycle tests ผ่าน
- automatic slot/dispense เปิดหลัง manual acceptance เท่านั้น

## Prompt สำหรับส่งต่อให้ AI/วิศวกร

```text
อ่าน docs/HANDOFF_CURRENT_TH.md, docs/ARCHITECTURE_TH.md,
docs/IRIV_WIRING_TH.md และ docs/STM32_NMOS_CURRENT_WIRING_TH.md ให้ครบก่อนแก้ไข
จากนั้นตรวจ git status/diff และสถานะ live แบบ read-only ห้าม discard งานเดิม
เริ่มจาก DI10 two-state commissioning โดยไม่สั่งมอเตอร์ แล้วแก้ hardwired safety ของ Z
ก่อนออกแบบ production Nucleo motion backend ผ่าน CommandBus/SafetyInterlock
ห้าม flash, ARM, HOME, JOG หรือ MOVE จนกว่า safety gate ใน ARCHITECTURE_TH.md จะผ่าน
```

