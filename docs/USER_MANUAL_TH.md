# คู่มือเว็บควบคุม NaritVendingMachine

## ก่อนเริ่มใช้งาน

1. ตรวจพื้นที่เคลื่อนที่ X/Y/Z และนำสิ่งกีดขวางออก
2. ตรวจว่า E-Stop ทางกายภาพใช้งานได้และ DI10 แสดง `HIGH / CLEAR`
3. ตรวจหน้า System Control & Health: Controller, IRIV I/O และ NUCLEO ต้อง Online
4. ปลด E-Stop, Clear Alarm แล้ว Enable Motion ตามลำดับ
5. Home แกนที่ต้องใช้งาน ก่อนสั่ง Jog, GOTO หรือ Demo

> X/Y มีการตัดไฟ 60 V ทางกายภาพ ส่วน Z ในปัจจุบันหยุด STEP pulse ด้วยซอฟต์แวร์เท่านั้น จึงต้องติดตั้ง safety relay/contactor สำหรับ Z ก่อนถือว่าเป็น E-Stop ที่สมบูรณ์

## หน้าใช้งาน

- **Overview:** สถานะเครื่อง การเชื่อมต่อ Alarm ตำแหน่ง และคำสั่งปัจจุบัน
- **Motion Control:** Home, Jog, Min/Max และ GOTO XYZ; เปลี่ยนค่าแล้วต้อง Validate/Arm ใหม่
- **Positions & Slots:** แก้และบันทึกพิกัด Slot; Save ไม่ทำให้เครื่องเคลื่อนที่
- **Machine Visualization:** ภาพตำแหน่งจริง/เป้าหมาย เลือก Slot และ Demo Slot Sampling
- **Diagnostics & I/O:** DI/DO, Alarm, Event และรายละเอียด protocol
- **Machine Setup:** Motor, Homing, I/O, USB และ Manual Commissioning
- **System Control & Health:** เปิด/ปิดสิทธิ์ Motion และกู้ USB handshake
- **MQTT Monitor:** สถานะ broker และข้อความ โดยไม่เป็นเจ้าของ Motion

## หยุดและกู้ระบบ

- กด **STOP** เพื่อหยุดคำสั่งและ Disarm
- กด E-Stop ทางตู้เมื่อมีอันตราย จากนั้นตรวจว่าหน้าเว็บแสดง DI10 Active
- หลังแก้สาเหตุ: ปลด E-Stop → ตรวจทุก link → Clear Alarm → Enable Motion → Home ใหม่
- ถ้า STM32 ไม่ตอบ: หน้า System Control & Health → Reset USB Link; ปุ่มนี้ไม่ใช่การกด NRST ทางกายภาพ
- หาก IRIV I/O Offline ห้าม Enable Motion ให้ตรวจสาย LAN, ไฟเลี้ยง, Modbus และ address ก่อน

## Manual Commissioning

ใช้เฉพาะพื้นที่ปลอดภัย ต้อง Arm และกดค้างเพื่อวิ่ง การ bypass ไม่สามารถข้าม E-Stop, driver alarm หรือ communication fault ได้ Raw Jog จะล้าง Homed status

## Demo Slot Sampling

ดูขั้นตอนฉบับเต็มที่ [DEMO_SLOT_SAMPLING_TH.md](DEMO_SLOT_SAMPLING_TH.md) ค่าเริ่มต้นเป็น Motion only และต้องมีขอบเขตจำนวนรอบหรือเวลาเสมอ

