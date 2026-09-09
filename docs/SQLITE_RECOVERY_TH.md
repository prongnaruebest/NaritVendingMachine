# การสำรองและกู้คืน SQLite อย่างปลอดภัย

เอกสารนี้ใช้กับฐานข้อมูล SQLite ที่ Controller เป็นเจ้าของ เช่น ประวัติ Demo Slot Sampling ห้ามคัดลอกไฟล์ฐานข้อมูลที่กำลังเปิดใช้งานด้วยคำสั่ง copy ธรรมดา เพราะอาจได้ข้อมูลที่ไม่สอดคล้องกัน

## หลักการ

- การสำรองขณะระบบทำงานต้องใช้ SQLite online backup API
- ตรวจ `PRAGMA integrity_check` ทั้งฐานข้อมูลต้นทางและไฟล์สำรอง
- การกู้คืนต้องตรวจไฟล์สำรองให้ผ่านก่อนแก้ฐานข้อมูลจริง
- เขียนผลกู้คืนลงไฟล์ชั่วคราว แล้วแทนที่ฐานข้อมูลจริงแบบ atomic
- ควรสร้าง safety backup ของฐานข้อมูลเดิมก่อนกู้คืนเสมอ
- หยุด Controller ก่อนทำ offline restore เพื่อป้องกัน process เดิมถือ connection หรือเขียนข้อมูลพร้อมกัน
- การสำรองหรือกู้คืนฐานข้อมูลต้องไม่ส่งคำสั่ง Motion

## ส่วนประกอบในโปรแกรม

`narit_vending.persistence.SQLiteMaintenance` มีคำสั่งหลักดังนี้:

- `integrity_check(path)` ตรวจว่าฐานข้อมูลอ่านได้และโครงสร้างสมบูรณ์
- `backup_to(destination)` สร้าง consistent backup โดยไม่แก้ฐานข้อมูลต้นทาง
- `restore_from(source, safety_backup=...)` ตรวจ source, สำรองฐานเดิม และแทนที่ด้วยไฟล์ที่ผ่านการตรวจแล้ว

ฟังก์ชันจะปฏิเสธการใช้ไฟล์เดียวกันเป็นต้นทางและปลายทาง และจะไม่แทนที่ฐานข้อมูลจริงหากไฟล์สำรองเสียหาย

## ขั้นตอนกู้คืนบนเครื่องจริง

1. Disable Motion และยืนยันว่าไม่มีคำสั่งกำลังทำงาน
2. หยุด Controller service
3. สำรองฐานข้อมูลปัจจุบันไปยังชื่อไฟล์ที่มี timestamp
4. ตรวจ integrity ของไฟล์ที่จะนำมากู้คืน
5. กู้คืนพร้อมระบุ safety backup
6. เริ่ม Controller service
7. ตรวจ health, schema version และรายการล่าสุดแบบ read-only
8. หากตรวจไม่ผ่าน ให้หยุด service และย้อนกลับจาก safety backup

ห้าม Home, Jog, GOTO, Dispense หรือ Demo Sampling เพื่อทดสอบขั้นตอน backup/restore โดยอัตโนมัติ

## ขอบเขตปัจจุบัน

Demo repository ใช้ SQLite ใน runtime แล้ว ส่วน Audit และ Idempotency มีทั้ง memory และ SQLite repository แต่ Controller runtime ยังใช้ค่าเริ่มต้นแบบ memory จนกว่าจะผ่าน phase gate สำหรับเปิด persistence และกำหนดตำแหน่งฐานข้อมูลจริงอย่างชัดเจน
