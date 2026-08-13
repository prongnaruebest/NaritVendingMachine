# Narit Vending Machine — Architecture (v2.0)

เอกสารนี้อธิบายโครงสร้าง การทำงาน และ flowchart ของระบบ `Narit Vending Machine` ฉบับสมบูรณ์ อัปเดตตามสถานะโค้ดจริงล่าสุด

---

## สถานะระบบปัจจุบัน (Current Production Architecture — 2026-07)

> ส่วนนี้เป็นแหล่งอ้างอิงหลักสำหรับระบบที่ deploy ใช้งานอยู่จริง และแทนที่คำอธิบายแบบ single-process หรือ MQTT topic รุ่นเก่าที่ปรากฏในหัวข้อถัดไป

### โครงสร้างการทำงานจริง

```text
Operator Browser → Web Process (Flask :80) → Unix IPC → Controller Process → GPIO / Motion
                                                       └→ MQTT Broker
```

- **Web Process** ให้บริการ HMI, static assets และ HTTP API เท่านั้น; ไม่เปิด GPIO และไม่สร้าง MQTT client
- **Controller Process** เป็นเจ้าของ MotionService, state machine, command bus, safety interlock, GPIO และ MQTT client เพียงตัวเดียว
- Web ติดต่อ Controller ผ่าน `/run/narit-vending/ctrl.sock`; หาก Controller ไม่พร้อม คำสั่งต้อง fail-safe ด้วย HTTP 503
- การ restart Web ไม่หยุด motion หรือ MQTT; การ restart Controller เป็นการหยุดการควบคุมจริงและ presence จะ offline ชั่วคราว

### Safety boundary และคำสั่งเคลื่อนที่

Browser, REST API และ MQTT ไม่สามารถข้าม Controller ได้ ทุกคำสั่งต้องผ่านการตรวจ E-Stop, software stop, alarm, limit switch, homing, travel boundary และ target/slot validity ที่ Controller ก่อนสั่ง GPIO

คำสั่งไปยังพิกัดใช้ `Validate → Arm → Execute`; การเปลี่ยนพิกัดหรือความเร็วหลัง validate ทำให้ arm state ใช้ไม่ได้. Go To Slot ยก Safe Z ก่อนเคลื่อน X/Y และ Dispense ใช้ได้เมื่อยืนยันว่า gantry อยู่ที่ slot ถูกต้องแล้วเท่านั้น

### MQTT contract ปัจจุบัน

| ทิศทาง | Topic | กติกา |
|---|---|---|
| Subscribe | `cabinet/{cabinet_id}/command` | รองรับ action `release` เท่านั้น; ต้องมี `request_id` และ `slot`; ปฏิเสธ request หมดอายุ/ซ้ำ/ไม่ถูกต้อง |
| Publish | `cabinet/{cabinet_id}/scan`, `/status`, `/presence` | รายงาน phase และผลสำเร็จ/ล้มเหลว; presence เป็น QoS 1 retained พร้อม Last Will offline |

MQTT ใช้ client ID เฉพาะ cabinet และ `clean_session=false`; reconnect backoff 4–60 วินาที. MQTT Monitor และ `/api/mqtt/status` แสดงเฉพาะ telemetry ที่ sanitize แล้ว ห้ามเปิดเผย password, token หรือ secret

### Configuration, observability และ deployment

- `machine_config.json`: travel, steps/mm, Safe Z, homing, slot XYZ
- `hardware_config.json`: GPIO และ communication
- การบันทึก config ที่ผ่าน validation สร้าง revision และ backup ใต้ `backups/config/`
- `/health/live` ตรวจ Web, `/health/ready` แยก service-ready ออกจาก machine-ready, `/api/mqtt/status` แสดงสถานะ MQTT ที่ sanitize แล้ว
- งาน HMI ใช้ Web-only deployment เพื่อไม่ตัด Controller/MQTT; Full deployment ใช้เมื่อแก้ controller, motion, GPIO, MQTT runtime หรือ dependency

### Roadmap ที่ยังไม่ดำเนินการ (รวมจากเอกสาร Proposal)

รายการต่อไปเป็นแผนพัฒนา ไม่ใช่ความสามารถที่เปิดใช้บน production ในปัจจุบัน:

1. Persistent audit/event store เพื่อเก็บ event, command ID และผลการทำงานเกินกว่า in-memory ล่าสุด
2. Authentication/RBAC สำหรับแยก Viewer, Operator, Engineer และ Admin
3. MQTT TLS พร้อม CA/client certificate และ broker hardening
4. ลดสิทธิ์ systemd จาก root หลังยืนยัน GPIO group/permission บน Pi
5. Full deployment แบบ atomic release/health check/rollback
6. เพิ่ม Pi integration tests สำหรับ cold boot, network loss, E-Stop, limit, configuration rollback และ MQTT reconnect

ทุก roadmap ต้องรักษา two-process ownership, one-MQTT-client invariant, API compatibility และ safety gate ที่ Controller เป็นผู้ตัดสินใจเสมอ

### Actual Running Architecture (โครงสร้างที่ใช้งานจริง)

โครงสร้างด้านล่างคือไฟล์ที่มีอยู่และทำงานร่วมกันในระบบปัจจุบัน ไม่ใช่ proposal:

```text
narit_vending/
├── controller/                         # Controller process: เจ้าของ safety และ motion command
│   ├── __main__.py                      # เริ่ม MotionService, SequenceService, CommandBus, StateMachine และ IPC server
│   ├── command_bus.py                   # จุดรวมทุก command; single-flight lock + SafetyInterlock
│   ├── safety.py                        # ตรวจ E-Stop, stop latch, busy, homing, limits, motor test
│   ├── state_machine.py                 # สถานะ READY/NOT_READY/HOMING/MOVING/ALARM/E_STOP
│   ├── server.py                        # Unix IPC server ที่ /run/narit-vending/ctrl.sock
│   ├── sequence_service.py              # ลำดับ X → Y → Z → hold → Home Z → Y → X
│   └── handlers/
│       ├── home.py                      # HOME_AXIS / HOME_ALL
│       ├── jog.py                       # JOG
│       ├── move.py                      # MOVE_TO / MOVE_TO_SLOT / DISPENSE / validation
│       ├── sequence.py                  # RUN_SLOT_SEQUENCE → SequenceService
│       ├── stop.py                      # STOP / CONTROLLED_STOP / CLEAR_ALARM
│       └── motor_test.py                # motor test แบบแยกจาก normal motion
├── shared/                              # โครงสร้างข้อมูลระหว่าง Web และ Controller
│   ├── commands.py                      # CommandEnvelope และ CommandResult
│   ├── ipc_protocol.py                  # ชื่อ method/รูปแบบ IPC request-response
│   └── snapshot.py                      # MachineSnapshot, AxisSnapshot ที่ปลอดภัยต่อ JSON
├── web/                                 # Web process: Flask HMI/API facade, ไม่จับ GPIO
│   ├── __main__.py                      # เริ่ม Web service บน port 80
│   ├── app.py                           # Flask app factory และ register routes
│   ├── ipc_client.py                    # ControllerClient ส่งคำขอเข้า Unix socket
│   └── routes/                          # status, commands, slots, config, health
├── motion.py                             # MotionService, GPIO, axis/slot/home/move implementation
├── mqtt_service.py                       # MQTT client ที่ Controller เป็นเจ้าของเพียงตัวเดียว
├── webapp.py                             # MotionService compatibility adapter และ state สำหรับ HMI
├── config_foundation.py                  # validate, revision และ backup configuration
├── static/app.js + static/style.css      # browser HMI state/rendering
└── templates/index.html                  # HMI page shell
```

#### สิ่งที่เกิดขึ้นจริงเมื่อเปิดหน้า HMI

1. Browser โหลด `templates/index.html`, `static/app.js` และ `static/style.css` จาก **Web process**
2. `app.js` polling API เพื่อขอ machine snapshot และอัปเดต Axis, Alarm, Slot, MQTT และ Event History
3. Flask route ใน `web/routes/` ไม่เรียก GPIO; route ใช้ `web/ipc_client.py` ส่ง request ไป `controller/server.py`
4. IPC server ส่ง CommandEnvelope เข้า `controller/command_bus.py`
5. CommandBus เรียก `controller/safety.py`; ถ้า E-Stop/alarm/stop/homing/limit/busy ไม่ผ่าน จะคืน rejection โดยไม่เรียก motor
6. เมื่อผ่าน safety handler ใน `controller/handlers/` จึงเรียก `motion.py` เพื่อขับ GPIO ของ X/Y/Z
7. Controller สร้าง MachineSnapshot แล้วส่งกลับผ่าน IPC → Flask → Browser เพื่อแสดงผลเดียวกับที่ใช้ตัดสิน safety

#### สิ่งที่เกิดขึ้นจริงเมื่อ MQTT รับคำสั่ง

1. `controller/__main__.py` เริ่ม `mqtt_service.py` ภายใน **Controller process เท่านั้น**
2. MQTT client subscribe `cabinet/{cabinet_id}/command` และตรวจ `action=release`, `request_id`, `slot`, expiry และ duplicate request
3. MQTT แปลง `release` เป็น CommandEnvelope `RUN_SLOT_SEQUENCE` เพียงหนึ่งคำสั่ง โดยคง `request_id` เป็น idempotency key แล้วส่งเข้า `CommandBus.submit`
4. CommandBus/SafetyInterlock ตรวจ safety ก่อน `handlers/sequence.py` เรียก `SequenceService`; MQTT, Web และ Browser ไม่สามารถเรียก GPIO หรือ AxisController โดยตรง
5. SequenceService ทำตามลำดับ `Move X → Move Y → Move Z → verify target → hold 3 วินาที → Home Z → Home Y → Home X → verify home`; หากขั้นตอนใดผิดพลาดจะยกเลิกขั้นตอนที่เหลือ
6. `motion.py`/AxisController เป็นเจ้าของ GPIO และตรวจ E-Stop, stop latch, limit และ travel boundary ระหว่างการเคลื่อนของทุกแกน
7. Controller publish `/presence`, `/status` และ `/scan`; Web แสดง MQTT Monitor โดยอ่าน telemetry ผ่าน IPC ไม่ได้เชื่อม broker เอง

#### Slot Sequence boundary ที่ใช้งานจริง

| ชั้น | ไฟล์ | หน้าที่ |
|---|---|---|
| HTTP/HMI | `web/routes/commands.py`, `static/app.js` | เลือก Go To ปกติหรือ Sequence Mode และส่ง command ผ่าน IPC เท่านั้น |
| MQTT | `mqtt_service.py` | ตรวจ payload/expiry/idempotency, สร้าง `RUN_SLOT_SEQUENCE`, publish phase/final status |
| Controller | `controller/command_bus.py`, `controller/handlers/sequence.py` | single-flight lock, SafetyInterlock และส่งต่อให้ SequenceService |
| Sequence | `controller/sequence_service.py` | เป็นเจ้าของลำดับขั้นตอนและ phase; ไม่จับ GPIO |
| Hardware | `motion.py` | AxisController, GPIO pulse, position และ safety guard ระหว่างการเคลื่อน |

#### Process และ systemd ที่ทำงานบน Pi

- `narit-vending-controller.service` รัน `python -m narit_vending.controller` และเป็น owner ของ GPIO/MQTT
- `narit-vending-web.service` รัน `python -m narit_vending.web --port 80` และต้องใช้ Controller IPC
- Web-only deployment ส่งเฉพาะ `static/` และ `templates/` แล้ว restart Web; MQTT จึงไม่หลุด
- Full deployment restart Controller และ Web; presence offline ชั่วคราวเป็นสถานะจริงระหว่าง Controller restart

### สรุปสำหรับการพรีเซนต์ (Engineering Presentation Summary)

**ปัญหาที่ architecture นี้แก้:** ระบบควบคุม gantry มีช่องทางสั่งงานหลายทาง (HMI และ MQTT) แต่การเคลื่อนที่ต้องมีเจ้าของเพียงหนึ่งเดียว เพื่อไม่ให้ Web, browser หรือ network message ข้าม interlock แล้วสั่ง GPIO ได้โดยตรง

**คำตอบของระบบ:** แยกเป็น 2 processes ชัดเจน — Web เป็นเพียงหน้าจอและ API facade; Controller เป็น authority เดียวของ CommandBus, SafetyInterlock, Motion/GPIO และ MQTT. ดังนั้นไม่ว่าคำสั่งจะมาจาก HMI หรือ MQTT จะรวมที่ Controller แล้วผ่าน safety gate เดียวกันก่อนถึง hardware

| ประเด็นที่จะสื่อ | หลักฐานในระบบที่รันจริง | ผลต่อการปฏิบัติงาน |
|---|---|---|
| ไม่มีทางลัดถึงมอเตอร์ | Web ใช้ Unix IPC และ MQTT สร้าง `CommandEnvelope` เข้า `CommandBus` | คำสั่งที่ไม่ผ่าน safety ไม่สร้าง GPIO pulse |
| ป้องกันคำสั่ง motion ซ้อนกัน | `CommandBus` ใช้ single-flight dispatch และตรวจ busy | ลดความเสี่ยงจาก HMI/MQTT สั่งพร้อมกัน |
| ป้องกันซ้ำจาก network | MQTT ใช้ `request_id` เป็น idempotency key และตรวจ expiry | retry message ไม่ทำให้ sequence เดิมวิ่งซ้ำ |
| ตรวจทั้งก่อนและระหว่างเคลื่อน | SafetyInterlock ตรวจ readiness ก่อนเริ่ม; `AxisController` ตรวจ E-Stop/stop/limit/travel ทุกแกน | safety ยังทำงานหาก state เปลี่ยนขณะกำลังเคลื่อน |
| แยก UI deployment จาก control | Web-only deployment restart เฉพาะ Web | ปรับ HMI โดยไม่ทำให้ MQTT หรือ Controller หลุด |

### เส้นทางคำสั่ง 3 แบบที่ต้องแยกในการนำเสนอ

| การใช้งาน | จุดเริ่ม | Command ที่ Controller ได้ | ลำดับการเคลื่อน | ผลลัพธ์ |
|---|---|---|---|---|
| Go To Slot ปกติ | HMI, Sequence Mode ปิด | `MOVE_TO_SLOT` ตาม API เดิม | Safe Z → X/Y → Z target | คง gantry ไว้ที่ slot เพื่อรอ Dispense; Dispense เป็นคำสั่งแยกและต้อง verify position |
| Slot Sequence Mode | HMI, Sequence Mode เปิด | `RUN_SLOT_SEQUENCE` ผ่าน IPC | X → Y → Z → verify → hold 3 s → Home Z → Home Y → Home X | ส่งผล target/home verification กลับ HMI |
| MQTT `release` | `cabinet/{cabinet_id}/command` | `RUN_SLOT_SEQUENCE` ผ่าน `CommandBus.submit` | ลำดับเดียวกับ Slot Sequence Mode | publish phase และ final status โดยคง `request_id` |

> **ข้อควรเน้น:** Safe-Z flow เป็นพฤติกรรมของ Go To Slot ปกติ ส่วน Sequence Mode ที่ได้รับการกำหนดให้ทำงานตามลำดับ X → Y → Z → hold → Home Z → Y → X เป็น workflow แยกใน `SequenceService` จึงไม่ควรอธิบายว่าเป็น flow เดียวกัน

### สิ่งที่ตรวจสอบได้ในการสาธิต

1. เปิด HMI แล้วแสดงว่า Browser ติดต่อ Web แต่ Web ส่งคำสั่งผ่าน `/run/narit-vending/ctrl.sock` เท่านั้น
2. แสดง `/health/live`, `/health/ready` และ `/api/mqtt/status` เพื่อแยก “service พร้อม” ออกจาก “machine พร้อมเคลื่อน”
3. ใช้ HMI หรือ MQTT ส่งคำสั่งที่มี `request_id`; แสดงว่า phase/status และ CommandResult กลับมาโดยไม่เปิดเผย secret
4. ทดสอบแบบไม่ขยับมอเตอร์ด้วย unit/mock test: safety block, sequence order, stop-on-failure, MQTT idempotency และ route ผ่าน IPC
5. ก่อนทดสอบเครื่องจริง ให้ตรวจพื้นที่ปลอดภัย, E-Stop, homing, slot XYZ และอนุมัติการเคลื่อนที่โดยผู้รับผิดชอบก่อนเสมอ

### ขอบเขตปัจจุบันและแผนต่อไป

- ส่วน `webapp.py` ยังเป็น compatibility adapter เพื่อรักษา API เดิม; sequence business logic ย้ายไป `controller/sequence_service.py` แล้ว
- Event history แบบ persistent, RBAC, MQTT TLS, atomic rollback และ Pi fault-injection suite เป็น **Target Modular Architecture / roadmap** ยังไม่ควรนำเสนอว่าเปิดใช้แล้ว
- Unit/integration tests ที่ใช้ mock ไม่ได้แทนการรับรอง hardware; การทดสอบ motor จริงต้องเป็นขั้นตอนแยกที่มีการอนุมัติและ checklist หน้างาน

### Target Modular Architecture (โครงสร้างเป้าหมาย)

ผังต่อไปนี้อธิบายว่าระบบควรถูกแบ่งหน้าที่อย่างไรเมื่อ refactor ในอนาคต เพื่อให้การเปลี่ยนแปลง UI, API, MQTT, persistence หรือ GPIO ไม่กระทบ safety และ motion โดยตรง. **เป็น target structure ไม่ใช่การยืนยันว่าไฟล์ทั้งหมดมีอยู่ใน production ปัจจุบัน**.

```text
narit_vending/
├── api/                         # HTTP boundary: parse/validate request, map errors, never drive GPIO
│   ├── app_factory.py
│   ├── error_handlers.py
│   ├── legacy/routes.py          # compatibility endpoints during migration
│   └── v1/routes/                # versioned public API
│       ├── status.py
│       ├── commands.py
│       ├── motion.py
│       ├── slots.py
│       ├── configuration.py
│       ├── alarms.py
│       └── maintenance.py
├── application/                  # use-cases: one command path and orchestration
│   ├── command_bus.py
│   ├── command_queue.py
│   ├── command_handler.py
│   ├── commands/                 # Home, Jog, Move, Slot, Motor Test, Safety commands
│   └── services/                 # machine/motion/homing/safety/slot/config services
├── domain/                       # pure business and safety rules; no Flask, MQTT or gpiozero import
│   ├── models/                   # axis, slot, command, alarm, configuration
│   ├── state_machine/            # machine state and allowed transitions
│   └── safety/                   # interlock and policy
├── infrastructure/               # replaceable technical adapters
│   ├── gpio/                     # gpiozero, pigpio and mock backends behind interfaces
│   ├── config/                   # schema, loader, migration and backup
│   ├── mqtt/                     # controller-owned adapter and payload schemas
│   └── persistence/              # JSON/SQLite implementations
├── repositories/                 # slot/event/command persistence contracts
├── diagnostics/                  # health, startup checks and metrics
├── static/                       # frontend modules: core, API, workspaces, components, CSS layers
└── templates/                    # HMI shell and reusable partials

config/                           # versioned machine/hardware/slot/MQTT configuration
└── schema/

tests/                            # unit, integration, fault injection, browser and Pi smoke tests
```

#### เส้นทางการทำงานตามโครงสร้างเป้าหมาย

1. Browser เรียก `api/v1/routes` หรือ compatibility route; API ตรวจรูปแบบ request และสิทธิ์ แต่ไม่ตัดสิน safety ของ motor เอง
2. API สร้าง command แล้วส่งเข้า `application/command_bus.py`; command queue ป้องกันคำสั่ง motion ซ้อนกันและเก็บ command ID
3. Command handler ขอ snapshot จาก domain state machine และส่งผ่าน `domain/safety/interlock.py` ก่อนเรียก service ใด ๆ
4. Application service ใช้ repository เพื่ออ่าน slot/config/audit และใช้ infrastructure adapter เพื่อสื่อสาร GPIO หรือ MQTT
5. GPIO backend เป็น implementation detail; tests ใช้ mock backend ได้โดยไม่ขยับ motor จริง
6. MQTT adapter แปลง message เป็น command เดียวกับ HTTP; ห้าม MQTT เรียก GPIO หรือ MotionService โดยตรง
7. Diagnostics อ่าน state/metrics แบบ read-only; persistence เก็บ event/command ที่ sanitize แล้วเพื่อ audit และ export

#### กฎการย้ายระบบ

- ย้ายทีละ boundary พร้อม compatibility route และ regression tests; ห้ามย้าย GPIO/motion ทั้งก้อนครั้งเดียว
- Controller process ยังคงเป็นเจ้าของ `application`, `domain`, `infrastructure/gpio` และ `infrastructure/mqtt`; Web process เป็น API/HMI facade
- สร้าง interface และ test ก่อนสลับ implementation เช่น `gpiozero_backend` ไป `pigpio_backend`
- การเพิ่ม SQLite, auth/RBAC, TLS หรือ command queue ต้องเริ่มจาก migration plan, rollback และ Pi smoke test

---

## ภาพรวมระบบ

ระบบทำงานบน `Raspberry Pi` โดยให้ Pi เป็น `web server` สำหรับควบคุมเครื่องจ่ายสินค้า ผู้ใช้เปิดหน้าเว็บผ่านชื่อเครื่อง `NaritVendingMachine.local` แล้วสั่งงาน `Home`, `Jog`, `Go To Slot`, `Save Slot` และ `Stop` ได้จาก browser หรือเรียกผ่าน REST API โดยตรง

ระบบแบ่งออกเป็น 3 ชั้นหลัก:

- `Motion Control Layer` — ควบคุมมอเตอร์ `X/Y/Z`, limit switch, emergency stop, และตำแหน่ง
- `Command/API Layer` — รับคำสั่งจาก CLI หรือ REST API แล้วส่งต่อไปยัง motion controller
- `Web UI Layer` — แสดงสถานะ realtime และให้ผู้ใช้สั่งงานผ่านหน้าเว็บ

---

## โครงสร้างไฟล์สำคัญ

| ไฟล์ | หน้าที่ |
|---|---|
| `main.py` | จุดเริ่มต้น CLI เรียก `narit_vending.cli.main` |
| `narit_vending/motion.py` | แกนหลัก ควบคุม X/Y/Z, home, move, limit, stop, slot config, logging |
| `narit_vending/webapp.py` | Flask web server, REST API v2.0, CORS, logging, `MotionService` |
| `narit_vending/mqtt_service.py` | MQTT Client Service (LWT Heartbeat, Remote Dispense, Telemetry & Alarm Pub/Sub) |
| `narit_vending/cli.py` | คำสั่ง terminal: `status`, `home`, `jog`, `move`, `goto-slot` |
| `narit_vending/templates/index.html` | โครงสร้างหน้าเว็บควบคุม HMI |
| `narit_vending/static/app.js` | Browser logic สำหรับเรียก API, สปีดซิงค์, ไทม์เมอร์ และอัปเดตสถานะ realtime |
| `narit_vending/static/style.css` | รูปแบบหน้าเว็บ theme blue dark และแอนิเมชันไฟ LED สถานะ |
| `hardware_config.json` | คอนฟิกพินฮาร์ดแวร์ (STEP, DIR, ENABLE, Sensors, LEDs, Comm, MQTT, Accel/Decel) |
| `machine_config.json` | ค่าตำแหน่ง slot 1–30 (รวม product profile) |
| `narit_vending.log` | Log file บันทึกทุก request และ motion error อัตโนมัติ |
| `deploy/narit-vending-web.service` | systemd service สำหรับเริ่มเว็บอัตโนมัติหลังบูต |
| `scripts/setup_pi.sh` | ติดตั้ง dependency, ตั้ง hostname, เปิด service |
| `scripts/deploy_to_pi.ps1` | Deploy จาก Windows ไปยัง Pi ผ่าน SSH |

---

## การทำงานของระบบ MQTT (MQTT System Operation & Architecture)

ระบบควบคุมเครื่องจ่ายสินค้าอัตโนมัตินี้ได้รวมเอา **MQTT Protocol (Message Queuing Telemetry Transport)** เข้ามาเป็นช่องทางสื่อสารหลักแบบสองทาง (Bi-directional Asynchronous Communication) ควบคู่กับ HTTP REST API เพื่อรองรับการทำงานในลักษณะ Industrial IoT (IIoT)

### 1. จุดประสงค์และการประยุกต์ใช้งาน (Use Cases)
- **การสั่งจ่ายสินค้าแบบสตรีมมิง (Remote Dispense)**: รองรับคำสั่งจากเซิร์ฟเวอร์ชำระเงิน (Payment Gateway), ตู้ Kiosk หรือ Mobile App โดยไม่ต้องเปิดพอร์ต HTTP สู่สาธารณะ
- **การเฝ้าระวังสถานะแบบ Real-time (Telemetry Monitoring)**: รายงานพิกัด X/Y/Z, สถานะมอเตอร์, สวิตช์ E-Stop และสถานะไฟแจ้งเตือนกลับไปยัง Cloud Dashboard แบบทันที
- **การแจ้งเตือนเหตุฉุกเฉิน (Instant Alarm Notification)**: ส่งสัญญาณแจ้งเตือนความผิดพลาด (เช่น ชน Limit Switch หรือกดปุ่มหยุดฉุกเฉิน) ด้วย QoS สูงสุดไปยังระบบส่วนกลาง
- **กลไกการตรวจจับตู้ล้มเหลว (Last Will & Testament - LWT)**: เมื่อตู้สูญเสียการเชื่อมต่อหรือไฟดับ Broker จะแจ้งระบบส่วนกลางทันทีว่าตู้ Offline

---

### 2. โครงสร้างและกลไกซอฟต์แวร์ (Software Architecture & Execution Flow)

1. **Background Async Loop**:
   โมดูล `narit_vending/mqtt_service.py` จะถูกเริ่มต้นทำงานทันทีเมื่อ `MotionService` ใน `webapp.py` ถูกสร้าง โดยรันเป็น **Background Daemon Thread** (`paho.mqtt.client.loop_start()`) ทำให้การรับส่งข้อความ MQTT ไม่บล็อกการรันของเว็บเซิร์ฟเวอร์ Flask หรือการสั่งงานมอเตอร์

2. **Thread-Safe Command Execution**:
   คำสั่ง MQTT ทั้งหมดที่เข้ามาใน `_on_message()` จะถูกประมวลผลผ่านเมธอดของ `MotionService` ซึ่งมีการล็อกด้วย `threading.RLock()` ทำให้รับประกันความปลอดภัยของหน่วยความจำและการแย่งกันสั่งมอเตอร์ (Race Condition Protection)

---

### 3. โครงสร้าง Topic และรูปแบบ Payload (Topic Hierarchy & Schemas)

Topic ทั้งหมดอ้างอิงรหัสประจำเครื่องจาก `hardware_config.json` ในรูปแบบ `vending/{machine_id}/...`:

| Topic | Direction | QoS | Retain | คำอธิบาย & ตัวอย่าง Payload |
|---|---|:---:|:---:|---|
| `vending/{id}/heartbeat` | Publish (Pi -> Broker) | 1 | True | **สถานะการเชื่อมต่อ (LWT)**<br/>`{"online": true}` หรือ `{"online": false, "reason": "connection_lost"}` |
| `vending/{id}/status` | Publish (Pi -> Broker) | 1 | True | **สถานะเครื่องและพิกัดแกน (Telemetry)**<br/>`{"busy": false, "status": {"state": "idle", "estop": false, ...}}` |
| `vending/{id}/response` | Publish (Pi -> Broker) | 1 | False | **ผลการประมวลผลคำสั่ง**<br/>`{"cmd": "dispense", "result": {"ok": true, "message": "Machine operation started"}}` |
| `vending/{id}/cmd/dispense` | Subscribe (Broker -> Pi) | 1 | - | **สั่งจ่ายสินค้าตามช่อง**<br/>`{"slot": "5"}` หรือ `{"slot_code": "1"}` |
| `vending/{id}/cmd/speed` | Subscribe (Broker -> Pi) | 1 | - | **ปรับความเร็วมอเตอร์**<br/>`{"speed_mm_s": 45.0}` |
| `vending/{id}/cmd/timer` | Subscribe (Broker -> Pi) | 1 | - | **ตั้งเวลานับถอยหลัง**<br/>`{"duration_s": 60.0}` |
| `vending/{id}/cmd/home` | Subscribe (Broker -> Pi) | 1 | - | **สั่ง Home แกน**<br/>`{"axis": "all"}` หรือ `{"axis": "x"}` |
| `vending/{id}/cmd/stop` | Subscribe (Broker -> Pi) | 2 | - | **สั่งหยุดฉุกเฉิน / Soft Stop ทันที**<br/>`{}` |
| `vending/{id}/cmd/clear_alarm` | Subscribe (Broker -> Pi) | 1 | - | **รีเซ็ตสัญญาณเตือนภัย**<br/>`{}` |

---

### 4. การตั้งค่าคอนฟิกระบบ MQTT (`hardware_config.json`)

สามารถเปิด/ปิด หรือเปลี่ยน Broker ได้ผ่านไฟล์คอนฟิกโดยไม่ต้องแก้ไขโค้ด:

```json
"mqtt": {
  "enabled": true,
  "broker": "broker.emqx.io",
  "port": 1883,
  "client_id": "vending_machine_01",
  "username": "",
  "password": "",
  "topic_prefix": "vending/machine_01",
  "keepalive_s": 60
}
```

---

## ค่าคอนฟิกเครื่อง

ไฟล์ `machine_config.json` เก็บค่าทั้งหมดของระบบ:

- พิน `pulse`, `dir`, `head_limit`, `tail_limit` ของแต่ละแกน
- `steps_per_mm`, `max_travel_mm`, `max_speed_mm_s`, `default_speed_mm_s`, `jog_step_mm`
- ลำดับการ `home` (`home_order`)
- ตำแหน่ง `slot 1–30` พร้อม Product Profile

### สรุปแกน

| Axis | Pulse Pin | Dir Pin | Min Limit | Max Limit | Steps/mm | Max Travel (mm) |
|---|---:|---:|---:|---:|---:|---:|
| X | 16 | 23 | 17 | 27 | 80.0 | 220.0 |
| Y | 26 | 24 | 22 | 9 | 80.0 | 260.0 |
| Z | 18 | 25 | 11 | 5 | 50.0 | 200.0 |

### โครงสร้าง Slot (v2.0)

```json
"5": {
  "x_mm": 45.0,
  "y_mm": 20.0,
  "z_mm": 5.0,
  "product_name": "น้ำดื่ม",
  "dispense_delay_ms": 800
}
```

- `product_name` — ชื่อสินค้าในช่องนั้น (ค่าเริ่มต้น `""`)
- `dispense_delay_ms` — เวลาหน่วงสำหรับการ dispense (ค่าเริ่มต้น `0`)
- ค่าเริ่มต้นพิกัดทุก slot คือ `X=0`, `Y=0`, `Z=0`

---

## Classes ใน motion.py

### Exception Classes

| Class | สืบทอดจาก | เกิดเมื่อ |
|---|---|---|
| `MotionError` | RuntimeError | ข้อผิดพลาดทั่วไปของ motion |
| `LimitTriggeredError` | MotionError | ชน limit switch |
| `EmergencyStopError` | MotionError | E-Stop ถูกกด |
| `NotHomedError` | MotionError | สั่ง move_to_mm โดยยังไม่ home |
| `StopRequestedError` | MotionError | ผู้ใช้กด Stop บนหน้าเว็บ |

### Data Classes

| Class | ฟิลด์สำคัญ | หมายเหตุ |
|---|---|---|
| `AxisConfig` | pulse_pin, dir_pin, steps_per_mm, max_travel_mm, max_speed_mm_s, default_speed_mm_s | frozen=True |
| `SlotPosition` | code, x_mm, y_mm, z_mm, product_name, dispense_delay_ms | frozen=True, v2.0 |
| `MachineConfig` | x, y, z, home_order, slots, safe_z_mm | frozen=True |

### AxisController

ควบคุมมอเตอร์ทีละแกน

| เมธอด | หน้าที่ |
|---|---|
| `move_steps(steps, direction, speed_mm_s)` | ปล่อย pulse ตามจำนวน steps + คำนวณความเร็ว (หน่วงเวลา) อัตโนมัติ |
| `move_mm(distance_mm, speed_mm_s)` | แปลง mm → steps แล้วเรียก move_steps |
| `move_to_mm(target_mm, speed_mm_s)` | เคลื่อนไปตำแหน่งสัมบูรณ์ (ต้อง home ก่อน) |
| `home(backoff_steps, max_steps)` | Home แกน + บันทึก log start/complete |
| `stop()` | ปิด pulse ทันที |
| `status()` | คืนค่า position, homed, limit, estop |
| `_guard_before_move()` | ตรวจสอบก่อนเริ่มเคลื่อน |
| `_guard_during_move()` | ตรวจสอบระหว่างเคลื่อน (ทุก **5 steps**) |

### MotionController

รวมการควบคุมแกนทั้งสาม

| เมธอด | หน้าที่ |
|---|---|
| `axes()` | คืน `{"x": ..., "y": ..., "z": ...}` |
| `home_axis(axis_name)` | Home แกนเดียว |
| `home_all()` | Home ทุกแกนตาม home_order |
| `move_to(x_mm, y_mm, z_mm, speed_mm_s)` | เคลื่อนไปพิกัดสัมบูรณ์ (X→Y→Z ตามลำดับ) |
| `move_by_mm(x, y, z, speed_mm_s)` | เคลื่อนสัมพัทธ์จากตำแหน่งปัจจุบัน |
| `move_to_slot(slot_code)` | ยก Z → เคลื่อน X/Y → ลง Z ไปยัง slot |
| `update_slot(code, x, y, z, product_name, dispense_delay_ms)` | อัปเดตพิกัด + product profile (คง field เดิมถ้าไม่ส่งมา) |
| `request_stop()` | ตั้ง flag stop ทุกแกน |
| `clear_stop()` | ล้าง flag stop |
| `current_position()` | คืนตำแหน่งปัจจุบัน {x_mm, y_mm, z_mm} |
| `status()` | คืน estop, แกน X/Y/Z status, current_position |
| `emergency_stop_active()` | ตรวจสอบ E-Stop |

---

## กลไกความปลอดภัย

1. **E-Stop** — ตรวจก่อนและระหว่างการเคลื่อนที่
2. **Soft Stop Request** — จากปุ่ม SOFT STOP บนหน้าเว็บ (ไม่ block HTTP thread, มอเตอร์หยุดแต่ไม่ตัดไฟ)
3. **Limit Switch Min/Max** — ตรวจทั้ง head และ tail limit
4. **Software Travel Limit** — จาก `max_travel_mm` ใน config
5. **Guard ทุก 5 steps** — ตรวจสอบระหว่างเคลื่อนที่ถี่ขึ้น 4× (จากเดิม 20 steps)
6. **RLock** — ป้องกัน 2 คำสั่ง motion รันพร้อมกัน
7. **Input Validation** — ทุก endpoint ตรวจ field และ type ก่อนส่งให้ controller

---

## MotionService Methods (webapp.py)

| เมธอด | หน้าที่ |
|---|---|
| `status_payload()` | ส่งสถานะทั้งหมด (busy, last_error, slots, position) |
| `_run(fn)` | รัน fn ใน RLock + จัดการ exception + log error |
| `stop()` | สั่ง stop ทันที (ไม่ใช้ lock — ทำงานได้ขณะ busy) |
| `home_axis(axis)` | Home แกนเดียว |
| `home_all()` | Home ทุกแกน |
| `jog(axis, distance_mm)` | Jog แกนเดียวด้วยระยะทาง |
| `move_to(x, y, z)` | เคลื่อนไปพิกัด absolute |
| `move_to_slot(slot_code)` | ไปยัง slot |
| `save_slot(code, x, y, z, product_name, dispense_delay_ms)` | บันทึกพิกัด + product profile |
| `save_slot_from_current(code)` | บันทึกตำแหน่งปัจจุบันเป็น slot |
| `get_slot(code)` | ดึงข้อมูล slot เดียว (พร้อม product profile) |
| `reset_slot(code)` | Reset พิกัด → 0,0,0 (คง product_name ไว้) |
| `get_config()` | ดึง MachineConfig ทั้งหมด |
| `is_axis_homed(axis)` | เช็กว่าแกนนั้น home แล้วหรือยัง |
| `is_all_homed()` | เช็กทุกแกนพร้อมกัน + `all_homed` flag |

---

## REST API Endpoints (v2.0)

### พื้นฐาน

| Method | Endpoint | หน้าที่ |
|---|---|---|
| `GET` | `/api/ping` | เช็กการเชื่อมต่อ → `{ "ok": true, "message": "pong" }` |
| `GET` | `/api/status` | สถานะทั้งหมด (busy, position, slots, estop) |
| `GET` | `/api/config` | ค่าคอนฟิกแกน X/Y/Z |

### Home

| Method | Endpoint | หน้าที่ |
|---|---|---|
| `POST` | `/api/home/x` | Home แกน X |
| `POST` | `/api/home/y` | Home แกน Y |
| `POST` | `/api/home/z` | Home แกน Z |
| `POST` | `/api/home/all` | Home ทุกแกน |
| `GET` | `/api/home/<axis>/check` | เช็ก Home แกนเดียว (x, y, z) |
| `GET` | `/api/home/all/check` | เช็ก Home ทั้ง 3 แกนพร้อมกัน |

### การเคลื่อนที่

| Method | Endpoint | Body | หน้าที่ |
|---|---|---|---|
| `POST` | `/api/jog` | `{"axis": "x", "distance_mm": 10, "speed_mm_s": 20}` | Jog แกนเดียว (ระบุ speed_mm_s หรือ time_s ได้) |
| `POST` | `/api/move` | `{"x_mm": 10, "y_mm": 20, "time_s": 5}` | เคลื่อนไปพิกัด absolute (ระบุ speed_mm_s หรือ time_s ได้) |
| `POST` | `/api/stop` | — | หยุดทันที |

### Slot Management

| Method | Endpoint | Body | หน้าที่ |
|---|---|---|---|
| `GET` | `/api/slots` | — | ดึงข้อมูลทุก slot |
| `GET` | `/api/slots/<code>` | — | ดึงข้อมูล slot เดียว |
| `POST` | `/api/slots/<code>/goto` | — | เคลื่อนไปยัง slot |
| `POST` | `/api/slots/<code>/save-current` | — | บันทึกตำแหน่งปัจจุบัน |
| `POST` | `/api/slots/<code>` | `{"x_mm", "y_mm", "z_mm", "product_name", "dispense_delay_ms"}` | บันทึกพิกัด + product profile |
| `POST` | `/api/slots/<code>/reset` | — | Reset พิกัด → 0,0,0 |
| `DELETE` | `/api/slots/<code>` | — | ลบพิกัด (reset → 0,0,0) |

### Convention ของ Response

ทุก endpoint คืน `"ok": true/false` เสมอ พร้อม HTTP status code:

```json
{ "ok": true, ... }      ← สำเร็จ (HTTP 200)
{ "ok": false, "error": "..." }  ← ผิดพลาด (HTTP 400)
```

---

## Logging (v2.0)

- บันทึกลงไฟล์ `narit_vending.log` + stdout พร้อมกัน
- Format: `2026-07-17 14:41:00 [INFO] narit_vending.webapp: GET /api/status`
- Log ที่บันทึก:
  - ทุก HTTP request (method + path)
  - Home axis start และ complete (พร้อมจำนวน steps)
  - Motion error ทุกครั้ง (WARNING)
  - เริ่มต้น server

---

## CORS (v2.0)

เปิด CORS ทุก endpoint อัตโนมัติ:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## Flowchart ภาพรวมคำสั่งจากหน้าเว็บ

```mermaid
flowchart TD
    A["ผู้ใช้เปิดเว็บ NaritVendingMachine.local"] --> B["Flask Web App (webapp.py)"]
    B --> C["MotionService (busy lock + logging)"]
    C --> D["MotionController (X/Y/Z)"]
    C --> E["machine_config.json (slots + product profile)"]
    D --> F["AxisController (Pulse/Dir/Limit + guard ทุก 5 steps)"]
    B --> G["narit_vending.log"]
```

## Flowchart การ Home แกน

```mermaid
flowchart TD
    A["เริ่มคำสั่ง Home แกน"] --> B["Log: Home X starting"]
    B --> C["ตรวจ E-stop และ Stop Request"]
    C --> D["หมุนทิศไปหา Min Limit (pulse ทีละ step)"]
    D --> E{"ชน Min Limit?"}
    E -- "ยัง" --> D
    E -- "ชนแล้ว" --> F["Backoff ออกจากสวิตช์เล็กน้อย"]
    F --> G["ตั้งตำแหน่ง = 0 mm, is_homed = True"]
    G --> H["Log: Home X complete (N steps)"]
```

## Flowchart การไปยัง Slot

```mermaid
flowchart TD
    A["กดปุ่ม Go To Slot"] --> B["อ่านค่า X/Y/Z + product_name จาก config"]
    B --> C{"Z ต่ำกว่า safe_z?"}
    C -- "ใช่" --> D["ยก Z ขึ้นถึง safe_z ก่อน"]
    C -- "ไม่" --> E["เคลื่อน X และ Y ไปพิกัดเป้าหมาย"]
    D --> E
    E --> F["เลื่อน Z ลงไปยังตำแหน่ง slot"]
    F --> G["อัปเดตสถานะ realtime + ส่งกลับหน้าเว็บ"]
```

---

## ลำดับการเริ่มระบบ

1. Raspberry Pi บูตขึ้น
2. `systemd` เรียก `narit-vending-web.service`
3. service สั่ง Python ใน venv รัน `narit_vending.webapp`
4. `logging.basicConfig` ตั้งค่า log → ไฟล์ + stdout
5. `Flask` โหลด `machine_config.json` และสร้าง `MotionController`
6. Log: `Narit Vending starting — host=0.0.0.0 port=80`
7. ผู้ใช้เปิด `http://NaritVendingMachine.local/`
8. `app.js` เริ่ม poll `GET /api/status` ทุก 500 ms

---

## ข้อสังเกตและแผนพัฒนาต่อ

- [ ] **Worker Thread** — ถ้า motion ใช้เวลานาน ควรแยกเป็น background thread แบบ proper queue
- [ ] **Dispense Sequence** — ใช้ `dispense_delay_ms` ที่เก็บไว้ใน slot เพื่อ automate การจ่ายสินค้า
- [ ] **Dispense History** — บันทึกประวัติการจ่ายสินค้า (slot, เวลา, สำเร็จ/ล้มเหลว)
- [ ] **Auto-Home on Startup** — option `--auto-home` ใน service
- [ ] **Config Hot-Reload** — `POST /api/config/reload` โดยไม่ต้องรีสตาร์ท service
- [ ] **ทดสอบ** `steps_per_mm`, `home_direction`, และ `max_travel_mm` กับเครื่องจริงเสมอ

---

## เอกสารที่เกี่ยวข้อง

- [README.md](README.md)
- [API_DOCS.html](API_DOCS.html) — เอกสาร REST API ฉบับสมบูรณ์
- [ARCHITECTURE.html](ARCHITECTURE.html) — เอกสารนี้ในรูปแบบ HTML
- [machine_config.json](machine_config.json)
- [motion.py](narit_vending/motion.py)
- [webapp.py](narit_vending/webapp.py)
