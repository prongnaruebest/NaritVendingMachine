# คู่มือ Configuration และ Axis Calibration

คู่มือนี้ใช้กับเครื่องจริงโปรไฟล์ IRIV (`machine_config.iriv.json` และ `hardware_config.iriv.json`)
การแก้ configuration ไม่ทำให้มอเตอร์เคลื่อน แต่ `Apply & Restart` ทำให้ Controller restart,
motion ถูกล็อก และ Homed status ถูกล้าง

## 1. Configuration authority

Effective configuration ถูกประกอบตามลำดับ:

1. `machine_config.iriv.json` ให้ค่าพื้นฐานของ axis, homing, travel และ slots
2. `hardware_config.iriv.json > motors` ให้ STEP/DIR/Enable pins
3. `hardware_config.iriv.json > digital_inputs` ให้ limit/home pins
4. `hardware_config.iriv.json > machine_parameters.axes` override motion parameters

ห้ามอ่านไฟล์ใดไฟล์หนึ่งแล้วสรุปว่าเป็นค่าที่ Controller ใช้ ให้ตรวจ `GET /api/config/effective`
หรือหน้า Machine Setup พร้อม configuration revision เสมอ ค่า override ที่ต่างกันต้องแสดง warning
ไฟล์ที่ไม่มี `.iriv` เป็นโปรไฟล์อื่น ไม่ใช่ authority ของเครื่อง IRIV V1

## 2. ค่าปัจจุบันของโปรไฟล์ IRIV

| Axis | Drive type | pulses/rev | pulses/mm | Maximum travel | Default speed | Homing search/latch |
|---|---|---:|---:|---:|---:|---:|
| X | lead screw/effective calibration | 1,600 | 64.705882 | 1,700 mm | 5 mm/s | 20 / 5 mm/s |
| Y | lead screw/effective calibration | 1,600 | 64.705882 | 1,700 mm | 5 mm/s | 20 / 5 mm/s |
| Z | timing belt/pulley | 1,600 | 9.0 | 160 mm | 2 mm/s | 20 / 5 mm/s |

ทั้งสามแกนบันทึก `commissioned_max_speed_mm_s = 100` แต่ห้ามตีความว่า 100 mm/s ผ่านการทดสอบแล้ว
หากไม่มี commissioning record ที่ตรวจ driver alarm, PEND, position error และกลไก ให้ลดค่าลงเป็น
ความเร็วที่พิสูจน์แล้วก่อนใช้งาน production

## 3. สูตรมาตรฐาน

```text
pulses_per_rev = motor_steps_per_rev × driver_microsteps
pulses_per_mm = pulses_per_rev ÷ travel_per_rev_mm
travel_per_rev_mm = pulses_per_rev ÷ pulses_per_mm
pulse_hz = speed_mm_s × pulses_per_mm
rpm = pulse_hz × 60 ÷ pulses_per_rev
speed_mm_s = pulse_hz ÷ pulses_per_mm
```

เพดานเชิงตัวเลขคือค่าต่ำสุดของ `max_speed_mm_s`, `commissioned_max_speed_mm_s` และ
`max_pulse_hz ÷ pulses_per_mm` เพดาน NUCLEO หรือ pulse-input rating ของ driver
ไม่ใช่ความเร็วกลไกที่ปลอดภัย

## 4. X/Y lead screw และ effective calibration

จาก motor 200 step/rev และ microstep 8 จะได้ `pulses_per_rev = 1,600` แต่ค่าปัจจุบัน
`64.705882 pulse/mm` เทียบเท่า effective travel `24.727273 mm/rev` ซึ่งไม่เท่ากับ screw pitch
5 mm/rev ที่เคยอ้างไว้ ต้องตรวจ DIP switch, อัตราทด, pulse count และการวัด stroke อีกครั้ง

```text
calibrated_pulses_per_mm = observed_pulses ÷ measured_distance_mm
```

ห้ามปรับ pitch เพื่อทำให้ตัวเลขหน้าจอตรงเพียงอย่างเดียว ทดสอบอย่างน้อยสองระยะและสองทิศ
เพื่อค้นหา backlash หรือ pulse loss

## 5. Z timing belt/pulley

Z ไม่มี lead screw ค่า compatibility field `lead_screw_pitch_mm = 177.777778` หมายถึง effective
travel per motor revolution จาก `1,600 ÷ 9` ไม่ใช่ lead-screw pitch จริง

```text
pulley_travel_per_rev_mm = belt_pitch_mm × pulley_teeth ÷ gear_ratio
pulses_per_mm = pulses_per_rev ÷ pulley_travel_per_rev_mm
```

ปัจจุบัน belt pitch คือ 2 mm แต่ `pulley_teeth` ยังเป็น null จึงต้องถือ `9 pulse/mm` เป็น empirical
value ชั่วคราว ต้องยืนยันจาก pulse count Min→Max และระยะจริง 160 mm

## 6. Travel calibration workflow

1. สำรอง configuration และบันทึก revision
2. ตรวจ E-Stop, Stop, ALM, NUCLEO และ IRIV I/O
3. ใช้ความเร็วต่ำที่พิสูจน์แล้วและ Home ที่ Min
4. ผู้ควบคุมสั่ง Move to Max ซึ่งต้องจบด้วย physical Max sensor และ watchdog
5. บันทึก observed pulses และวัด Min→Max ด้วยเครื่องมือภายนอก
6. คำนวณ pulses/mm แล้วทำซ้ำ Max→Min เพื่อตรวจ backlash/pulse loss
7. กำหนด measured/software travel ตามพื้นที่ปลอดภัยจริง
8. แก้ `Machine Setup > Travel & Drive Setup`
9. ตรวจ effective values แล้ว `SAVE TO PI`
10. `APPLY & RESTART`, รอ Controller กลับมาและตรวจ revision
11. Home ใหม่และทดสอบระยะสั้นด้วยความเร็วต่ำ

Move to Min/Max ใช้ sensor จริงเป็น completion boundary; software travel ไม่ควรแทน sensor
แต่ E-Stop, Stop, alarm, communication fault และ watchdog ห้ามถูกปิด

## 7. Motor และ Homing Settings

| Parameter | ความหมาย | Validation สำคัญ |
|---|---|---|
| `motor_steps_per_rev` | full steps ต่อรอบ | มากกว่า 0 และตรง datasheet |
| `driver_microsteps` | microstep ของ driver | มากกว่า 0 และตรง DIP switch |
| `steps_per_mm` | pulse ต่อ 1 mm | ผ่าน empirical calibration |
| `max_travel_mm` | software coordinate สูงสุด | ไม่เกินช่วงปลอดภัย |
| `default_speed_mm_s` | speed เริ่มต้น | ไม่เกินทุก speed ceiling |
| `acceleration`, `deceleration` | ramp หน่วย mm/s² | เพิ่มทีละขั้นและตรวจ oscillation |
| `home_direction`, `forward_direction` | polarity ทิศทาง | เป็น 0/1 และตรงข้ามกัน |

- `home_position_mm` ต้องอยู่ระหว่าง 0 และ `max_travel_mm`
- search speed ใช้ค้นหาระยะไกล; latch speed ใช้ approach รอบยืนยัน
- timeout เป็น time watchdog ไม่ใช่จำนวน step จำกัด
- Homed เป็น true เมื่อ zero และ offset move สำเร็จเท่านั้น
- Protocol v3 จึงใช้ parallel Home All; v2 ต้อง fallback แบบลำดับ

## 8. PEND commissioning X/Y

PiControl local DI2 คือ `X_PEND` และ DI3 คือ `Y_PEND` เป็น in-position feedback ไม่ใช่ Drive Alarm

1. คง `commissioned=false` และ `require_transition=false`
2. ตรวจ raw/logical polarity ตอน idle
3. สั่งระยะสั้นที่ความเร็วต่ำภายใต้ผู้ควบคุม
4. ยืนยัน transition และเวลาที่กลับ stable หลายรอบ รวม zero-distance
5. ตั้ง `settle_timeout_ms` จากค่าที่วัดพร้อม margin
6. เปิด `commissioned=true` ทีละแกน
7. เปิด `require_transition=true` เมื่อ polling มองเห็น transition ทุกคำสั่งจริงเท่านั้น

PEND ไม่สามารถ bypass E-Stop/ALM หาก PEND ไม่มาเมื่อ commissioned แล้ว คำสั่งต้อง Failed
และไม่ควร Reset Drives อัตโนมัติ

## 9. Save, Validate และ Apply

1. `RESET CHANGES` คืนเฉพาะค่าที่ยังไม่ได้บันทึก
2. การแก้ field ต้องทำให้ dirty และ invalidate pending Validate/Arm
3. `SAVE TO PI` ต้อง validate และสร้าง backup ก่อน atomic write
4. Validation error ต้องห้าม Save และแสดง field/code
5. หลัง Save ต้องแสดง `restart_required=true`; process เดิมยังไม่ใช้ค่าใหม่
6. `APPLY & RESTART` ใช้เมื่อเครื่อง Idle และพื้นที่ปลอดภัย
7. รอ API กลับมาแล้วตรวจ `restart_required=false` และ revision ใหม่
8. ตรวจ Controller/NUCLEO/IRIV และ Home ใหม่

ห้ามกด Apply ซ้ำระหว่าง restart หากไม่กลับมาตามเวลา ให้ตรวจ service log และ effective configuration
แทนการสั่ง motion

## 10. Configuration acceptance record

- วันที่, ผู้ดำเนินการ และ revision ก่อน/หลัง
- DIP switch, motor steps, pulley teeth/ratio หรือ screw pitch ที่ตรวจจริง
- measured distance, observed pulses และ pulses/mm
- search/latch/default/commissioned speed พร้อมผล ALM/PEND
- backup path และผล validation
- ผล Home ซ้ำ, short move, bidirectional move และ external position measurement
## 11. การตั้งค่า S-curve สำหรับแกน X/Y (Phase 8)

ไฟล์ `machine_config.iriv.json` และ `hardware_config.iriv.json` มีค่าต่อไปนี้สำหรับแกน X และ Y เท่านั้น:

- `scurve_enabled`: เปิดใช้โปรไฟล์ S-curve (ค่าเริ่มต้น `false`)
- `scurve_profile_type`: ต้องเป็น `seven_segment_s_curve`
- `scurve_start_speed_mm_s` และ `scurve_end_speed_mm_s`: ความเร็วขอบเขตของโปรไฟล์
- `scurve_max_jerk_mm_s3`: เพดาน jerk ต้องมากกว่า 0
- `scurve_control_period_us`: คาบควบคุม 100–10,000 ไมโครวินาที

หน้า Machine Setup แสดงค่าชุดนี้เฉพาะการ์ด X/Y และบันทึกลง machine/hardware configuration แบบ atomic พร้อม backup ได้แล้ว ส่วน preview เป็นการคำนวณเพื่อทบทวนค่าบนหน้าเว็บเท่านั้นและไม่สั่ง motion สวิตช์ Enable จะถูกปิดไว้จนกว่า NUCLEO handshake จะรายงาน buffered S-curve capability จริง

ค่า production ปัจจุบันยังเป็น `scurve_enabled = false` และยังไม่ถูกส่งไปควบคุมมอเตอร์ ห้ามเพิ่มค่าเหล่านี้ให้แกน Z เพราะ Z ต้องใช้ motion path เดิม

Controller แสดง routing matrix ใน status payload แยกตามแกนและชนิดคำสั่ง หากเปิด S-curve แล้ว capability หรือ runtime หาย ระบบต้อง block คำสั่งแทนการ fallback เงียบ ๆ ปัจจุบัน Home และ Limit Seek ยังไม่ใช้ S-curve เพราะเป็นคำสั่งที่ต้องหยุดตาม sensor และ buffered contract รุ่นปัจจุบันรองรับเฉพาะระยะ/pulse ที่ทราบล่วงหน้า

Sensor-terminated contract ที่เตรียมไว้กำหนด sensor เป็น `X_MIN`, `X_MAX`, `Y_MIN` หรือ `Y_MAX`, เลือกหยุดแบบ `controlled` สำหรับ search หรือ `immediate` สำหรับ latch และบังคับ watchdog 0.1–3,600 วินาที Firmware ต้องประกาศ `sensor_terminated_profile`, `axis_sensor_stop` และ `profile_watchdog` ผ่าน handshake ครบทุกค่า จึงจะถือว่ารองรับ ห้ามอนุมานจาก protocol version เพียงอย่างเดียว

มี firmware candidate แบบ HAL-independent สำหรับกำกับการหยุด X/Y แยกแกนแล้ว: แกนที่พบ sensor จะหยุดโดยไม่บังคับให้อีกแกนหยุด, ตรวจ sensor ที่ active ก่อนเริ่ม, มี watchdog ต่อแกน และ global safety stop แบบ latch ซึ่งต้อง Reset ก่อนเริ่มใหม่ โค้ดส่วนนี้ผ่าน host test แต่ยังจงใจไม่รวมใน CubeIDE build และยังไม่อนุญาตให้เปิด `scurve_enabled` บนเครื่องจริงจนกว่าจะเชื่อม facade/HAL, build, handshake และผ่าน commissioning

Candidate parser/facade รับกรอบ `SENSOR_PROFILE` แยกจาก `PROFILE` แล้ว และห้ามเริ่มกรอบชนิดนี้ผ่าน bounded-profile start path เพื่อป้องกันการข้าม sensor supervisor เมื่อ sensor ทำงาน facade จะหยุด scheduler เฉพาะแกนนั้น ส่วน sensor watchdog หรือ global safety fault จะหยุดทุกแกนแบบ fail-safe ใน candidate ปัจจุบันทั้ง `controlled` และ `immediate` ปิด pulse ของแกนทันที; การทำ controlled deceleration ก่อนถึงจุดหยุดจริงต้องเพิ่ม pre-trigger/deceleration contract และพิสูจน์ระยะหยุดก่อน commissioning จึงยังไม่โฆษณาความสามารถนี้กับเครื่องจริง

ฝั่ง Raspberry Pi มี ASCII serializer ที่สร้าง `PROFILE` และ `SENSOR_PROFILE` ตาม field order ของ C parser พร้อม checksum และมี sensor-profile wire adapter แยก stage/start แล้ว Adapter ปิดไว้โดยค่าเริ่มต้นและปฏิเสธก่อนส่งหาก handshake ขาด capability ใด capability หนึ่ง ปัจจุบันทดสอบผ่าน injected mock exchange เท่านั้นและยังไม่ได้ต่อเข้ากับ production `NucleoLink`

Candidate UART dispatcher จำกัด command line ไม่เกิน 1,023 bytes, รับเฉพาะ `SENSOR_PROFILE` และ `SENSOR_START`, ตรวจจำนวน frame ก่อน start และตอบ JSON ACK/error แบบคงที่ Input ที่มี newline ซ้อน, trailing token, command ไม่รู้จัก หรือยาวเกินกำหนดจะถูกปฏิเสธ ชุด host test ครอบคลุม feature flag ทั้งปิด/เปิดและ deterministic malformed-input fuzz แต่ dispatcher ยังไม่รวมใน CubeIDE source list
