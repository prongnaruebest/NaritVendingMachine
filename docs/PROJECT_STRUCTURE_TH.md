# โครงสร้างโปรเจกต์ NaritVendingMachine

```text
narit_vending/
  controller/          Controller process, CommandBus, Safety, sequences
    handlers/          ตัวแปลง CommandEnvelope เป็น service action
    demo_service.py    Demo state, bounded sampling และ SQLite audit
  web/                 Flask web process และ IPC client
    routes/            Status, commands, configuration
  shared/              CommandEnvelope, MachineSnapshot, IPC protocol
  static/              app.js shared UI state และ style.css
  templates/           HMI HTML
  motion.py            Axis/MotionController และ homing
  nucleo.py            USB Serial handshake, heartbeat, STEP command
  iriv_io.py           Modbus TCP DI/DO แบบ fail-safe
tests/                 Mock-hardware automated tests
firmware/              STM32 source/artifacts
deploy/                systemd services
scripts/               validation, backup และ deploy
docs/                  คู่มือและสถาปัตยกรรม
machine_config*.json   Machine coordinates, axes และ slots
hardware_config*.json  I/O, USB และ hardware mapping
demo_results.sqlite3   Runtime Demo sessions บนเครื่อง Deploy
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

