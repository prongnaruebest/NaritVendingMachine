# คู่มือ Demo Slot Sampling

Demo เป็น sequence ที่ Controller ควบคุม Browser ใช้ตั้งค่าและแสดงผลเท่านั้น การปิดหรือ Refresh หน้าไม่ย้าย authority ไปยัง Browser

## ขั้นตอนใช้งาน

1. ตรวจพื้นที่และความพร้อมจาก System Control & Health
2. Home X/Y/Z และเลือก Slot ใน Visualization
3. เลือก Sampling Mode: Sequential, Random, Balanced หรือ Selected Slot Only
4. ใส่ Number of Slot Moves; หน้าเว็บคำนวณ Maximum Duration อัตโนมัติจากระยะ, speed และ Dwell
5. ตั้ง Dwell และความเร็ว X/Y/Z จาก shared speed control แล้วตรวจเวลาอัตโนมัติอีกครั้ง
6. กด `1 CONFIGURE` → `2 VALIDATE` → `3 ARM`
7. ตรวจพื้นที่อีกครั้ง แล้วกด `4 START` และยืนยัน
8. `PAUSE AFTER SLOT` จะหยุดหลัง Slot ปัจจุบัน; `STOP DEMO` หยุด Motion และ Disarm ทันที
9. ตรวจ counters และใช้ `EXPORT CSV` เก็บผล

Demo เป็น Motion only และไม่สั่ง Dispense ผลแต่ละ sample และ session ถูกเก็บใน `demo_results.sqlite3` หลัง Controller restart session เดิมจะไม่ Resume อัตโนมัติ

Maximum Duration เป็น watchdog ที่ Controller ใช้จำกัด session ไม่ใช่ช่องเพิ่มความเร็ว และไม่ควรแก้ด้วยมือ
เมื่อเปลี่ยนจำนวน moves, dwell, slot candidates หรือ speed หน้าเว็บต้องคำนวณใหม่และ invalidate Configure/Validate/Arm เดิม

## Counters

- Requested: จำนวนที่คาดจาก cycles × slots
- Attempted/Passed/Failed/Skipped/Stopped
- Success Rate: Passed ÷ Attempted
- Current/Next Slot, Cycle, Session ID และ Last Result

หากเกิด E-Stop, IRIV I/O loss, NUCLEO timeout, driver alarm หรือ limit fault ให้ตรวจ Alarm และทำ recovery ก่อน Home ใหม่
