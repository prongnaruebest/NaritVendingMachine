# การตั้งค่าระบบส่งกำลังและระยะเคลื่อนที่

เอกสารสรุปนี้ใช้กับ IRIV V1 รายละเอียดเต็มอยู่ที่
[CONFIGURATION_AND_CALIBRATION_TH.md](CONFIGURATION_AND_CALIBRATION_TH.md)

## ค่าที่บันทึกอยู่ปัจจุบัน

| แกน | ระบบส่งกำลัง | ระยะ | Calibration ที่บันทึก |
|---|---|---:|---:|
| X | MISUMI MTSRL25-1800; ต้องยืนยัน pitch/อัตราทดจริง | 1,700 mm | 64.705882 pulse/mm |
| Y | MISUMI MTSRL25-1800; ต้องยืนยัน pitch/อัตราทดจริง | 1,700 mm | 64.705882 pulse/mm |
| Z | GTD-A001 timing belt 2GT | 160 mm | 9 pulse/mm; pulley teeth ยังไม่ยืนยัน |

ความยาวชิ้นส่วน nominal ไม่ใช่ usable stroke ค่า production ต้องมาจาก physical Min→Max measurement
และ pulse count ที่บันทึกในรอบเดียวกัน

## ขั้นตอนย่อ

1. สำรอง configuration และบันทึก revision
2. ตรวจ safety/communication และใช้ความเร็วต่ำ
3. Home ที่ Min
4. ผู้ควบคุมสั่ง Move to physical Max sensor
5. บันทึก observed pulse และวัดระยะด้วยเครื่องมือภายนอก
6. คำนวณ `pulses_per_mm = observed_pulses / measured_distance_mm`
7. ทำซ้ำสองทิศและหลายระยะ
8. แก้ Machine Setup, Save, Apply & Restart
9. ตรวจ revision, Home ใหม่และทดสอบระยะสั้น

สูตรแนะนำคือ `software travel = measured physical stroke − safety margin` แต่ configuration ปัจจุบัน
เก็บ X/Y `measured_travel_mm=1700`, `margin=10` และ `max_travel_mm=1700` ซึ่งไม่ตรงสูตรนี้
จึงต้องยืนยันเจตนาและวัดซ้ำก่อนเปลี่ยนค่า production

## Z แบบสายพาน

`travel_per_rev_mm = belt_pitch_mm × pulley_teeth ÷ gear_ratio` และ
`pulses_per_mm = pulses_per_rev ÷ travel_per_rev_mm` ปัจจุบัน pulley teeth ยังเป็น null จึงห้าม
สมมติจำนวนฟัน ค่า 9 pulse/mm ต้องถือเป็น empirical value จนมี measurement record

## ความเร็ว

configuration บันทึก commissioned maximum 100 mm/s ทุกแกน แต่ค่านี้ไม่ใช่หลักฐานว่าเครื่องผ่าน
commissioning ที่ความเร็วดังกล่าว ต้องเพิ่มทีละขั้นและตรวจ ALM, PEND, position error และกลไก
ค่า 50,000 pulse/s ของ NUCLEO ไม่ใช่ mechanical safe-speed rating

## ประวัติที่ห้ามนำมาปะปน

บันทึกวันที่ 2026-09-07 เคยใช้ 110,000 pulse กับระยะ 1,600 mm และได้ 68.75 pulse/mm
configuration ปัจจุบันเปลี่ยนเป็น 64.705882 pulse/mm สำหรับ 1,700 mm โดยยังต้องมี measurement record ใหม่
ห้ามใช้บันทึก 1,600 mm เป็นหลักฐานรองรับค่า 1,700 mm
