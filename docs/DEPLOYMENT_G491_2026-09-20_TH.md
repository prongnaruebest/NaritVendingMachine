# รายงาน Deploy NUCLEO-G491RE วันที่ 2026-09-20

## ขอบเขต

Deploy Controller/Web release `61ef6a957a8e-c4051c40de67` และทดสอบ Flash firmware Protocol v4 โดยไม่สั่ง Home, Jog, GOTO, Dispense หรือ Demo Sampling

## ผล Controller/Web

- Controller และ Web services ทำงานปกติ
- `/health/live` เป็น `UP`
- configuration revision คือ `5b9251d300995610ff7672311637f50413836bd0009fbbbfd92dd63eb860979e`
- Controller เริ่มต้นโดย `motion_enabled = false`
- automated tests บน development host ผ่าน `515 tests` และ `22 subtests`

## เครื่องมือ Flash และ rollback

- `stlink-tools 1.6.1` ของ Debian ไม่รู้จัก STM32G491RE chip ID `0x479`
- สร้าง `stlink` จาก upstream commit `a7bfb83000567f775b3780dac24ae6f02e449327` แยกไว้ที่ `/opt/stlink-g491`
- สำรอง Flash เดิมครบ 524,288 bytes ก่อนเขียนทุกครั้ง
- SHA-256 rollback image: `cc9d3ff468dae158433f2d887ae7e0b902724574d5fad8312b8e97b3acfbdf9c`
- Backup อยู่ที่ `/home/admin/NaritVendingV1/backups/pre-c5e8b32-20260920-161023/firmware/`

## ผล Flash candidate

- Candidate SHA-256: `750bb9600caccc68b5c12ffa2ad535fa5e438028a5a364ee9db1d23d07fcaa34`
- `st-flash` เขียนสำเร็จและอ่านกลับมาเทียบกับ candidate ตรงกันทุก byte
- หลัง boot Controller ไม่ได้รับ heartbeat จาก NUCLEO ผ่าน ST-LINK VCP และรายงาน `Nucleo heartbeat timed out`
- ไม่พบ capability handshake จึงไม่ผ่าน release gate และไม่มีการเปิด Motion

## การ rollback

- เขียน rollback image เดิมกลับครบ 512 KiB
- อ่าน Flash หลัง rollback และเทียบตรงกันทุก byte
- หลัง rollback NUCLEO กลับมา online, Protocol 4, safe และ disarmed
- IRIV I/O online, X/Y driver alarm ไม่ active และ Motion ยังคง disabled

## งานที่ต้องทำต่อ

ตรวจ firmware startup path ของ candidate โดยเน้น clock, USART/VCP initialization, interrupt/DMA configuration, heartbeat scheduling และ watchdog boot state ก่อนสร้าง artifact ใหม่ ห้าม Flash ซ้ำจน host-side tests, clean build และ serial-handshake bench gate ผ่าน

## Root cause ที่ยืนยันภายหลัง

Debugger ยืนยันว่า CPU ติดอยู่ใน `TIM6_DAC_IRQHandler` ขณะ `HAL_TIM_Base_Start_IT()` ยังไม่คืนค่ากลับมาที่ startup code สาเหตุคือ TIM6 update interrupt เกิดขึ้นทันที แต่ `NucleoG491ControlTimer.running` ยังเป็น 0 ทำให้ handler return โดยไม่ clear UIF และเกิด interrupt storm ก่อนเริ่ม serial link

แก้โดยตั้ง `running = 1` ก่อน enable timer interrupt และ rollback ค่าเป็น 0 หาก HAL start ล้มเหลว พร้อมเพิ่ม C host regression test ที่บังคับให้ ISR เกิดภายใน `HAL_TIM_Base_Start_IT()` เพื่อป้องกันบัคนี้ย้อนกลับมา

## ผลยืนยันหลังแก้ไข (2026-09-21)

- Firmware commit: `4a7a5e1`
- Candidate SHA-256: `e17cf5350c55a3292cef377d2341da34e2a3241752cf3c52fd05b9afb5fe084e`
- Clean build สำเร็จ และ automated tests ผ่าน `516 tests` กับ `22 subtests`
- Flash และ read-back verification ตรงกับ candidate ทุก byte
- NUCLEO handshake ผ่านด้วย Protocol 4 และ capabilities ครบ รวม `terminal_rate_config`
- Controller รายงาน `supports_buffered_scurve = true`
- หลัง deploy NUCLEO ยัง disarmed/safe, Motion disabled, IRIV I/O online และไม่มี X/Y driver alarm
- ไม่มีการสั่ง Home, Jog, GOTO, Dispense หรือ Demo Sampling ระหว่าง deploy และ verification

## Deploy UART-interrupt heartbeat firmware (2026-09-21)

- Source revision และ Controller package revision: `dff96fd9044432497a5bfe9fcae981c22c36d8e2`
- Clean Release build ของ NUCLEO-G491RE สำเร็จ: text 35,024 bytes, data 112 bytes,
  bss 4,248 bytes; linker ยังเตือน RWX LOAD segment และต้องแก้ในงาน hardening ถัดไป
- Firmware BIN SHA-256:
  `b23340012a4c478c40a3aaeb44a57493991d3c54dfcd829b31f4800a82e86c58`
- Artifact manifest ระบุ Protocol 4 และ capability
  `dynamic_watchdog_heartbeat` ตรงกับ firmware handshake
- สำรอง Controller, configuration และ SQLite databases ก่อน deploy ที่
  `/home/admin/NaritVendingV1/backups/pre-dff96fd-20260921-150731/` และตรวจ
  `SHA256SUMS.txt` ผ่านทุกไฟล์
- Deploy เฉพาะ `narit_vending/nucleo.py` ที่เปลี่ยนใน Controller layer;
  `motion.py` บนเครื่องมี SHA-256 ตรงกับ source อยู่แล้ว
- Flash ผ่าน ST-LINK mass-storage `NOD_G491RE1`; volume รับ image และไม่สร้าง
  `FAIL.TXT` จากนั้น VCP กลับมาที่ stable by-id path เดิม
- ข้อจำกัด: รอบนี้ไม่ได้ทำ full-flash read-back byte comparison แบบ `st-flash`;
  หลักฐานการ activate คือ board reboot, Protocol 4 handshake และ capability ใหม่
  `dynamic_watchdog_heartbeat` จาก firmware ที่กำลังรัน
- หลัง restart Controller/Web เป็น active, `/health/live` และ `/health/ready` ตอบ 200,
  IRIV I/O และ NUCLEO online, E-Stop/driver alarms clear, UART overrun/drop และ
  watchdog trip เป็นศูนย์
- Controller ปลด dynamic-motion quarantine ตาม capability ใหม่ แต่ Motion ยังคง
  disabled, NUCLEO safe/disarmed, axes not homed และไม่มี active command
- `heartbeat_age_ms` ขณะ disarmed เท่ากับระยะเวลาตั้งแต่ boot เพราะ metric นี้วัด
  อายุของ dynamic-motion heartbeat ล่าสุด; ต้องประเมิน `max_heartbeat_gap_ms` และ
  `watchdog_trip_count` ระหว่าง commissioning motion จึงจะยืนยัน 500 ms watchdog
  path ภายใต้ pulse load ได้
- ไม่มี Home, Jog, GOTO, Dispense, drive-power reset หรือ Demo Sampling ระหว่าง
  deploy และ health verification รอบนี้

## Low-speed commissioning หลัง deploy (2026-09-21)

ผู้ควบคุมยืนยันว่าพื้นที่เครื่องปลอดภัยก่อนเริ่ม motion จริง การทดสอบใช้ลำดับ
single-axis ก่อน coordinated motion และตรวจ interlock/telemetry หลังทุก gate:

- Manual Commissioning X+ และ Y+ อย่างละประมาณ 5 mm ที่ 20 mm/s ผ่าน;
  Min switch release ถูกทิศและไม่มี driver alarm
- Home All ที่ search 50 mm/s และ latch 5 mm/s ผ่านครบ X/Y/Z
- Dynamic X+ 10 mm ที่ 20 mm/s ถึง 647/647 pulses และ terminal velocity/acceleration
  เป็นศูนย์
- พบ regression เมื่อ Dynamic X- กลับ target 0 mm: Min sensor ทำงานก่อน virtual
  pulse position ถึงศูนย์ ทำให้ Controller จัดเป็น limit fault และล้าง Homed state
- แก้ใน commit `9b4edb4` โดยยอมรับเฉพาะ single-axis, ทิศ Home, target 0 pulses
  และ Min active เป็น sensor-terminated zero completion; E-Stop, Stop, non-zero target,
  Max และ multi-axis limit stop ยังคง fail-closed
- Host automated tests หลังแก้ผ่าน `527 tests` และ `22 subtests`; deploy เฉพาะ
  `motion.py` กับ `domain/motion_policy.py` หลังสำรองไว้ที่
  `/home/admin/NaritVendingV1/backups/pre-9b4edb4-20260921-190525/`
- Retest Dynamic X ±10 mm และ Y ±10 mm ที่ 20 mm/s ผ่าน ตำแหน่งกลับ 0 steps
  และ Homed state ยังคงถูกต้อง
- Coordinated X+/Y+ จาก 0 ไป 10/10 mm ที่ 20 mm/s ผ่าน ทั้งสองแกนรายงาน
  647 pulses จากนั้น Home All กลับจุดอ้างอิงผ่าน
- Maximum heartbeat gap ที่พบตลอดรอบคือ 127 ms ต่ำกว่า watchdog 500 ms;
  watchdog trip, UART overrun และ dropped RX bytes เป็นศูนย์
- สถานะสุดท้าย: services active, health UP, Machine READY, X/Y/Z homed ที่ 0 mm,
  Motion Enabled, NUCLEO safe/disarmed, ไม่มี active command, E-Stop/driver alarms clear
- ยังไม่ได้ทดสอบ speed ramp ที่สูงกว่า 20 mm/s, GOTO Slot, Demo Sampling หรือ
  9-stage vending sequence กับ firmware นี้ จึงห้ามถือว่า release ผ่าน full-speed
  mechanical commissioning

### Speed ramp gate 40 mm/s

- ผู้ควบคุมยืนยันพื้นที่ปลอดภัยสำหรับ X/Y ไป-กลับ 50 mm ที่ 40 mm/s
- Dynamic X+ และ X- ระยะ 50 mm ผ่าน: ปลายทางบวก 3,235 pulses (49.995 mm)
  และกลับ Min/0 โดย Homed state ยังคงถูกต้อง
- Dynamic Y+ และ Y- ระยะ 50 mm ผ่านด้วยผลเทียบเท่า X
- Coordinated X+/Y+ ไป 50/50 mm ที่ 40 mm/s ผ่าน ทั้งสองแกนรายงาน 3,235 pulses
- Home All หลังทดสอบผ่านและคืน X/Y/Z ที่ 0 mm
- Maximum heartbeat gap ใน gate นี้ 125 ms; watchdog trip, UART overrun,
  dropped RX bytes และ X/Y driver alarms เป็นศูนย์
- สถานะสุดท้ายยังเป็น Machine READY, Motion Enabled, NUCLEO safe/disarmed,
  ไม่มี active command และ services/health UP
- Gate นี้ยังไม่ครอบคลุมความเร็วสูงกว่า 40 mm/s, ระยะ Slot จริง, Z sequence,
  Demo Sampling หรือ 9-stage vending sequence

### Speed ramp gate 60 mm/s

- ผู้ควบคุมยืนยันพื้นที่ปลอดภัยสำหรับ X/Y ไป-กลับ 100 mm ที่ 60 mm/s
- Dynamic X และ Y ไป-กลับ 100 mm ผ่าน: ปลายทางแต่ละแกน 6,471 pulses
  (100.006 mm) และกลับ Min/0 โดย Homed state ยังคงถูกต้อง
- Coordinated X+/Y+ ไป 100/100 mm ที่ 60 mm/s ผ่าน ทั้งสองแกนรายงาน
  6,471 pulses จากนั้น Home All กลับ X/Y/Z ที่ 0 mm ผ่าน
- Maximum heartbeat gap ใน gate นี้ 128 ms; watchdog trip, UART overrun,
  dropped RX bytes และ X/Y driver alarms เป็นศูนย์
- สถานะสุดท้าย Machine READY, Motion Enabled, NUCLEO safe/disarmed,
  ไม่มี active command และทุกแกน Homed
- Gate นี้ยังไม่ครอบคลุม GOTO Slot ระยะจริง, Z pick/drop, Demo Sampling,
  9-stage vending sequence หรือความเร็วสูงกว่า 60 mm/s

### GOTO Slot 27 terminal-approach regression

- การทดสอบ GOTO Slot 27 ที่ 40 mm/s ยก Z ไป 85 mm สำเร็จ แต่ Dynamic Y จาก
  0 ไป 340 mm ไม่จบภายใน timeout 22 วินาที; Controller จึง STOP, Disarm,
  ล้าง Homed ของ X/Y และคง Stop latch ตาม fail-closed policy
- Driver alarm, E-Stop, USB watchdog, UART overrun และ RX drop ไม่ทำงานระหว่าง
  เหตุการณ์ จึงตัดสาเหตุด้าน safety input/transport ออกได้
- พบว่า Controller ส่ง `kp_enabled=0`; แก้ให้ X/Y Dynamic route เปิด Virtual Kp
  ที่ 2.5/s เพื่อให้ requested rate ลดตาม remaining pulses ก่อนผ่าน
  jerk/acceleration/deceleration envelope
- เพิ่ม C host regression ระยะ Y 22,000 pulses (Slot 27 ที่ 340 mm) และ Python
  protocol assertion; full automated suite ผ่าน 527 tests และ 22 subtests
- Diagnostic retest ยืนยันว่า firmware ทำ Y ครบ 22,000 pulses และรายงาน COMPLETE
  แต่ X ซึ่งมีระยะ 0 pulse อยู่ IDLE; Controller รอ X=COMPLETE จึงเกิด false timeout
- แก้ใน commit `69a86c2` ให้ stage/start เฉพาะแกนที่มีระยะมากกว่า 0 pulse
  พร้อม regression test X=0/Y=340 mm; ไม่ลดระดับ interlock หรือ completion criteria
- หลัง deploy รอบสุดท้าย Home All ถูกหยุดเพราะ X Min ยัง active หลัง backoff 647 pulses
  (ประมาณ 10 mm) จึงยังไม่ retest Slot 27 หลัง fix; Controller ถูก Disable Motion,
  NUCLEO safe/disarmed และ Stop latch ยังคง active เพื่อรอตรวจ X Min หน้าเครื่อง

### X Max limit-seek diagnostic

- ผู้ควบคุมยืนยันพื้นที่ปลอดภัยสำหรับ X+ ไปหา Max ที่ไม่เกิน 20 mm/s
- เนื่องจาก X ยังไม่ Homed และ firmware รายงาน
  `supports_sensor_terminated_scurve=false` คำสั่งนี้ต้องใช้ Controller-owned legacy
  `LIMIT_SEEK`; ยังไม่ใช่ Dynamic Virtual-Kp route
- Controller ส่งเฟรม `MOVE X 0 1000000 1294`; NUCLEO ACK moving และ telemetry
  รายงาน X moving โดย E-Stop, ALM X/Y และ USB watchdog ไม่ทำงาน
- หลังเวลามากกว่าระยะเดินทางเชิงทฤษฎี X Min ยังคง active และ X Max ไม่ active
  จึงส่ง STOP ทันทีแทนการรอ watchdog เต็มช่วง
- สถานะหลังหยุด: Motion Disabled, Stop latched, NUCLEO safe/disarmed,
  X/Y alarm clear และ KM1 power feedback true
- ผลนี้ชี้ว่า command/USB/pulse path ทำงาน แต่ยังไม่มีหลักฐานว่ากลไก X เคลื่อนออกจาก
  Min ต้องตรวจ LED/Enable ของ HBS860H, มอเตอร์/คัปปลิง/สกรู, DIR wiring และสถานะ
  IRIV DI0 ด้วยการสังเกตหน้าเครื่องก่อน motion ครั้งถัดไป
- ห้ามทดสอบ Kp absolute move จนกว่าจะสร้าง reference coordinate ที่เชื่อถือได้จาก
  physical limit และ `is_homed=true`
- Retest หลังผู้ควบคุมยืนยันว่าสวิตช์ปกติ: ส่ง X+ 20 mm/s และตรวจ live state
  หลัง 10 วินาที แต่ IRIV DI0/X Min ยังคง active จึง STOP และ Disable Motion
  ทันทีตาม gate; X Max ไม่ active, ALM clear และ NUCLEO กลับ safe/disarmed
- ต้องทำ live press/release observation ของ physical X Min เทียบกับ raw IRIV DI0
  ก่อนทดสอบต่อ เพื่อแยก polarity/mapping fault ออกจากกลไกไม่ออกจากสวิตช์

### X drive 7-flash following-error mitigation

- ระหว่าง Home ผู้ควบคุมพบไฟแดง HBS860H แกน X กระพริบ 7 ครั้ง ซึ่งตามตาราง
  diagnostic ของไดรฟ์หมายถึง Position Following Error
- Legacy Home เริ่ม pulse ที่ความถี่คงที่โดยไม่มี acceleration ramp; ค่าเดิม
  50 mm/s เท่ากับประมาณ 3,235 pulse/s จึงเป็น step input ที่อาจทำให้โรเตอร์ตามไม่ทัน
- ลด `homing_search_speed_mm_s` เฉพาะ X/Y เป็น 20 mm/s (ประมาณ 1,294 pulse/s)
  และคง precision latch 5 mm/s; Z ยังคง 50 mm/s เพราะใช้ DM542 และกลไกสายพาน
- การเปลี่ยนนี้เป็น mitigation ไม่ใช่หลักฐานว่า mechanical fault ถูกแก้แล้ว ต้องตรวจ
  binding, coupling, drive current และทดสอบ Home ด้วยผู้ควบคุมหน้าเครื่องภายหลัง
- ขณะเกิดไฟแดง Controller ยังรายงาน `X_DRIVE_ALM=false`; ดังนั้น DI0 wiring,
  common, voltage level และ active polarity ต้อง commissioning ก่อนถือว่า software
  interlock ตรวจจับ fault ของไดรฟ์ X ได้จริง ห้ามกลับ polarity จากซอฟต์แวร์โดยเดา

### Repeated Jog after controlled release

- หลัง Home สำเร็จ Hold-to-run Jog X/Y ใช้ Dynamic S-curve ได้ แต่การปล่อยปุ่ม
  ทำให้ Controller ล้าง Homed โดยไม่มีการรับตำแหน่งหยุดจริงจาก NUCLEO จึงกด Jog
  ครั้งถัดไปไม่ได้
- แก้ transport ให้ขอ terminal `DYN_STATUS` หลัง `CONTROLLED_STOP` และก่อน Disarm
  จากนั้น Controller อัปเดต `position_steps` จาก confirmed STEP-edge coordinate
- รักษา Homed เฉพาะเมื่อ `position_valid=true` และ `position_pulses` อยู่ใน travel
  range; telemetry หาย/ผิดรูป/เกินขอบเขตยังล้าง Homed แบบ fail-closed
- ตำแหน่งนี้เป็น open-loop emitted-pulse coordinate ไม่ใช่ encoder-measured position
