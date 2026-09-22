# ระบบ Motion Control ปัจจุบันของ NaritVendingMachine

เอกสารนี้อธิบายระบบที่ใช้งานจริงหลัง deploy NUCLEO-G491RE Protocol v4 และ
commissioning ถึง 60 mm/s เมื่อวันที่ 2026-09-21 โดยอ้างอิง source revision
`9b4edb4` ขึ้นไป เอกสารนี้ไม่ใช่ใบรับรองว่าความเร็วสูงสุดทางกลผ่านการทดสอบแล้ว

## 1. สรุปสั้นที่สุด

เครื่องใช้ motion สองเส้นทางร่วมกัน:

1. **Dynamic jerk-limited motion สำหรับ X/Y** — ใช้กับ Jog, absolute move,
   coordinated X/Y และ GOTO Slot เมื่อ handshake ยืนยัน Protocol v4 พร้อม
   `dynamic_motion` และ `dynamic_watchdog_heartbeat`
2. **Legacy timer motion** — ใช้กับ Z และ Home/limit-seek ซึ่ง Controller ต้องอ่าน
   physical sensors ผ่าน IRIV I/O แล้วสั่งหยุดตามลำดับ

Web ไม่ควบคุม timer หรือ GPIO โดยตรง Web ส่ง CommandEnvelope ไป Controller บน
IRIV Pi; Controller ตรวจ safety และส่ง target/constraints ไป G491RE; G491RE ทำ
realtime trajectory ที่รอบควบคุม 1 kHz และสร้าง STEP/DIR ด้วย hardware timer

ตำแหน่ง X/Y/Z ที่แสดงเป็น **estimated position จากจำนวน STEP pulses** หลัง Home
ไม่ใช่ตำแหน่งกลไกที่วัดต่อเนื่องจาก encoder ภายนอก PEND ของ HBS860H เป็นเพียง
สัญญาณยืนยันตำแหน่งเมื่อ commission แล้ว ไม่ใช่ feedback ของวงรอบ planner

## 2. Ownership และ data flow

```text
Browser / HMI
  │  HTTP API: Home, Jog, Move, Slot, Stop
  ▼
Flask Web process
  │  CommandEnvelope ผ่าน Unix IPC
  ▼
Controller process (machine authority)
  ├─ ตรวจ E-Stop, Stop, ALM, limits, Home, travel, configuration revision
  ├─ อ่าน IRIV Modbus DI และ PiControl local DI
  ├─ serialize คำสั่งให้มี motion เดียวที่ครองเครื่อง
  └─ USB Serial Protocol v4
       │ CONFIG/POSITION/TARGET/START/HEARTBEAT/STOP
       ▼
STM32 NUCLEO-G491RE (realtime execution)
  ├─ LPUART1 RX interrupt + ring buffer
  ├─ TIM6 control tick 1 kHz
  ├─ Virtual Kp request + jerk-aware constraint envelope
  ├─ TIM1 OC CH1/CH2 สร้าง STEP X/Y
  └─ legacy timer path สร้าง STEP Z/Home
       │ STEP/DIR
       ▼
HBS860H X/Y และ DM542 Z → มอเตอร์/กลไก
```

หลักสำคัญคือ Controller เป็นผู้มีอำนาจอนุมัติ ส่วน NUCLEO เป็นผู้ทำ realtime
execution ทั้งสองฝั่งมี watchdog/interlock ของตนเอง แต่ NUCLEO ห้ามเริ่ม motion
เองหลัง boot, reset หรือ reconnect

## 3. Motion routing ที่ใช้จริง

| Operation | X/Y | Z | เหตุผล |
|---|---|---|---|
| Jog แบบกำหนดระยะ | Dynamic planner | Legacy | Dynamic runtime commission เฉพาะ X/Y |
| GOTO XYZ / Slot | Dynamic X/Y; Z legacy ตาม plan | Legacy | รักษา API เดียว แต่ backend แยกตาม capability |
| Coordinated X/Y | Dynamic start เดียวสำหรับสองแกน | ไม่เกี่ยวข้อง | แต่ละแกนมี target และ speed constraint ของตนเอง |
| Home | Legacy + Controller sensor supervision | Legacy | Home sensors อยู่ที่ IRIV I/O ไม่ได้ต่อเข้า MCU โดยตรง |
| Move to physical limit | Controller-supervised limit seek | Legacy | ต้องหยุดจาก sensor จริง |
| Manual Commissioning | bounded raw pulse | bounded raw pulse | ใช้เฉพาะ armed commissioning; ไม่ใช่หลักฐาน S-curve |
| STOP / E-Stop / communication fault | ตัด pulse/disarm | ตัด pulse/disarm | priority สูงสุดและห้าม bypass |

หาก handshake ไม่มี capability ครบ Dynamic X/Y จะถูก quarantine และใช้เส้นทาง
ที่ policy อนุญาตหรือปฏิเสธคำสั่งแบบ fail-closed ห้าม UI อ้างว่าใช้ Dynamic S-curve
เมื่อ firmware ไม่รองรับ

## 4. Position model และหน่วย

หลัง Home สำเร็จ:

```text
estimated_position_mm = position_steps / steps_per_mm
target_pulses = round(target_position_mm × steps_per_mm)
remaining_pulses = abs(target_pulses - emitted_pulses)
```

สำหรับ Hold-to-run Jog เมื่อปล่อยปุ่ม Controller ส่ง `CONTROLLED_STOP` ให้ planner
ลดความเร็วตาม S-curve แล้วอ่าน `DYN_STATUS` ก่อน Disarm หาก NUCLEO ยืนยัน
`position_valid=true` พร้อม `position_pulses` ภายใน travel range ระบบจะรักษา Homed
และใช้ตำแหน่ง pulse ดังกล่าวเป็นจุดเริ่ม Jog ครั้งถัดไป หากยืนยันไม่ได้จะล้าง Homed
ตาม fail-closed policy

NUCLEO นับ pulse ที่ **ขอบตกของ STEP ที่ปล่อยจริง** เท่านั้น ไม่ได้นับ pulse ที่
เพียงถูก queue ขอบเขตจบคำสั่งจึงเป็น integer pulse เสมอ ทำให้ตำแหน่งที่แทนได้จริง
อาจต่างจากค่า mm เล็กน้อย เช่น X/Y 100 mm กลายเป็น 6,471 pulses หรือ 100.006 mm

ค่ากลไกที่ effective ปัจจุบัน:

| Axis | กลไก | pulses/mm | travel ที่ตั้ง | driver |
|---|---:|---:|---:|---|
| X | lead screw | 64.705882 | 1,780 mm | HBS860H |
| Y | lead screw | 64.705882 | 1,700 mm | HBS860H |
| Z | timing belt/pulley | 9.0 | 160 mm | DM542 |

การสูญเสีย drive power, fault ที่ทำให้ไม่ทราบ pulse จริง, emergency stop ระหว่าง
motion หรือการเปลี่ยน pulses/mm/travel ต้อง invalidate `is_homed`

## 5. ทฤษฎี Dynamic planner ปัจจุบัน

### 5.1 Virtual Kp request

Virtual Kp ไม่ใช่ closed-loop position feedback จาก encoder แต่เป็นวิธีสร้างคำขอ
ความเร็วจากจำนวน pulse ที่ยังเหลือ:

```text
requested_rate = min(Kp × remaining_pulses, max_rate)
```

เมื่ออยู่ไกล target คำขอจะชน max rate; เมื่อเข้าใกล้ target คำขอจะลดลงตามระยะ
ถ้าปิด Kp ระบบจะขอ max rate แล้ว constraint envelope ยังต้องเร่ง/เบรกอย่างนุ่มนวล

ข้อจำกัด: Kp ไม่สามารถชดเชยการติดขัด, lost step, backlash หรือความคลาดเคลื่อนทางกล
เพราะ planner เห็นเพียง pulse ที่ตนเองปล่อย

### 5.2 Kinematic constraint envelope

ทุก control tick คำนวณ state จาก velocity และ acceleration ปัจจุบัน แล้วจำกัดด้วย:

- maximum velocity
- acceleration
- deceleration
- jerk
- pulse frequency และ travel boundary

Planner ประเมินระยะหยุดแบบ jerk-aware:

```text
t_ramp = (current_acceleration + max_deceleration) / max_jerk
v_after_ramp = v + a·t_ramp - 0.5·j·t_ramp²
d_ramp = v·t_ramp + 0.5·a·t_ramp² - j·t_ramp³/6
d_stop = d_ramp + v_after_ramp²/(2·max_deceleration)
d_required = d_stop + v·dt
```

เมื่อ `d_required >= remaining_pulses` planner เข้า braking state จากนั้น acceleration
เปลี่ยนทีละไม่เกิน `jerk × dt` และ velocity integrate จาก acceleration เก่า/ใหม่
จึงไม่กระโดดจาก 0 ไป target speed ทันที

### 5.3 ทำไมเรียกว่า S-curve

การจำกัด jerk ทำให้ acceleration เปลี่ยนเป็น ramp แทนการกระโดดทันที Velocity จึงมี
รูปโค้งต่อเนื่องและ position มีลักษณะ S-curve โค้ดยังมี analytical seven-segment และ
quintic profile สำหรับ validation/simulation แต่ realtime X/Y ปัจจุบันใช้ Dynamic
Virtual-Kp + jerk-aware envelope ที่คำนวณทุก 1 ms ไม่ได้ stream pulse blocks 10,000
steps จาก Pi

### 5.4 Terminal completion

Pulse phase accumulator แปลง rate เป็น edge ตามเวลา เมื่อ pulse สุดท้ายกำลังจะออก
แต่ velocity ยังสูงกว่า terminal rate ระบบจะหน่วง final edge จน state ลดความเร็วพอ
เมื่อ emitted pulses เท่ากับ target:

- output rate = 0
- acceleration state reset = 0
- axis state = COMPLETE

กรณี single-axis วิ่งทิศ Home ไป target 0 แล้ว Min sensor ทำงานก่อน virtual pulse
ถึงศูนย์ Controller ยอมรับเป็น sensor-terminated zero completion และ resync position
คำสั่งถัดไป เงื่อนไขนี้ไม่ใช้กับ target อื่น, Max, multi-axis, E-Stop หรือ Stop

## 6. Realtime execution บน G491RE

- TIM6 interrupt เรียก control tick ที่ 1 kHz (`dt = 1 ms`)
- TIM1 Output Compare CH1/CH2 สร้าง X/Y pulse independently
- compare interval เปลี่ยนตาม output rate โดยไม่ใช้ blocking delay ทำ pulse
- direction ถูกตั้งก่อน enable STEP และหน่วง 1 ms ซึ่งมากกว่าข้อกำหนด 5 us
- emitted pulse ถูกนับที่ falling edge
- LPUART1 รับ heartbeat ด้วย interrupt priority สูงกว่า control/pulse timer และเก็บใน
  ring buffer จึงยังรับ heartbeat ขณะ timer สร้าง pulse
- heartbeat timeout 500 ms ทำให้ disarm และตัด pulse ทุกแกน
- invalid timer rate หรือ HAL failure ปิด shared X/Y outputs แบบ fail-closed

## 7. Protocol v4 สำหรับ Dynamic X/Y

ลำดับทั่วไปของคำสั่ง:

```text
DYN_CONFIG   axis + travel + pulses/mm + Kp + V/A/D/J + terminal rate + revision
DYN_POSITION axis + estimated pulses + revision
DYN_TARGET   command_id + axis + absolute target pulses + revision
DYN_START    command_id + axis mask
HEARTBEAT    ระหว่าง execution
DYN_STATUS   position/target/emitted/remaining/rate/acceleration/state/fault
```

Controller cache configuration ตราบที่ speed/parameters ไม่เปลี่ยน การเปลี่ยน speed
ทำให้ resync config และ invalidate validation/arm token คำสั่ง target ใหม่ขณะ motion
กำลังทำงานถูก reject แทนการ retarget กลาง trajectory

Telemetry สำคัญ:

- `heartbeat_age_ms`
- `max_heartbeat_gap_ms`
- `watchdog_trip_count`
- `uart_overrun_count`
- `rx_dropped_bytes`
- emitted/remaining pulses, rate, acceleration, braking และ fault ต่อแกน

## 8. Home process

Home ปัจจุบันเป็น Controller-supervised legacy motion เพราะ sensor ต่อกับ IRIV I/O:

1. ตรวจ E-Stop, Stop, ALM, IRIV และ USB
2. ถ้า Min active ให้ back off จน sensor release
3. Search ทิศลบด้วย `homing_search_speed_mm_s` (ปัจจุบัน X/Y = 20 mm/s, Z = 50 mm/s)
4. พบ Min แล้วหยุด
5. Back off
6. Approach ใหม่ด้วย `homing_latch_speed_mm_s` (ปัจจุบัน 5 mm/s)
7. กำหนด coordinate = 0
8. ไป `home_position_mm`
9. ตั้ง `is_homed = true` เมื่อทุกขั้นสำเร็จเท่านั้น

Home All ปัจจุบัน serialize ตาม Controller orchestration แม้ Protocol v4 รองรับ
ความสามารถอื่นมากขึ้น เพราะ sensor freshness/stop decision ยังอยู่ฝั่ง Pi

## 9. Safety chain

คำสั่ง motion ต้องผ่านทั้งหมด:

- Controller/Web/NUCLEO/IRIV communication healthy
- E-Stop DI10/KM1 clear
- PiControl DI0 `X_DRIVE_ALM` และ DI1 `Y_DRIVE_ALM` clear
- software Stop clear และ motion authority enabled
- axis Homed สำหรับ normal motion
- target อยู่ใน software travel
- physical limit ไม่ block ทิศที่กำลังจะไป
- configuration revision ตรงกัน
- USB heartbeat ไม่เกิน 500 ms

PEND X/Y ที่ PiControl DI2/DI3 ยังเป็น advisory จนกว่าจะ commission polarity,
transition และ settle timeout แล้วตั้ง `commissioned=true`

`STOP` เป็น immediate pulse inhibit ส่วน `CONTROLLED_STOP` ขอให้ planner ลดความเร็ว
ตาม constraint แต่ E-Stop, alarm, watchdog และ communication fault ใช้ immediate stop
และไม่มี auto-resume

## 10. กระบวนการของคำสั่งหลัก

### Jog / Move / GOTO Slot

1. Web ส่ง API request
2. Controller สร้าง CommandEnvelope และ serialize
3. ตรวจ safety, Home, target, speed และ limits
4. สร้าง immutable AxisMovePlan/CoordinatedMovePlan
5. เลือก route จาก capability และ axis
6. Sync Dynamic config/estimated position เมื่อจำเป็น
7. Stage absolute target pulses และสั่ง start
8. ส่ง heartbeat และเฝ้า IRIV/PiControl interlocks
9. NUCLEO tick trajectory และสร้าง pulse
10. ตรวจ terminal telemetry/PEND policy แล้ว commit estimated position
11. กลับ Safe/Disarmed เมื่อคำสั่งจบ

### Slot sequence

Controller เป็นเจ้าของ 9-stage sequence: validate/safe Z, move XY, extend Z pick,
Y lift+dwell, retract Z, move parking, extend Z drop+dispense, retract Z และ return
Home แต่ละ phase ใช้ motion API เดียวกันและตรวจ Stop ระหว่าง dwell ห้าม browser
รัน phase timer หรือสร้าง motion เอง

## 11. แผนผัง source code

### Python / IRIV Pi

| Path | หน้าที่ |
|---|---|
| `narit_vending/motion.py` | Axis/Machine config, planning, route execution, Home, Slot และ position ownership |
| `narit_vending/nucleo.py` | USB serial, handshake, heartbeat, legacy/dynamic commands และ telemetry |
| `narit_vending/domain/motion_policy.py` | directional limit และ sensor-terminated zero policy แบบ pure function |
| `narit_vending/domain/motion_plans.py` | immutable AxisMovePlan/CoordinatedMovePlan |
| `narit_vending/domain/motion_math.py` | mm/s, pulse Hz, RPM และ effective speed limits |
| `narit_vending/domain/motion_profile.py` | analytical quintic/seven-segment profile สำหรับ model/test |
| `narit_vending/domain/motion_profile_routing.py` | capability-based route decision |
| `narit_vending/domain/nucleo_profile_protocol.py` | typed Protocol v4 commands และ validation |
| `narit_vending/nucleo_profile_transport.py` | buffered/sensor profile transport abstraction |
| `narit_vending/controller/` | CommandBus, handlers, IPC, homing orchestration, completion verification |
| `narit_vending/web/routes/commands.py` | HTTP → CommandEnvelope; ไม่มี hardware authority |
| `narit_vending/webapp.py` | MotionService, sequence, safety status และ configuration workflow |

### Firmware / G491RE

| Path | หน้าที่ |
|---|---|
| `Motion_NaritVending/Motion_NaritVending/Core/Src/nucleo_serial_link.c` | Protocol parser, handshake, UART IRQ ring buffer และ telemetry response |
| `.../Core/Src/nucleo_motion.c` | boot-safe state, arm/disarm, heartbeat, legacy timer และ dynamic integration |
| `.../profile_core/nucleo_virtual_kp.c` | remaining pulses → requested rate |
| `.../profile_core/nucleo_constraint_envelope.c` | velocity/acceleration/deceleration/jerk และ stopping feasibility |
| `.../profile_core/nucleo_dynamic_planner.c` | planner state, terminal completion และ emitted pulse count |
| `.../profile_core/nucleo_dynamic_runtime.c` | arm/start/watchdog/fault state machine ต่อแกน |
| `.../profile_core/nucleo_dynamic_coordinator.c` | synchronized X/Y start และ stop ownership |
| `.../profile_core/nucleo_dynamic_facade.c` | protocol-to-runtime transaction boundary |
| `.../profile_hal/nucleo_g491_control_timer.c` | TIM6 deterministic 1 kHz tick |
| `.../profile_hal/nucleo_g491_profile_hal.c` | TIM1 OC STEP/DIR และ falling-edge accounting |

### Tests

- `tests/test_dynamic_scurve_motion.py` — Controller routing, config sync, target,
  limit/fault และ zero-target regression
- `tests/test_nucleo_g491re_firmware.py` — firmware integration/static invariants
- `tests/c_host/` — compile/run planner modules บน host โดยไม่สั่ง hardware
- `tests/test_motion_policy.py`, `test_motion_math.py`, `test_nucleo_profile_protocol.py`
  — pure safety/math/protocol contracts

## 12. Configuration ที่มีผลต่อ motion

ค่าหลักต่อแกนอยู่ใน `machine_config.iriv.json`:

- `steps_per_mm`, `max_travel_mm`, `max_pulse_hz`
- `commissioned_max_speed_mm_s`
- `acceleration`, `deceleration`
- `scurve_enabled`, `scurve_max_jerk_mm_s3`
- `scurve_start_speed_mm_s`, `scurve_end_speed_mm_s`
- `scurve_control_period_us`
- `homing_search_speed_mm_s`, `homing_latch_speed_mm_s`

ค่าที่แก้ใน UI เป็น candidate ก่อน Validate/Save/Apply ค่า effective ต้องมาจาก
Controller และ ACK จาก firmware การเปลี่ยน pulses/mm หรือ travel ทำให้ Homed state
หมดอายุ การเพิ่มเพดานไม่ได้แปลว่ากลไกผ่าน commissioning

## 13. ผลทดสอบที่ยืนยันแล้วและสิ่งที่ยังไม่ยืนยัน

ยืนยันบนเครื่องจริงแล้ว:

- Protocol v4 + `dynamic_watchdog_heartbeat`
- Home All
- X/Y single-axis และ coordinated ที่ 20, 40 และ 60 mm/s
- ระยะทดสอบสูงสุด 100 mm; heartbeat gap สูงสุด 128 ms
- watchdog trip, UART overrun/drop และ driver alarm เป็นศูนย์ใน test gates เหล่านี้

ยังไม่ถือว่าผ่าน:

- ความเร็วสูงกว่า 60 mm/s
- GOTO Slot/ระยะ travel ยาวพร้อมโหลดจริง
- Z pick/drop และ dispense hardware
- Demo Sampling และ 9-stage sequence แบบเต็ม
- PEND X/Y ในฐานะ commissioned completion interlock
- การยืนยันระยะกลไกด้วยเครื่องมือวัดภายนอกทุกแกน

รายละเอียดผล deploy/commissioning อยู่ใน `docs/DEPLOYMENT_G491_2026-09-20_TH.md`
และกฎความปลอดภัย/กู้ระบบอยู่ใน `docs/SAFETY_AND_RECOVERY_TH.md`
