# คู่มือทดสอบและวิเคราะห์ปัญหา

เอกสารนี้ใช้กับ NaritVendingMachine IRIV V1 สำหรับค้นหาสาเหตุโดยไม่ลด safety และไม่สั่ง
มอเตอร์จาก automated test การทดสอบที่ทำให้เครื่องเคลื่อนต้องมีผู้ควบคุมอยู่หน้าเครื่องและยืนยันพื้นที่ปลอดภัย

## 1. หลักการสำคัญ

- เส้นทางคำสั่งคือ Web → Controller IPC → Safety/Policy → NUCLEO → Drive → Motor
- IRIV I/O และ PiControl local I/O เป็น feedback/interlock ไม่ใช่แหล่งกำเนิด pulse
- E-Stop, Stop, ALM, communication fault และ watchdog ห้าม bypass
- ห้ามกด Reset/Enable/Home ซ้ำต่อเนื่องโดยยังไม่อ่าน `last_error`, inhibit reason และ Event Log
- ค่าตำแหน่งหลัง power loss, interrupted motion หรือ Raw Jog อาจเชื่อถือไม่ได้ ให้ Home ใหม่
- PEND คือ in-position feedback; ALM คือ drive fault ทั้งสองสัญญาณห้ามตีความสลับกัน

## 2. ตรวจระบบแบบ read-only

จากเครื่องที่เข้าถึง HMI ได้ ใช้ PowerShell โดยเปลี่ยน host เมื่อจำเป็น:

```powershell
Invoke-RestMethod http://192.168.70.80/health/live
Invoke-RestMethod http://192.168.70.80/health/ready
Invoke-RestMethod http://192.168.70.80/api/status
Invoke-RestMethod http://192.168.70.80/api/io/status
```

คำสั่งเหล่านี้ต้องไม่สร้าง motion:

- `/health/live` ยืนยันเฉพาะ Web process
- `/health/ready` แยก `service_ready` ออกจาก `machine_ready`
- `/api/status` แสดง Controller snapshot, active command, Home, NUCLEO และ error ล่าสุด
- `/api/io/status` แสดง IRIV/PiControl inputs พร้อม stale/communication state

ห้ามสรุปว่า hardware พร้อมจาก HTTP 200 ของ `/health/live` เพียงรายการเดียว และ HTTP 503 จาก
`/health/ready` อาจหมายถึง dependency ไม่พร้อม ไม่ได้แปลว่า Web process ล่ม

## 3. ลำดับตรวจเมื่อคำสั่งไม่ทำงาน

1. กด Stop หากมีการเคลื่อนผิดปกติ แล้วรอ `busy=false`
2. ตรวจ Controller online, NUCLEO Safe Link และ IRIV/PiControl communication แยกกัน
3. ตรวจ E-Stop/DI10, software Stop latch, X/Y ALM และ active alarms
4. ตรวจ `motion_enabled`, `configuration_restart_required` และ Home ของแกนที่จะใช้
5. ตรวจ sensor เฉพาะทิศ: sensor ที่ active ต้องห้ามวิ่งเข้าหา แต่ต้องอนุญาตให้ถอยออกเมื่อ safety อื่น clear
6. อ่าน `last_error`, operation phase และ Event Log ก่อน Reset
7. แก้ต้นเหตุ แล้ว Reset Alarms → Enable Motion → Home ใหม่เมื่อ reference สูญหาย

## 4. ตารางวิเคราะห์อาการ

| อาการ | จุดตรวจแรก | แนวทาง |
|---|---|---|
| หน้าเว็บขึ้น Controller Offline | `/health/live`, `/health/ready`, Controller service/IPC | แยก frontend render error ออกจาก Controller failure ห้าม refresh แล้วสั่งซ้ำทันที |
| NUCLEO Offline/Safe Link หาย | USB by-id path, baud, handshake, protocol, heartbeat | หยุด motion; แก้ link และ handshake ก่อน Enable/Home |
| IRIV I/O Offline หรือ stale | LAN, Modbus host/port/unit, timestamp | ถือ safety input ไม่ปลอดภัยและห้าม motion จนข้อมูล fresh |
| Home ไม่เริ่ม | motion enabled, DI10, ALM, USB, sensor stuck | ตรวจ polarity และ sensor จริง ห้ามเพิ่ม timeoutเพื่อกลบ sensor fault |
| Home หยุดก่อน sensor | operation phase, watchdog, ALM, communication, Stop | ระบุเหตุที่หยุดก่อนเปลี่ยน speed/timeout |
| Home oscillation ตอน latch | latch speed, backoff/release, sensor bounce | ใช้ latch speed 5 mm/s ตาม config X/Y และตรวจ mounting/debounce |
| Jog กดค้างแล้วกระตุก | browser hold events, segment continuity, USB acknowledgements | ตรวจว่ามี command boundary/Stop ทุกช่วงหรือไม่ ห้ามเพิ่ม segment แบบสุ่ม |
| Z Jog ไม่ได้หลัง Home | Z Home, Min/Max polarity, position/travel 0–160 mm, stop latch | อนุญาตเฉพาะทิศออกจาก active limitและตรวจ 9 pulse/mm |
| อยู่ Max แล้วสั่งกลับไม่ได้ | directional limit policy, busy/command completion, stale latch | Max ต้อง block เฉพาะทิศ Max; ทิศ Min ต้องพร้อมเมื่อ interlock อื่น clear |
| Min/Max ไปไม่ถึง sensor | physical-seek command, missing-sensor watchdog, ALM/USB | Min/Max ต้องหยุดจาก physical sensor ไม่ใช่ software margin แต่ watchdog ยังต้องทำงาน |
| เปลี่ยน speed แล้วสั่งไม่ได้ | command type และ validation token | GOTO/Slot ต้อง Validate/Arm ใหม่; Jog/Min-Max ไม่ควรค้าง token เก่า |
| เลือก Slot แล้วไม่เคลื่อน | slot validity, selected slot sync, Home, enabled, busy | Save ไม่เท่ากับ Go To; ตรวจ target และ Controller rejection |
| Z เท่าเดิมแต่เปลี่ยน X/Y | moving-axis selection/zero-distance axis | Z zero-distance ต้องไม่ทำให้ coordinated command Failed |
| Drive ALM ค้าง | DI0 `X_DRIVE_ALM`, DI1 `Y_DRIVE_ALM`, drive LED/code | แก้ encoder/motor/power/mechanical fault ก่อน power reset |
| Reset Drives ไม่สำเร็จ | DO0 command, KM1 feedback DI10, contactor voltage/contact | ห้ามวน power reset; ยืนยันไฟตกจริงและ feedback เปลี่ยนตามลำดับ |
| PEND timeout | DI2 X_PEND/DI3 Y_PEND polarity, transition, polling | คง advisory จน commissioning; อย่าใช้ PEND เป็น ALM |

## 5. Home troubleshooting

สถานะที่คาดหวังต่อแกนคือ `SEARCHING → SENSOR FOUND → BACK OFF → LATCH APPROACH →
ZERO SET → OFFSET MOVE → COMPLETE` หาก FAILED ให้บันทึก phase, sensor, time และ error

- sensor active ก่อนเริ่ม: ต้องตรวจ stuck-active/release behavior ไม่ควรวิ่งค้นหาต่ออย่างไม่จำกัด
- search ไม่ใช้ software position limit แต่ต้องมี time watchdog และ communication watchdog
- แกนที่พบ sensor ต้องหยุดเฉพาะแกนนั้น; global safety fault ต้องหยุดทุกแกน
- `is_homed=true` ได้เมื่อ zero และ offset move สำเร็จเท่านั้น
- Protocol v2 ใช้ sequential fallback; parallel Home All เปิดได้เมื่อ handshake ยืนยัน v3

## 6. Limit และ directional recovery

Physical Min/Max seek อนุญาตให้ค้นหานอก software coordinate ที่คลาดเคลื่อนได้ แต่ยังคง E-Stop,
Stop, ALM, USB/IRIV fault และ missing-sensor watchdog เมื่อ sensor ทำงาน:

- ห้ามคำสั่งที่วิ่งเข้า sensor มากขึ้น
- อนุญาตคำสั่งที่วิ่งออกจาก sensor
- ปิด active command/busy ให้สมบูรณ์ ไม่ทิ้ง stop latch จาก completion ปกติ
- หาก reference ไม่แน่นอนหลัง interruption ให้ล้าง Homed และ Home ใหม่

## 7. Drive ALM, KM1 และ PEND

- PiControl DI0 = `X_DRIVE_ALM`, DI1 = `Y_DRIVE_ALM`; ALM active ต้อง inhibit/stop motion
- PiControl DI2 = `X_PEND`, DI3 = `Y_PEND`; ใช้ยืนยัน settled เมื่อ commissioning แล้ว
- PiControl DO0 สั่ง KM1 drive-power path ของ X/Y ตามวงจรจริง
- IRIV I/O DI10 = `KM1_FEEDBACK / E-Stop`; active หรือ stale ต้อง fail-safe stop/disarm
- Power reset ต้องเป็น bounded Controller command: Disable → Cut Power → ยืนยัน feedback → dwell →
  Restore Power → ยืนยัน feedback → ตรวจ ALM → คง Motion Disabled
- หาก ALM ยังอยู่ ห้าม reset ซ้ำอัตโนมัติ ให้ตรวจ drive fault code, encoder, motor cable, load และ supply
- PEND ยังต้อง `commissioned=false` จนวัด polarity/transition/settle time ครบ

ข้อจำกัดสำคัญ: wiring ล่าสุดระบุ KM1 ตัด 60 V ของ X/Y แต่ Z/DM542 24 V ยังไม่ผ่าน safety
contactor จึงห้ามถือ software pulse inhibit ของ Z เป็น emergency-stop layer ที่เทียบเท่าฮาร์ดแวร์

## 8. Slot และ Demo Sampling

ก่อน Go To Slot ตรวจ selected slot, saved XYZ, bounds, Home ทุกแกน, motion enabled และ speed กลาง
ถ้าแกนหนึ่งมี delta เป็นศูนย์ ให้ planner ตัดแกนนั้นออกจาก active axes โดยไม่ทำให้คำสั่งทั้งหมดล้มเหลว

Demo Sampling ต้อง bounded ด้วยจำนวน move และ duration ที่ Controller คำนวณ/บังคับ มี Stop, ไม่ Resume
เองหลัง restart และไม่ Dispense ทุกผลต้องเก็บ session, requested, attempted, passed, failed, skipped,
stopped, target, result, timestamps และ error เพื่อดูย้อนหลัง/Export CSV

## 9. Automated verification (ไม่มี motion จริง)

```powershell
$taskPython = "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $taskPython scripts\quality_gate.py
```

เกณฑ์ผ่านคือทุก gate ผ่าน และบรรทัดท้ายยืนยันว่าไม่ได้ start server, Controller, GPIO, serial transport
หรือ motion command ชุดทดสอบต้องใช้ fake/mock hardware เท่านั้น

## 10. บันทึกหลักฐานก่อนแก้ค่า

เก็บเวลา, configuration revision, firmware/protocol, current/target XYZ, sensor raw/logical/stale,
ALM/PEND/DI10, command ID/type/phase, speed/pulse rate, error และ Event Log ที่เกี่ยวข้อง ห้ามเปลี่ยน
หลาย parameter พร้อมกัน เพราะจะย้อนหาสาเหตุไม่ได้

## 11. เกณฑ์หยุดทดสอบทันที

- การเคลื่อนผิดทิศ, ชน, oscillation หรือเสียงผิดปกติ
- E-Stop/Stop/ALM/communication fault
- sensor state ไม่ตรงของจริง
- ตำแหน่งหรือ pulse/mm ไม่สอดคล้องกับระยะภายนอก
- KM1 feedback ไม่เปลี่ยนตามคำสั่ง หรือ ALM ไม่หายหลังแก้ต้นเหตุหนึ่งรอบ

หลังหยุด ห้ามสั่งต่อโดยอาศัยค่าตำแหน่งเดิม ให้ตรวจสาเหตุและ Home ใหม่เมื่อปลอดภัย
