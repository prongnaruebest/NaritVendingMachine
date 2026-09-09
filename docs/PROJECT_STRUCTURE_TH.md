# โครงสร้างโปรเจกต์ NaritVendingMachine

Repository นี้แยก Web process ออกจาก Controller process เพื่อให้ browser หรือ Flask ไม่สามารถครอบครอง GPIO/pulse และไม่ลด safety เมื่อหน้าเว็บ reload หรือเกิด JavaScript error

```text
narit_vending/
  controller/          Controller process, CommandBus, Safety, sequences
    handlers/          ตัวแปลง CommandEnvelope เป็น service action
    demo_service.py    Demo state, bounded sampling และ SQLite audit
  web/                 Flask web process และ IPC client
    routes/            Status, commands, configuration
  shared/              CommandEnvelope, MachineSnapshot, IPC protocol
  static/              API client, shared store, router/page lifecycle, app rendering และ CSS
  templates/           HMI HTML
  motion.py            Axis/MotionController และ homing
  nucleo.py            USB Serial handshake, heartbeat, STEP command และ transport capability
  iriv_io.py           Modbus TCP DI/DO แบบ fail-safe
tests/                 Mock-hardware automated tests
firmware/              STM32 source/artifacts
deploy/                systemd services
scripts/               validation, backup และ deploy
docs/                  คู่มือและสถาปัตยกรรม
machine_config*.json   Machine coordinates, axes และ slots
hardware_config*.json  I/O, USB และ hardware mapping
demo_results.sqlite3   Runtime Demo sessions บนเครื่อง Deploy
controller_history.sqlite3   Command audit และ idempotency บนเครื่อง Deploy
```

## Data flow

```text
Browser → Flask → CommandEnvelope → IPC → CommandBus → SafetyInterlock
                                               ↓
                                Motion/Demo Sequence → NUCLEO USB → STEP/DIR

IRIV DI10/Limits/Alarms → IRIV Backend → Controller Safety → STOP/DISARM
                                                      ↓
                                               MachineSnapshot → HMI
```

Controller เป็น machine authority ส่วน Browser/localStorage เก็บได้เฉพาะ preference ที่ไม่ใช่ safety authority เช่นความเร็วที่เลือกไว้ UI ทุก motion command ต้องถูกตรวจซ้ำโดย Controller

## Process ownership

- Web: render, validate input shape, ส่งคำขอ, แสดงผล
- Controller: motion, safety, GPIO, IRIV I/O, NUCLEO, MQTT command และ Demo
- NUCLEO: pulse timer, armed/disarmed state และ USB watchdog
- SQLite: Demo audit; Web อ่านผ่าน Controller IPC ไม่เปิดไฟล์โดยตรง

## เส้นทางคำสั่ง

```text
UI control
  → Flask route ตรวจชนิดข้อมูล
  → CommandEnvelope
  → Unix IPC
  → CommandBus serialize/priority
  → SafetyInterlock
  → MotionService/SequenceService
  → NucleoLink USB Serial
  → STM32 timer STEP/DIR
```

STOP และ E-Stop มี priority สูงสุด คำสั่งปกติจะถูก Controller ตรวจซ้ำแม้ UI แสดงว่าพร้อม

## Long-move segmentation

`AxisController` รับแผนการเคลื่อนที่เต็มระยะ ส่วน `NucleoLink` เปิดเผย `max_move_steps` ของ firmware การเคลื่อนที่ที่ยาวกว่าหนึ่ง frame จะถูกแบ่งโดย Controller เช่น 44,000 pulses ที่ limit 10,000 จะเป็น 10,000 + 10,000 + 10,000 + 10,000 + 4,000

หลักสำคัญ:

- ใช้กับ X/Y/Z และทุก caller ที่ผ่าน `_execute_plan`
- ตรวจ safety ระหว่าง segment
- อัปเดต position หลัง segment ที่สำเร็จ
- ห้าม UI แบ่ง pulse เอง
- Manual Commissioning pulse-count ยังคงมีขอบเขตของ workflow แยกต่างหาก

## Shared UI state

`static/machine-store.js` เป็น shared browser state สำหรับ selected slot, speed X/Y/Z, position, homed state, connection, alarm, active command และ validation/arm state ส่วน `static/api-client.js` รับผิดชอบ HTTP/timeout/response parsing, `static/router.js` รับผิดชอบ hash/deep-link, `static/page-controllers.js` จำกัดอายุ timer/listener เฉพาะหน้าที่เปิด และ `static/app.js` รับผิดชอบ interaction/rendering ค่าใน localStorage เป็น preference เท่านั้น ไม่ใช่ machine authority

เมื่อ speed หรือ target เปลี่ยน:

- Direct Jog/Min/Max ตรวจ readiness ใหม่และใช้ค่าถัดไป
- GOTO validation/preview/arm เดิมถูก invalidate
- คำสั่งที่กำลังทำงานไม่ถูก retime โดย browser

## I/O diagnostics telemetry

`iriv_io.py` เก็บ raw transition, logical transition, active duration และจำนวนสัญญาณสั้นที่ debounce กรองออกต่อ input โดยส่งผ่าน MachineSnapshot/API ให้ HMI แสดงผล การนับนี้อยู่ในหน่วยความจำของ Controller และ reset เมื่อ service restart; safety decision ยังคงใช้ logical input หลัง polarity/debounce และไม่ได้ย้าย authority ไปไว้ใน browser

## Configuration ownership

- `machine_config.iriv.json`: axes, travel, speed, homing และ slots สำหรับ IRIV runtime
- `hardware_config.iriv.json`: IRIV Modbus, USB path, protocol และ I/O mapping
- Controller โหลดและ validate configuration ก่อนใช้งาน
- ก่อน deploy configuration ต้อง backup และตรวจ effective revision

## การทดสอบ

- `tests/` ใช้ mock hardware และต้องไม่ส่ง motion จริง
- Frontend tests ตรวจ navigation, shared speed state, syntax และ responsive contracts
- Motion tests ตรวจ conversion, safety, homing และ USB segmentation
- การผ่าน automated tests ไม่ยืนยันกลไกจริง, polarity, ระยะ travel หรือความเร็วสูงสุด
