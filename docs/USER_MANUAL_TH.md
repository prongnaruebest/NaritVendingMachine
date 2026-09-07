# คู่มือเว็บควบคุม NaritVendingMachine

คู่มือนี้ใช้กับ HMI ปัจจุบันที่ `http://192.168.70.80/` สำหรับควบคุมเครื่องจริงผ่าน Controller และ NUCLEO USB ห้ามใช้หน้าเว็บแทนการตรวจความปลอดภัยทางกายภาพ

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
- **Diagnostics & I/O:** DI/DO, Alarm, Event และรายละเอียด protocol
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

## Move to Min/Max

1. Home แกนที่ต้องการ
2. ตั้ง speed ของแกน
3. ตรวจ Current position, travel range และ Min/Max sensors
4. กด Min หรือ Max และยืนยันว่าพื้นที่ปลอดภัย

คำสั่งระยะยาวไม่ต้องแบ่งระยะเอง Controller จะแบ่งจำนวน pulse ตาม capability `max_move_steps` ของ NUCLEO โดยอัตโนมัติ ปัจจุบันใช้ 10,000 pulses ต่อ USB frame และตรวจ Stop/E-Stop/limit ทุก segment

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

## Manual Commissioning

ใช้เฉพาะช่าง commissioning ในพื้นที่ปลอดภัย ต้อง Arm ก่อนและ Arm มีอายุจำกัด Hold-to-run ต้องหยุดเมื่อปล่อยปุ่ม, blur, page hidden หรือ communication loss การ bypass home/position limit ไม่สามารถข้าม E-Stop, physical Stop, driver alarm หรือ communication fault ได้ Raw Jog จะล้าง Homed status และต้องมี audit log

## Demo Slot Sampling

ดูขั้นตอนฉบับเต็มที่ [DEMO_SLOT_SAMPLING_TH.md](DEMO_SLOT_SAMPLING_TH.md) ค่าเริ่มต้นเป็น Motion only และต้องมีขอบเขตจำนวนรอบหรือเวลาเสมอ

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

## หลังจบงาน

1. หยุด motion และรอให้สถานะ Idle
2. Disable Motion หากไม่มีผู้ควบคุมหน้าเครื่อง
3. ตรวจ Event Log หากมี rejected/failed command
4. บันทึกผล commissioning หรือ Demo ก่อนปิดระบบ
