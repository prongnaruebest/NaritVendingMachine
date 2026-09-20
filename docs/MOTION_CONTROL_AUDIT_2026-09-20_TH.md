# รายงานตรวจงาน Motion Control ต่อจาก Gemini — 2026-09-20

## ขอบเขต

ตรวจ source, tests และเอกสารของ Controller กับ NUCLEO-G491RE โดยไม่ deploy,
ไม่ flash และไม่ออกคำสั่ง Home/Jog/GOTO หรือ motion จริง

## ข้อค้นพบที่ยืนยันได้

1. Dynamic X/Y S-curve, constraint envelope และ Virtual Kp ถูกเชื่อมเข้ากับ
   protocol v4 แล้ว ไม่ได้เป็น candidate ที่ unreachable ตามเอกสารเก่าบางส่วน
2. Control tick เคยถูกขับจาก `NucleoMotion_Poll()` ทำให้ cadence ขึ้นกับ main
   loop และเมื่อช้าเกิน 1 ms จะชดเชยได้เพียงหนึ่ง tick ซึ่งไม่ deterministic
3. Legacy MOVE และ dynamic X/Y ใช้ TIM1 ร่วมกัน แต่ก่อน audit ไม่มี guard ที่
   firmware ป้องกัน `DYN_START` ขณะ legacy X/Y ยังทำงาน
4. Controller เคยใช้ความเร็ว scalar สูงสุดของแผนไป configure ทั้ง X/Y ทำให้แกน
   ระยะสั้นอาจจบก่อนและไม่รักษา coordinated trajectory
5. ความผิดพลาดระหว่าง `DYN_CONFIG` เคยถูกลดเหลือ warning แล้วขั้นตอน motion
   สามารถดำเนินต่อได้ ซึ่งไม่เหมาะกับ configuration revision boundary
6. Capability gate เดิมไม่ได้กำหนดให้ต้องมี `dynamic_motion`
7. เอกสาร source-of-truth มีข้อความ protocol v3/candidate disabled ปะปนกับ
   implementation protocol v4 และชื่อ artifact ปัจจุบันยังอยู่ใต้ `artifacts/v3`
8. ข้อความ benchmark 210 mm/s ไม่มี raw CSV/log หรือ external measurement ใน
   repository จึงใช้เป็นหลักฐาน mechanical accuracy หรือไม่ตกสเต็ปไม่ได้

## การแก้ไขในรอบนี้

- คืน planner tick ไปที่ TIM6 interrupt 1 kHz และ fail closed ถ้า timer init/start
  ไม่สำเร็จ
- ปฏิเสธ dynamic start เมื่อ legacy X/Y ยังครอบครอง TIM1
- บังคับ capability handshake ให้มี `dynamic_motion`
- ส่ง planned speed แยก X/Y เข้า dynamic configuration
- ยก configuration failure เป็น `NucleoError` ก่อน stage target
- คง dynamic configuration หลัง move สำเร็จ เพื่อลด disarm/configure ที่ซ้ำ
- แก้ compatibility ของ Slot positioning เมื่อ integration เก่าไม่มี config
- เพิ่ม regression tests และแก้เอกสารไม่ให้ตีความ configuration เป็นผลทดสอบจริง

## สิ่งที่ยังต้องทำก่อนใช้ motion จริง

1. สร้าง artifact protocol v4 ใน path/name ใหม่พร้อม SHA-256 และ manifest ที่
   ระบุ commit, build flags และ board target; ห้ามนำ artifact v3 เดิมไป flash
2. สำรอง Controller/configuration บน Pi แล้วตรวจ health และ USB handshake แบบ
   read-only ว่ารายงาน G491RE, protocol v4 และ capability ครบ
3. Flash ผ่าน commissioning gate และตรวจ E-Stop/Stop/watchdog โดยไม่เคลื่อนที่
4. ทดสอบ X และ Y ทีละแกนด้วยความเร็วต่ำ พร้อม ALM/PEND/limit และ external
   distance measurement ก่อน Home All หรือ coordinated move
5. เก็บ raw commissioning log แยกค่าที่สั่ง, emitted pulses, เวลา, ระยะวัดจริง,
   ALM/PEND และผลผู้ปฏิบัติงาน

## ความเสี่ยงคงเหลือ

- ระบบเป็น open-loop estimate จาก emitted STEP edge ไม่ใช่ measured position
- Controller ยอมรับ protocol 3 หรือ 4 เพื่อ compatibility; capability handshake
  จึงเป็น gate ที่ห้ามตัดออก
- linker เตือน ELF มี RWX LOAD segment แม้ build สำเร็จ ควรปรับ linker script
  ก่อน release artifact ขั้นสุดท้าย
- root package และ `NaritVendingV1` ยังมี source ซ้ำ ต้องรักษาให้ตรงกันจนกว่าจะ
  ย้าย consumer ทั้งหมดและลบ compatibility copy อย่างมี characterization test
- เอกสาร handoff เก่าบางไฟล์ยังกล่าวถึง F439/protocol v3 ต้องถือสอง source-of-
  truth ที่อัปเดตในรอบนี้และรายงานนี้เป็นข้อมูลล่าสุด
