# ผังต่อ IRIV PiControl, IRIV IO และ NUCLEO-F439ZI ล่าสุด

สถานะ ณ 3 กันยายน 2026: ใช้ Nucleo เป็น motion pulse generator และใช้ IRIV IO
เป็น remote digital I/O เท่านั้น เอกสาร Galil/FX5U รุ่นก่อนหน้าไม่ใช่ wiring ที่กำลัง commission

## เครือข่ายและ USB

| อุปกรณ์ | เส้นทาง | ค่าใช้งาน |
|---|---|---|
| IRIV PiControl | LAN หลัก `eth0` | `192.168.70.80/24` |
| NUCLEO-F439ZI | LAN | `192.168.70.81/24`; ใช้ link/diagnostic |
| NUCLEO-F439ZI | ST-LINK USB VCP | `/dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_0666FF485753667187113533-if02`, 115200 8-N-1; ใช้ control/heartbeat |
| IRIV PiControl | OT LAN `eth1` | `10.0.0.2/24` |
| IRIV IO | Modbus TCP | `10.0.0.10:502`, Unit ID `255` |

USB serial เป็นเส้นทางควบคุมหลัก เพราะตรวจ device identity ได้แน่นอน ส่วน LAN ของ Nucleo
คงไว้สำหรับตรวจ link/diagnostic ห้ามเปิด HTTP LED demo เนื่องจาก LED1 ใช้ขา `PB0` เดียวกับ X-DIR

## IRIV IO digital inputs

| ช่อง | ชื่อใน software | Field signal |
|---|---|---|
| DI0 | `x_head_limit` | X Min |
| DI1 | `x_tail_limit` | X Max |
| DI2 | `y_head_limit` | Y Min |
| DI3 | `y_tail_limit` | Y Max |
| DI4 | `z_head_limit` | Z Min |
| DI5 | `z_tail_limit` | Z Max |
| DI6 | `z_home` | Z Home |
| DI7 | `product_drop_parking` | Product Drop Parking |
| DI8 | `product_drop_sensor` | Product Drop Sensor |
| DI9 | `product_pickup_sensor` | Product Pickup Sensor |
| DI10 | `estop` | E-stop / safety relay feedback |

DI10 ตั้ง `polarity_verified=false` และ `fail_safe=true` ใน config จึงรายงาน E-STOP และ
block motion เสมอจนกว่าจะอ่านค่า raw ขณะ E-stop ปล่อยและกดครบสองสถานะแล้วบันทึก polarity
ห้ามเดาจากค่า DI10 ค่าเดียว

## IRIV IO digital outputs

| ช่อง | หน้าที่ |
|---|---|
| DO0 | Machine Ready |
| DO1 | Moving |
| DO2 | Alarm light/buzzer |
| DO3 | Dispense ผ่าน interposing relay |

เอาต์พุตเป็น SSR auxiliary output ไม่ใช้สร้าง STEP/DIR

## Nucleo STEP/DIR ผ่าน NMOS

| แกน | Pulse | Direction | Driver |
|---|---|---|---|
| X | `PA8 / TIM1_CH1` -> QX-PUL -> `PUL-` | `PB0` -> QX-DIR -> `DIR-` | HBS860H X |
| Y | `PA9 / TIM1_CH2` -> QY-PUL -> `PUL-` | `PB1` -> QY-DIR -> `DIR-` | HBS860H Y |
| Z | `PA5 / TIM2_CH1` -> QZ-PUL -> `PUL-` | `PB2` -> QZ-DIR -> `DIR-` | DM542 Z |

`PUL+`/`DIR+` ต่อ Field +24 V ตาม wiring ที่ผู้ใช้ยืนยัน แต่ต้องตรวจ input rating ของ driver
ตัวจริงก่อน pulse test; Source ของ NMOS และ Nucleo GND ต้องมี signal reference ร่วมกัน

เฟิร์มแวร์ motion candidate เริ่มแบบ disarmed, STEP/DIR LOW, จำกัด 10–1000 Hz และ
ไม่เกิน 10000 steps ต่อคำสั่ง ต้องรับ `ARM SAFE` และ `HEARTBEAT SAFE` ต่อเนื่อง;
ขาด heartbeat เกิน 500 ms จะหยุดและ disarm ไม่มีการเริ่มเคลื่อนเองหลัง boot/reset

## Safety hold points

- E-stop ต้องตัดกำลัง/enable ผ่าน safety relay แบบ hardwired ไม่พึ่ง Pi, Modbus, USB หรือ firmware
- Wiring ปัจจุบันระบุ KM1 ตัด 60 V ของ X/Y แต่ไฟ 24 V ของ Z/DM542 ยังไม่ผ่าน KM1:
  จุดนี้เป็น safety gap และยังไม่พร้อม production
- ก่อน flash motion firmware ต้องยืนยัน DI10 polarity, ตรวจว่า E-stop หยุด X/Y/Z จริง และ
  scope STEP/DIR โดยถอด driver หรือใช้ dummy load ก่อน
- ห้ามสั่ง HOME/JOG/MOVE ระหว่างการตรวจ communication และ pin mapping

รายละเอียดขา connector และวงจร NMOS ดู
[STM32_NMOS_CURRENT_WIRING_TH.md](STM32_NMOS_CURRENT_WIRING_TH.md)
