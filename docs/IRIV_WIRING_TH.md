# ผังการต่อ IRIV PiControl CM4 และ IRIV IO Controller

เอกสารนี้กำหนดผังสายสำหรับเครื่อง NARIT Vending ชุดใหม่ ตรวจสอบกับเครื่องจริงเมื่อ
13 สิงหาคม 2026:

- IRIV PiControl CM4: `eth0=192.168.70.80/24`, `eth1=10.0.0.2/24`
- IRIV IO Controller: Modbus TCP `10.0.0.10:502`, Unit ID `255`

## เครือข่าย

ต่อพอร์ต Ethernet OT ของ IRIV PiControl (`eth1`) เข้ากับ IRIV IO Controller โดยตรง
หรือผ่าน industrial switch ในวง `10.0.0.0/24` ห้ามตั้งอุปกรณ์อื่นซ้ำกับ `.2` หรือ `.10`

## IRIV IO digital inputs

อินพุตเป็น active-high การต่อแบบ dry contact ให้ใช้แหล่งจ่าย isolated ที่ขั้วของ IRIV IO
ตามสัญลักษณ์ S/S และ DCOM บนตัวเครื่อง ห้ามนำ 24 V เข้าขา GPIO ของ Raspberry Pi โดยตรง

| ช่อง | หน้าที่ | สถานะปกติที่แนะนำ |
|---|---|---|
| DI0 | E-Stop feedback จาก safety relay auxiliary contact | ON เมื่อวงจรปลอดภัย |
| DI1 | X home/head limit | OFF |
| DI2 | X tail limit | OFF |
| DI3 | Y home/head limit | OFF |
| DI4 | Y tail limit | OFF |
| DI5 | Z home/head limit | OFF |
| DI6 | Z tail limit | OFF |
| DI7 | Alarm feedback จาก driver X | OFF |
| DI8 | Alarm feedback จาก driver Y | OFF |
| DI9 | Alarm feedback จาก driver Z | OFF |
| DI10 | Door/interlock feedback | ON เมื่อประตูปิดและปลอดภัย |

DI1/DI3/DI5 รองรับ counter แต่ต้องปิด counter mode เพื่อใช้เป็น limit input ปกติ

## IRIV IO digital outputs

เอาต์พุตเป็น dry-contact solid-state relay, active-high, สูงสุด 50 V 500 mA ใช้สำหรับ
อุปกรณ์ auxiliary เท่านั้น ห้ามใช้สร้าง STEP/DIR pulse ของมอเตอร์

| ช่อง | หน้าที่ |
|---|---|
| DO0 | ไฟสถานะ Machine Ready สีเขียว |
| DO1 | ไฟสถานะ Moving สีเหลือง |
| DO2 | Alarm beacon/buzzer ผ่านวงจร 24 V |
| DO3 | Dispense actuator ผ่าน interposing relay และ fuse |

## วงจร E-Stop และมอเตอร์

E-Stop ต้องต่อแบบ hardwired ผ่าน safety relay เพื่อปลด ENABLE/contactor ของ driver X/Y/Z
โดยไม่พึ่ง Raspberry Pi, Ethernet, Modbus หรือซอฟต์แวร์ DI0 ใช้ตรวจ feedback เท่านั้น

IRIV PiControl และ IRIV IO แต่ละตัวมีเพียง 4 isolated DO และเป็น SSR output จึงไม่มี
STEP/DIR/ENABLE ครบ 9 สัญญาณสำหรับสามแกน และไม่เหมาะกับ pulse 2,000 Hz ให้ต่อ
STEP/DIR ของ X/Y/Z ผ่าน motion controller ที่มี hardware-timed pulse output โดยเฉพาะ
แล้วให้ IRIV PiControl ส่งคำสั่งระดับตำแหน่งไปยัง motion controller

## สถานะการติดตั้งซอฟต์แวร์

แอปติดตั้งที่ `/home/admin/NaritVending` และเปิดที่ `http://iriv.local/` ปัจจุบันกำหนด
`GPIOZERO_PIN_FACTORY=mock` ใน `/etc/narit-vending.env` เพื่อป้องกันการขับมอเตอร์จาก
pin map ของ Raspberry Pi 4 เดิม ห้ามถอด safe-mode จนกว่าจะติดตั้ง motion controller,
ทำ I/O backend สำหรับ IRIV IO, ตรวจ polarity ทีละช่อง และผ่าน E-Stop acceptance test

