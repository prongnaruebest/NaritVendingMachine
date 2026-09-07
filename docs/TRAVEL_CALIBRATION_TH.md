# การตั้งค่าระบบส่งกำลังและระยะเคลื่อนที่

## ค่าตั้งต้นของเครื่อง

| แกน | ระบบส่งกำลัง | ระยะอ้างอิง | ค่าคำนวณเริ่มต้น |
| --- | --- | ---: | --- |
| X | MISUMI MTSRL25-1800, pitch 5 mm/rev | 1,800 mm nominal | 200 step/rev × 8 microstep ÷ 5 = 320 pulse/mm |
| Y | MISUMI MTSRL25-1800, pitch 5 mm/rev | 1,800 mm nominal | 200 step/rev × 8 microstep ÷ 5 = 320 pulse/mm |
| Z | GTD-A001, timing belt 2GT | 180 mm nominal | คงค่า 200 pulse/mm จนกว่าจะยืนยันจำนวนฟัน pulley และอัตราทด |

ความยาวสกรู 1,800 mm ไม่ใช่หลักฐานว่า usable stroke เท่ากับ 1,800 mm เพราะตำแหน่งน็อต ชุดรองรับปลายเพลา และ limit sensor ทำให้ระยะจริงสั้นลง ค่า `max_travel_mm` สุดท้ายต้องมาจากการวัดกับเครื่องจริง

## ขั้นตอนวัดระยะ

1. เคลียร์ alarm ของไดรฟ์ตามคู่มือผู้ผลิตและตรวจว่าพื้นที่เคลื่อนที่ปลอดภัย
2. ใช้ความเร็ว commissioning ต่ำ ห้ามเริ่มจากความเร็วสูงสุด
3. Home แกนที่ต้องการวัดให้ตำแหน่ง Min เป็น 0
4. ผู้ควบคุมสั่ง Move to Max และเฝ้าปุ่ม Stop/E-Stop ตลอดเวลา ระบบต้องหยุดเมื่อ Max sensor ทำงาน
5. วัดระยะ Min ถึง Max จริงด้วยอุปกรณ์วัดภายนอก อย่าใช้ค่าหน้าเว็บเพียงอย่างเดียวก่อนสอบเทียบ pulse/mm
6. เปิด `Machine Setup > Travel & Drive Setup`
7. กรอก `Measured Min → Max` และ `Safety Margin`
8. กด `USE MEASURED − MARGIN` จากนั้นตรวจ `Maximum Travel`
9. กด `SAVE TO PI` และ `APPLY & RESTART` การบันทึกค่าจะไม่สั่งมอเตอร์เคลื่อนที่
10. Home ใหม่และทดสอบด้วยความเร็วต่ำก่อนใช้งานจริง

สูตรที่ใช้คือ `software travel = measured physical stroke − safety margin`

## การสอบเทียบ Z แบบสายพาน

หน้าอ้างอิง GTD-A001 ระบุสายพาน 2GT แต่ไม่ระบุจำนวนฟัน pulley ของชุดที่ติดตั้ง จึงห้ามสมมติค่า 20 ฟันโดยไม่มีการตรวจชิ้นส่วนจริง

- `travel_per_rev_mm = belt_pitch_mm × pulley_teeth ÷ gear_ratio`
- `pulses_per_mm = motor_steps_per_rev × microsteps ÷ travel_per_rev_mm`

ตัวอย่างเท่านั้น: pulley 20 ฟัน, pitch 2 mm, ไม่มีอัตราทด จะเคลื่อนที่ 40 mm/rev แต่ต้องตรวจ pulley และอัตราทดจริงก่อนบันทึก

## ข้อจำกัดความเร็วชั่วคราว

หลังพบ drive alarm ระบบตั้ง commissioned speed ชั่วคราวเป็น X/Y 5 mm/s และ Z 2 mm/s ค่านี้ไม่ใช่ความเร็วสูงสุดของกลไก แต่เป็นขอบเขตเริ่มต้นสำหรับ commissioning ใหม่ ค่าเพดาน 50,000 pulse/s ของ NUCLEO ไม่ใช่หลักฐานว่ากลไกสามารถทำงานที่ความเร็วนั้นได้อย่างปลอดภัย
