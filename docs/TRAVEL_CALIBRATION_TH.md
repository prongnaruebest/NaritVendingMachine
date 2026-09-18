# การตั้งค่าระบบส่งกำลังและระยะเคลื่อนที่

เอกสารสรุปนี้ใช้กับ IRIV V1 รายละเอียดเต็มอยู่ที่
[CONFIGURATION_AND_CALIBRATION_TH.md](CONFIGURATION_AND_CALIBRATION_TH.md)

## ค่าที่บันทึกจากการวัดจริง (Limit Seek Calibration 2026-09-18)

| แกน | ระบบส่งกำลัง | Physical Stroke (Min→Max Sensor) | Pulses บันทึกจริง | Steps/mm | Safety Margin | Software Max Travel |
|---|---|---:|---:|---:|---:|---:|
| X | MISUMI MTSRL25-1800 (Lead Screw) | 1,794.721 mm (~1,794.7 mm) | 116,129 pulses | 64.705882 | 14.7 mm | 1,780.0 mm |
| Y | MISUMI MTSRL25-1800 (Lead Screw) | 1,756.656 mm (~1,756.7 mm) | 113,666 pulses | 64.705882 | 56.7 mm | 1,700.0 mm |
| Z | GTD-A001 timing belt 2GT | 160.0 mm | 1,440 pulses | 9.0 | 3.0 mm | 160.0 mm |

สูตร `software travel = measured physical stroke − safety margin` สอดคล้องกันอย่างสมบูรณ์:
- แกน X: `1,794.7 mm − 14.7 mm = 1,780.0 mm` (พิกัด Slot X สูงสุดอยู่ที่ 1,270.0 mm มีระยะปลอดภัย > 500 mm)
- แกน Y: `1,756.7 mm − 56.7 mm = 1,700.0 mm` (พิกัด Slot Y สูงสุดอยู่ที่ 1,620.0 mm มีระยะปลอดภัย 80.0 mm)
- S-curve Kinematics (Commissioned): Max Speed = 60.0 mm/s, Accel/Decel = 120.0 mm/s², Max Jerk = 250.0 mm/s³, Start Speed = 5.0 mm/s, End Speed = 2.0 mm/s, Control Period = 1000 µs

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
