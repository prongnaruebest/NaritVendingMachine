# คู่มือเว็บควบคุม NaritVendingMachine

คู่มือนี้ใช้กับ HMI ปัจจุบันที่ `http://192.168.70.80/` สำหรับควบคุมเครื่องจริงผ่าน Controller และ NUCLEO USB ห้ามใช้หน้าเว็บแทนการตรวจความปลอดภัยทางกายภาพ

## ขอบเขตและหลักสำคัญ

- Browser ไม่ได้ควบคุม GPIO หรือ STEP/DIR โดยตรง ทุกคำสั่งต้องผ่าน Controller และ safety interlock
- สถานะ `Online` หมายถึงสื่อสารได้ ไม่ได้แปลว่าเครื่องพร้อมเคลื่อน ต้องดู `Machine Readiness` และ `Motion Authority` แยกกัน
- ปุ่ม `Enable Motion` ให้สิทธิ์คำสั่งในอนาคตเท่านั้น ไม่เริ่ม Home, Jog หรือ Move
- ปุ่ม `Disable Motion`, `Stop Motion` และ E-Stop มีหน้าที่ต่างกัน ห้ามใช้แทนกันในการแก้ปัญหาทางกล
- ค่าตำแหน่งจากซอฟต์แวร์เชื่อถือได้หลัง Home สำเร็จและ reference ยังไม่ถูกล้างเท่านั้น

## Quick Start สำหรับการทำงานปกติ

1. ตรวจพื้นที่, wiring และไฟเลี้ยงด้วยสายตา
2. เปิด Overview แล้วตรวจ Controller, NUCLEO และ IRIV I/O
3. ตรวจ `E-Stop / KM1 = CLEAR`, Drive Alarm = Clear และ Motion queue ว่าง
4. กด Reset Alarms เฉพาะหลังแก้ต้นเหตุแล้ว
5. กด Enable Motion และยืนยันว่า Motion Authority แสดง Enabled
6. Home แกนที่จะใช้งาน หรือ Home All
7. ตั้ง Speed X/Y/Z จาก control ชุดเดียวในหน้า Motion
8. เลือก Jog, Move, Slot หรือ Demo ตามงาน
9. หลังงานจบ รอ Idle แล้ว Disable Motion

## ความหมายสถานะหลัก

| สถานะ | ความหมาย | สิ่งที่ผู้ใช้ควรทำ |
|---|---|---|
| Controller Online | Web ติดต่อ process เจ้าของ motion ได้ | ตรวจ readiness ต่อ |
| NUCLEO Safe Link | USB handshake/heartbeat อยู่ในสถานะที่รายงานว่าปลอดภัย | ตรวจ protocol capability และ Home |
| IRIV I/O Online | Modbus polling ทำงาน | ตรวจ stale timestamp และ logical inputs ต่อ |
| Motion Authority Disabled | Controller ปฏิเสธ motion ใหม่ | แก้ interlock แล้ว Enable Motion |
| Not Homed | machine coordinate ของแกนนั้นยังเชื่อถือไม่ได้ | Home แกนนั้นก่อน normal motion |
| Busy / Active Command | มีคำสั่งอยู่ในการประมวลผล | รอหรือ Stop; ห้ามกดคำสั่งซ้ำ |
| Alarm / Inhibited | มี safety หรือ device fault | อ่าน reason และแก้ต้นเหตุก่อน Reset |

## ก่อนเริ่มใช้งาน

1. ตรวจพื้นที่เคลื่อนที่ X/Y/Z และนำสิ่งกีดขวางออก
2. ตรวจว่า E-Stop ทางกายภาพใช้งานได้และ DI10 แสดง `HIGH / CLEAR`
3. ตรวจหน้า System Control & Health: Controller, IRIV I/O และ NUCLEO ต้อง Online
4. ปลด E-Stop, กด **Reset Alarms** แล้ว **Enable Motion** ตามลำดับ
5. Home แกนที่ต้องใช้งาน ก่อนสั่ง Jog, GOTO หรือ Demo

> X/Y มีการตัดไฟ 60 V ทางกายภาพ ส่วน Z ในปัจจุบันหยุด STEP pulse ด้วยซอฟต์แวร์เท่านั้น จึงต้องติดตั้ง safety relay/contactor สำหรับ Z ก่อนถือว่าเป็น E-Stop ที่สมบูรณ์

## เมนูและหน้าที่ของแต่ละหน้า

- **Overview:** สถานะเครื่อง การเชื่อมต่อ Alarm ตำแหน่ง และคำสั่งปัจจุบัน
- **Motion Control:** Homing Workflow, Jog, Min/Max และ GOTO XYZ
- **Positions & Slots:** แก้และบันทึกพิกัด Slot; Save ไม่ทำให้เครื่องเคลื่อนที่
- **Machine Visualization:** ภาพตำแหน่งจริง/เป้าหมาย เลือก Slot และ Demo Slot Sampling
- **Diagnostics & I/O:** DI/DO พร้อม raw/logical state, polarity, debounce, transition/noise counter, Alarm พร้อมแนวทาง recovery, Event และรายละเอียด protocol
- **Machine Setup:** Motor, Homing, I/O, USB และ Manual Commissioning
- **System Control & Health:** เปิด/ปิดสิทธิ์ Motion และกู้ USB handshake
- **MQTT Monitor:** สถานะ broker และข้อความ โดยไม่เป็นเจ้าของ Motion

## Homing Workflow

1. ตรวจ E-Stop, Controller, IRIV I/O และ NUCLEO
2. กด Home X, Home Y, Home Z หรือ Home All
3. ต่อแกนจะทำ Search → Back off → Latch approach → Zero → Home-position offset
4. ระบบตั้ง `is_homed=true` เมื่อทุกขั้นของแกนนั้นสำเร็จเท่านั้น
5. Protocol v3 รองรับ Home All พร้อมกัน; firmware ที่ไม่รองรับต้อง fallback แบบลำดับ

Home search อาศัย sensor จริงและ time watchdog ไม่ใช้ software position limit เป็นตัวหยุดค้นหา หาก sensor ค้างหรือไม่ทำงาน คำสั่งต้องจบเป็น Failed

หากแกนเริ่มต้นอยู่บน Min sensor ระบบต้อง Back off ให้ sensor release แล้วจึง approach ซ้ำด้วย latch speed
ห้ามจับหรือดันแกนด้วยมือระหว่าง Home หาก Home ล้มเหลวให้อ่าน phase และ Event Log ก่อนสั่งซ้ำ

## Speed X/Y/Z

- Slider และช่องตัวเลขของแต่ละแกนใช้ shared state เดียวกันทุกหน้า
- Jog และ Min/Max ใช้ speed ของแกนนั้น
- คำสั่งหลายแกนใช้ค่าที่ Controller/backend รองรับโดยไม่เกิน limit ของแกนร่วมเคลื่อนที่
- ค่าที่รับได้ต้องไม่เกิน commissioned speed, axis maximum และ `max_pulse_hz / pulses_per_mm`
- การเปลี่ยน speed มีผลกับคำสั่งถัดไปเท่านั้น ไม่เปลี่ยนคำสั่งที่กำลังวิ่ง
- หลังเปลี่ยน speed ปุ่ม Jog และ Min/Max ของแกนที่ Home แล้วต้องใช้งานต่อได้ทันที
- ถ้าปุ่มถูกล็อก ให้วาง pointer/focus ที่ปุ่มเพื่ออ่านเหตุผล เช่น `Y not homed — home that axis first`
- หากเปลี่ยน speed หลัง Validate/Preview/Arm ของ GOTO ต้องทำขั้นตอนดังกล่าวใหม่ เพราะ arm token เดิมถูกยกเลิกเพื่อความปลอดภัย

## Jog

1. เลือก Jog step และ speed ของแกน
2. กดสั้นเพื่อเคลื่อนหนึ่ง step หรือกดค้างสำหรับ hold-to-run
3. ปล่อยปุ่ม, browser blur, page hidden หรือ connection loss ต้องหยุด
4. Normal Jog ต้อง Home แกนนั้นก่อน และห้าม bypass software limits

เมื่อ Min หรือ Max sensor ทำงาน ต้อง disable เฉพาะปุ่มที่เคลื่อนเข้าหา sensor ทิศตรงข้ามต้องยังใช้ถอยออกได้
หากทั้งสองทิศถูกปิด ให้ตรวจ Stop latch, Motion Authority, Homed, driver alarm และ stale connection แทนการ Reset ซ้ำ

## Move to Min/Max

1. Home แกนที่ต้องการ
2. ตั้ง speed ของแกน
3. ตรวจ Current position, travel range และ Min/Max sensors
4. กด Min หรือ Max และยืนยันว่าพื้นที่ปลอดภัย

คำสั่งระยะยาวไม่ต้องแบ่งระยะเอง Controller จะแบ่งจำนวน pulse ตาม capability `max_move_steps` ที่ NUCLEO handshake รายงานโดยอัตโนมัติ ห้ามยึดค่าคงที่จากหน้าเว็บ และ Controller ยังคงตรวจ Stop/E-Stop/limit ระหว่าง segment

คำสั่งนี้เป็นการค้นหา physical endpoint: sensor ที่เลือกเป็นเงื่อนไขจบคำสั่ง ไม่ใช่ margin จาก software travel
แต่ E-Stop, Stop, driver alarm, communication fault และ watchdog ยังทำงานเสมอ เมื่อชน Max แล้วต้องสั่งทิศ Min
หรือ target ที่ต่ำกว่าปัจจุบันเพื่อถอยออกได้ การ Reset alarm ไม่ใช่เงื่อนไขบังคับหากไม่มี alarm จริง

## Move รายแกนไปยังตำแหน่ง

1. ตรวจว่าแกนนั้น Homed และ Motion Authority Enabled
2. ใส่ Target position หน่วย mm ใน X, Y หรือ Z
3. ตรวจว่าค่าอยู่ระหว่าง 0 และ travel ของแกน
4. ตรวจ speed ของแกนจาก shared speed control
5. กด `MOVE X`, `MOVE Y` หรือ `MOVE Z`

การเคลื่อนที่ศูนย์ระยะ เช่น Z อยู่ที่ค่าเดิมแล้วเปลี่ยนเฉพาะ X/Y ต้องไม่ถือเป็น error
ถ้าคำสั่งถูกปฏิเสธให้อ่าน reason; ห้ามเพิ่ม target เกิน travel เพื่อบังคับให้เคลื่อน

## อ่านหน้า Diagnostics & I/O

- `RAW` คือบิตไฟฟ้าที่อ่านจาก IRIV I/O ส่วนสถานะ `TRIGGERED/CLEAR` คือค่าหลังใช้ polarity และ debounce แล้ว
- `Transitions` แสดงจำนวนการเปลี่ยน logical/raw นับตั้งแต่ Controller เริ่มทำงาน ถ้า raw เพิ่มแต่ logical ไม่เพิ่ม แสดงว่าการเปลี่ยนนั้นถูก debounce กรองออก
- `Filtered noise` ใช้ชี้ช่องที่มี pulse สั้นหรือ contact bounce ค่าสูงผิดปกติควรตรวจสาย, shield, ground, ระยะสาย และแหล่งรบกวน ห้ามแก้ด้วยการเพิ่ม debounce อย่างเดียวโดยไม่ตรวจฮาร์ดแวร์
- `Last change` และ `Last active` ช่วยเทียบเวลาที่ sensor/limit ทำงานกับ Event Log
- Counter เหล่านี้เริ่มใหม่เมื่อ Controller restart และไม่ใช่ประวัติถาวร

## อ่านและกู้ Alarm

- หน้า Alarms เรียงรายการที่ Active ก่อน และแสดง `RECOVERY` สำหรับสาเหตุแต่ละประเภท
- แก้สาเหตุทางกายภาพหรือการสื่อสารก่อนกด Reset Alarms; ปุ่ม Reset ไม่ควรใช้เพื่อบังคับข้าม fault
- หน้า System Control & Health แสดงประวัติ System/Safety ล่าสุดของ session เพื่อยืนยันว่า Enable, Disable, Reset หรือ connection change เกิดขึ้นเมื่อใด
- หน้า Event Log กรองตาม Severity/Category/Outcome/Search แล้วกด **Export CSV** เพื่อบันทึกรายการที่กรองอยู่ได้
- Event history ฝั่งหน้าเว็บเป็น in-memory ล่าสุด 200 รายการ จึงไม่ใช่ audit log ถาวรและจะเริ่มใหม่เมื่อ reload หน้า

## PEND ของไดรฟ์ X/Y

- `X_PEND` ที่ PiControl DI2 และ `Y_PEND` ที่ DI3 เป็นสัญญาณยืนยันว่าไดรฟ์เข้าเป้าหมาย ไม่ใช่ Drive Alarm
- ค่าเริ่มต้น `commissioned=false` ทำให้ระบบแสดงสถานะเพื่อวินิจฉัยเท่านั้น และไม่ใช้ตัดสินผลคำสั่ง motion
- หลังตรวจ polarity, การเปลี่ยนสถานะระหว่างวิ่ง และเวลาที่ใช้ settle กับเครื่องจริงแล้ว จึงตั้ง `commissioned=true` แยกแต่ละช่อง
- `settle_timeout_ms` คือเวลาสูงสุดที่ Controller รอ PEND หลังส่ง pulse ครบ หากหมดเวลาคำสั่งจะ Failed แต่ห้ามนำไป bypass E-Stop หรือ Drive Alarm
- `require_transition=true` ใช้เมื่อยืนยันแล้วว่าระบบ polling มองเห็น PEND เปลี่ยนสถานะทุกคำสั่ง หากยังไม่ยืนยันให้คง `false`

## GOTO XYZ

1. กรอก X/Y/Z หรือ Load current/selected slot
2. ตั้ง speed
3. กด **Validate**
4. ตรวจ **Preview**
5. กด **Arm**
6. ตรวจพื้นที่แล้วกด **Execute**

เมื่อ target, speed หรือ machine state เปลี่ยน ต้อง Validate → Preview → Arm ใหม่ ห้าม reuse token เดิม

## Positions, Slots และ Visualization

- Edit/Save เปลี่ยนเฉพาะข้อมูลตำแหน่ง ไม่ทำให้มอเตอร์เคลื่อนที่
- ตรวจ coordinates ให้อยู่ใน travel range ก่อน Save และก่อน Go To
- Selected slot และ speed ซิงก์ระหว่าง Motion, Slots และ Visualization
- Visualization เป็นเครื่องมือแสดงผล ไม่ใช่ safety authority

## หยุดและกู้ระบบ

- กด **STOP** เพื่อหยุดคำสั่งและ Disarm
- กด E-Stop ทางตู้เมื่อมีอันตราย จากนั้นตรวจว่าหน้าเว็บแสดง DI10 Active
- หลังแก้สาเหตุ: ปลด E-Stop → ตรวจทุก link → Clear Alarm → Enable Motion → Home ใหม่
- ถ้า STM32 ไม่ตอบ: หน้า System Control & Health → Reset USB Link; ปุ่มนี้ไม่ใช่การกด NRST ทางกายภาพ
- หาก IRIV I/O Offline ห้าม Enable Motion ให้ตรวจสาย LAN, ไฟเลี้ยง, Modbus และ address ก่อน

### System Control & Health

- `Disable Motion`: ส่ง Stop/Disarm และล็อกคำสั่งเคลื่อนที่ใหม่ ไม่ตัดสินแทน E-Stop ทางกายภาพ
- `Enable Motion`: ปลด software inhibit เมื่อ DI10, IRIV I/O, NUCLEO และ interlock ผ่าน ไม่ทำให้มอเตอร์เคลื่อน
- `Reset USB Link`: กู้ transport/handshake ของ NUCLEO ไม่ใช่ STM32 hardware NRST และไม่ Home อัตโนมัติ
- `Cut Power`: ตัดคำสั่ง DO0/KM1 สำหรับไฟไดรฟ์ X/Y ตามวงจรที่ติดตั้ง พร้อมคง Motion Disabled
- `Restore Power`: จ่ายกลับเมื่อ E-Stop NC และเงื่อนไขไฟฟ้าผ่าน แต่ไม่ Enable Motion และไม่คืน Homed
- `Reset Drives`: Stop/Disarm → ตัดไฟ X/Y ตามเวลาที่กำหนด → จ่ายกลับ จากนั้นต้องตรวจ DI0/DI1 alarm,
  DI10/KM1 feedback และ Home X/Y ใหม่

ใช้ Reset Drives หลังแก้ต้นเหตุของ HBS860H fault แล้วเท่านั้น การ power cycle อาจไม่ล้าง fault ที่เกิดจาก wiring,
motor feedback, over-current, over-voltage หรือสาเหตุที่ยังคงอยู่ ห้ามกดซ้ำเป็นวงรอบ

## Manual Commissioning

ใช้เฉพาะช่าง commissioning ในพื้นที่ปลอดภัย ต้อง Arm ก่อนและ Arm มีอายุจำกัด Hold-to-run ต้องหยุดเมื่อปล่อยปุ่ม, blur, page hidden หรือ communication loss การ bypass home/position limit ไม่สามารถข้าม E-Stop, physical Stop, driver alarm หรือ communication fault ได้ Raw Jog จะล้าง Homed status และต้องมี audit log

## Demo Slot Sampling

ดูขั้นตอนฉบับเต็มที่ [DEMO_SLOT_SAMPLING_TH.md](DEMO_SLOT_SAMPLING_TH.md) ค่าเริ่มต้นเป็น Motion only
ผู้ใช้ใส่จำนวน Slot Moves และ Dwell; UI คำนวณ Maximum Duration ให้อัตโนมัติจากตำแหน่ง, speed และ dwell
Controller ยังบังคับ bounded sequence และไม่ Resume session เดิมหลัง restart

## ตรวจปัญหาเบื้องต้น

| อาการ | ตรวจสอบ |
|---|---|
| ปุ่มแกนถูก disable | อ่านเหตุผลบนปุ่ม ตรวจ Home ของแกนนั้น, E-Stop, Stop latch, alarm และ connection |
| ปรับ speed แล้ว GOTO Execute ไม่ได้ | ทำ Validate → Preview → Arm ใหม่ |
| ปรับ speed แล้ว Min/Max ไม่ได้ | ตรวจว่าแกนนั้น Home แล้ว; speed ไม่ควรล็อก direct motion |
| Controller Offline | ตรวจ web/controller services และ IPC; อย่าสรุปว่า NUCLEO หรือ IRIV offline ตามไปด้วย |
| NUCLEO Offline | ตรวจ USB path, baud rate, firmware/protocol handshake และ USB reset link |
| IRIV Offline | ตรวจไฟเลี้ยง, LAN, host/port, Unit ID และ Modbus polling |
| Motor หยุดกลางทาง | ตรวจ E-Stop, Stop latch, limit, driver alarm, USB heartbeat และ Event Log |
| อยู่ Max แล้วถอยออกไม่ได้ | ตรวจว่าปุ่มทิศออกจาก sensor ไม่ถูก frontend ปิดผิด, active command จบแล้ว และ stop latch clear |
| Reset Drives แล้ว alarm ไม่หาย | หยุดกดซ้ำ ตรวจรหัส/ไฟ ALM ของ HBS860H, DI0/DI1, encoder/motor wiring และแรงดันจริง |
| หน้าเว็บค้างหรือค่าตำแหน่ง stale | กด Stop ทางกายภาพเมื่อมีความเสี่ยง ตรวจ Controller/IPC ก่อน refresh; ห้ามถือค่าค้างเป็นตำแหน่งจริง |

## หลังจบงาน

1. หยุด motion และรอให้สถานะ Idle
2. Disable Motion หากไม่มีผู้ควบคุมหน้าเครื่อง
3. ตรวจ Event Log หากมี rejected/failed command
4. บันทึกผล commissioning หรือ Demo ก่อนปิดระบบ
