# NARIT Vending - ผังต่อ STM32 + NMOS ที่ใช้งานปัจจุบัน

เอกสารนี้แยกเฉพาะทางเดินสัญญาณ `PULSE/DIRECTION` จาก
`NUCLEO-F439ZI` ผ่าน NMOS แบบ low-side/open-drain ไปยังไดรเวอร์มอเตอร์ X/Y/Z
โดยไม่รวม FX5U, Galil หรือ AS218TX-A

> **สถานะเอกสาร: AS-CONNECTED แบบ provisional**
>
> ไม่พบไฟล์ต้นฉบับชื่อ `NARIT_Vending_Dual_Wiring_PLC_STM32_NMOS` ใน workspace
> ตารางขา STM32 ด้านล่างจึงยืนยันจาก source code ปัจจุบันและคู่มือ ST UM1974
> ส่วนรุ่น NMOS, ค่า resistor, แรงดัน `V-PULSE` และ terminal ฝั่ง driver ต้องตรวจจาก
> อุปกรณ์/สายจริงก่อนเปลี่ยนสถานะเป็น VERIFIED AS-BUILT

> ตัดไฟและทำ Lockout/Tagout ก่อนวัด continuity หรือแก้สาย ห้ามใช้ STM32, NMOS,
> USB หรือ software เป็นวงจร E-Stop

## 1. ขอบเขตและสถานะระบบ

```mermaid
flowchart LR
    PI["IRIV PiControl"] <-->|"USB virtual COM\n115200 8-N-1"| ST["NUCLEO-F439ZI"]
    ST -->|"3.3 V PUL/DIR"| Q["6 x NMOS\nlow-side/open-drain"]
    V["V-PULSE\n5 V หรือ 24 V หลังยืนยัน"] --> DX["HBS860H X"]
    V --> DY["Driver Y - ต้องยืนยันรุ่น"]
    V --> DZ["DM542 Z"]
    Q -->|"PUL-/DIR-"| DX
    Q -->|"PUL-/DIR-"| DY
    Q -->|"PUL-/DIR-"| DZ
    SAFE["E-Stop + SR1/KM1"] -->|"ตัด 60 V ตาม wiring ล่าสุด"| DX
    SAFE --> DY
    GAP["DM542 Z 24 V\nยังไม่ผ่าน KM1"] -. "safety gap" .-> DZ
```

- STM32 สร้าง pulse ด้วย timer output compare ไม่ใช่ Raspberry Pi GPIO
- NMOS แต่ละตัวทำหน้าที่ sink กระแสของ optocoupler input ฝั่ง driver
- ใช้ NMOS แยกหนึ่งตัวต่อหนึ่งสัญญาณ รวม 6 ตัวสำหรับ `PUL/DIR` สามแกน
- `ENA`, limit, alarm และ E-Stop **ไม่ได้ต่อเข้า Nucleo โดยตรงในโมดูล motion ปัจจุบัน**
- วงจร safety ต้อง hardwired แยกต่างหาก
- `PB0` เป็นทั้งตำแหน่ง LED1 บน Nucleo และ `X_DIR` ใน wiring นี้ เฟิร์มแวร์ motion
  จึงปิดการ init/toggle LED และปิด HTTP LED demo เพื่อไม่ให้ทิศ X ถูกเปลี่ยนโดยไม่ตั้งใจ

## 2. STM32 pin map ที่ยืนยันจาก source code

| แกน | สัญญาณ | STM32 pin | Nucleo connector | Timer/function | NMOS channel |
|---|---|---|---|---|---|
| X | `X_PUL_MCU` | `PA8` | `CN12 pin 23` | `TIM1_CH1` | Q1 |
| X | `X_DIR_MCU` | `PB0` | `CN10 pin 31` / `D33` | GPIO output | Q2 |
| Y | `Y_PUL_MCU` | `PA9` | `CN12 pin 21` | `TIM1_CH2` | Q3 |
| Y | `Y_DIR_MCU` | `PB1` | `CN10 pin 7` / `A6` | GPIO output | Q4 |
| Z | `Z_PUL_MCU` | `PA5` | `CN12 pin 11` / `CN7 pin 10` / `D13` | `TIM2_CH1` | Q5 |
| Z | `Z_DIR_MCU` | `PB2` | `CN10 pin 15` / `D27` | GPIO output | Q6 |
| Common | `MCU_GND` | GND | เช่น `CN10 pin 5/17/27` | signal reference | Q1-Q6 Source |

แหล่งยืนยัน pin function คือ
[`NaritVendingV1/stm32/Src/nucleo_motion.c`](../NaritVendingV1/stm32/Src/nucleo_motion.c)
และ ST UM1974 ตาราง NUCLEO-F429ZI/F439ZI pin assignments

> ใช้ชื่อ `PA8/PB0/...` และหมายเลข `CNx pin` เป็นหลัก อย่าอ้างเฉพาะชื่อ Arduino
> `D5/D6/A6` เพราะอ่านสลับด้าน connector ได้ง่าย ให้ตรวจ pin 1 marker บนบอร์ดก่อนเสียบสาย

## 3. วงจร NMOS ต่อหนึ่งสัญญาณ

ใช้ topology เดียวกันกับ Q1-Q6:

```text
STM32 GPIO 3.3 V ---- Rg ---- Gate  Qn
                              |
                            Rpd
                              |
MCU GND -------------------- Source Qn -------- 0V-SIGNAL
                              |
                            Drain
                              |
Driver PUL- หรือ DIR- --------+

V-PULSE ---------------------- Driver PUL+ หรือ DIR+
```

| อุปกรณ์ | หน้าที่ | ค่าที่ต้องยืนยันจากของจริง |
|---|---|---|
| Q1-Q6 | N-channel MOSFET, low-side switch | ต้องเป็น logic-level ที่ขับด้วย 3.3 V ได้ และ `VDS` สูงกว่า `V-PULSE` พร้อม margin |
| `Rg` | จำกัดกระแสชาร์จ gate/ลด ringing | บันทึกค่าที่ติดตั้งจริง; ค่าออกแบบทั่วไป 100-330 ohm แต่ห้ามถือเป็นค่า as-built |
| `Rpd` | ดึง gate ลงเมื่อ MCU reset/สายหลุด | บันทึกค่าที่ติดตั้งจริง; ค่าออกแบบทั่วไป 47-100 kohm แต่ห้ามถือเป็นค่า as-built |
| `V-PULSE` | แหล่งจ่าย optocoupler input ของ driver | ใช้ 5 V หรือ 24 V ตามป้าย/selector/คู่มือของ driver lot จริงเท่านั้น |

ข้อกำหนด:

- Source ของ Q1-Q6, `0V-SIGNAL` และ GND ของ STM32 ต้องอ้างอิงร่วมกัน
- ห้ามป้อน `V-PULSE` เข้า GPIO ของ STM32 ไม่ว่าโดยตรงหรือผ่าน pull-up
- ต้องวัด `VGS`, drain voltage และ input current ของ driver ขณะ ON/OFF ก่อนต่อมอเตอร์
- ถ้าใช้ breakout NMOS module ให้ตรวจว่ามี optocoupler, LED, resistor หรือ logic inversion
  ภายในหรือไม่ เพราะอาจทำให้ pulse width/polarity ต่างจากวงจรข้างต้น
- STM32 HIGH ทำให้ NMOS ON และกระแสไหลผ่าน optocoupler ของ driver แม้แรงดันที่ `PUL-`/`DIR-`
  จะถูกดึงลงต่ำ ดังนั้นให้ตรวจ polarity จากกระแสที่ input ไม่ใช่ดูชื่อ active-high อย่างเดียว

## 4. ตารางต่อสาย STM32 -> NMOS -> driver

หมายเลข `S3xx` ด้านล่างเป็น local signal tag ของเอกสารนี้ ไม่ใช่การยืนยันหมายเลข wire
จากไฟล์ Dual Wiring ที่หาไม่พบ

| Tag | From | Via | To | หน้าที่ |
|---|---|---|---|---|
| S300 | STM32 `PA8`, CN12-23 | Rg -> Q1 Gate | - | X pulse command |
| S301 | Q1 Drain | - | TB-X/Driver X `PUL-` | X pulse sink |
| S302 | STM32 `PB0`, CN10-31 | Rg -> Q2 Gate | - | X direction command |
| S303 | Q2 Drain | - | TB-X/Driver X `DIR-` | X direction sink |
| S310 | STM32 `PA9`, CN12-21 | Rg -> Q3 Gate | - | Y pulse command |
| S311 | Q3 Drain | - | TB-Y/Driver Y `PUL-` | Y pulse sink |
| S312 | STM32 `PB1`, CN10-7 | Rg -> Q4 Gate | - | Y direction command |
| S313 | Q4 Drain | - | TB-Y/Driver Y `DIR-` | Y direction sink |
| S320 | STM32 `PA5`, CN12-11 / CN7-10 | Rg -> Q5 Gate | - | Z pulse command |
| S321 | Q5 Drain | - | TB-Z/DM542 `PUL-` | Z pulse sink |
| S322 | STM32 `PB2`, CN10-15 | Rg -> Q6 Gate | - | Z direction command |
| S323 | Q6 Drain | - | TB-Z/DM542 `DIR-` | Z direction sink |
| S330 | `V-PULSE` ผ่าน fuse | terminal distribution | X/Y/Z `PUL+` และ `DIR+` | common-anode signal supply |
| S331 | STM32 GND | Q1-Q6 Source | `0V-SIGNAL` | signal reference |

ต่อ PUL และ DIR เป็น shielded twisted pair แยกจากสายมอเตอร์และสาย AC ต่อ shield ที่
cabinet PE ฝั่งตู้เพียงด้านเดียว เว้นแต่คู่มือ driver lot จริงกำหนดต่างออกไป

## 5. Driver assignment ปัจจุบัน

| แกน | Driver | PUL/DIR | สถานะยืนยัน |
|---|---|---|---|
| X | HBS860H | common-anode ผ่าน Q1/Q2 | แกนและ logic voltage ต้องตรวจป้าย/สายจริง |
| Y | HBS860H | common-anode ผ่าน Q3/Q4 | ยืนยันจาก wiring ล่าสุด; ยังต้องตรวจป้ายและ input rating ของตัวจริง |
| Z | DM542 ที่ติดตั้ง | common-anode ผ่าน Q5/Q6 | ต้องยืนยันว่าเป็น DM542 revision ใดและรับ 5/24 V แบบใด |

`ENA+/-` ไม่ได้ถูกกำหนดใน `nucleo_motion.c` ห้ามผูก ENA เป็น ON ถาวรโดยอ้างเอกสารนี้
วงจร E-Stop/safety relay ต้องปลด torque หรือ power ตาม risk assessment โดยไม่พึ่ง STM32

## 6. Firmware ที่พบใน workspace

มี source สองสถานะซึ่งต้องไม่สับสน:

1. [`firmware/nucleo_f439zi/README.md`](../firmware/nucleo_f439zi/README.md) ระบุว่า
   safe-link binary รองรับเฉพาะ `PING/STATUS` และไม่เปิด motion output
2. [`NaritVendingV1/stm32/Src/nucleo_serial_link.c`](../NaritVendingV1/stm32/Src/nucleo_serial_link.c)
   มี source command `MOVE X|Y|Z dir steps speed` และเรียก `Stepper_Move()`
3. Binary `nucleo_f439zi_safe_link.bin` ที่พบใน workspace **ไม่มีข้อความ `MOVE `** แต่มี
   `PING`, `STATUS` และ `UNKNOWN_COMMAND` จึงต้องถือว่า binary นี้ไม่ขับ motion

ห้ามสรุปว่าบอร์ดที่เสียบอยู่กำลังรัน motion firmware จาก source code เพียงอย่างเดียว
ก่อนทดสอบต้องบันทึก SHA-256 ของ binary ที่ flash, อ่าน firmware identity/version และตรวจ
pulse ด้วย oscilloscope ที่ Gate/Drain โดยยังไม่ต่อ driver

## 7. ข้อจำกัดด้าน motion และ safety

source candidate `nucleo_motion.c` ปัจจุบันมี default-disarmed, จำกัดคำสั่งที่
`10-1000 Hz` และไม่เกิน `10000 steps`, ป้องกันสั่งแกนซ้อน และ watchdog 500 ms
ซึ่งหยุด output เมื่อ heartbeat ขาด อย่างไรก็ตามยังไม่มี:

- hardware E-Stop input และ immediate timer-output shutdown
- head/tail limit inputs ของ X/Y/Z
- driver alarm inputs
- ENA outputs หรือ hardwired enable-permissive feedback
- acceleration/deceleration profile
- safety permissive แบบ hardwired ที่เข้าขา interrupt ของ STM32 โดยตรง

watchdog เป็นเพียง operational stop ไม่ใช่ safety function ดังนั้นวงจรนี้เหมาะสำหรับ bench
test แบบ uncoupled/ความเร็วต่ำเท่านั้น จนกว่าฟังก์ชันข้างต้น
จะถูกออกแบบ ทดสอบ และมีวงจร safety hardwired ผ่านการตรวจรับ

## 8. Checklist ยืนยัน AS-BUILT

- [ ] ถ่ายรูปด้านบน/ล่างของ NMOS board และอ่าน part number Q1-Q6
- [ ] วัดและบันทึกค่า Rg/Rpd ทุกช่อง
- [ ] วัด `V-PULSE` และยืนยัน selector/resistor ของ HBS860H, driver Y และ DM542
- [ ] continuity จาก CN10/CN7 ไป Gate และจาก Drain ไป terminal driver ทีละเส้น
- [ ] ยืนยัน Source ทั้งหกต่อ `0V-SIGNAL` และ STM32 GND จริง
- [ ] เปิดไฟเฉพาะ logic วัดว่า Drain ทุกช่องอยู่ OFF ระหว่าง reset/boot
- [ ] ทดสอบ PUL/DIR ด้วย dummy optocoupler แล้วตรวจ pulse width/frequency/polarity
- [ ] ยืนยัน binary ที่ flash มี hash/version ตรงกับ release ที่อนุมัติ
- [ ] ทดสอบ E-Stop โดยถอด USB/network และจำลอง firmware hang
- [ ] ตรวจว่า reset หรือ communication กลับมาไม่ทำให้มอเตอร์เริ่มเอง
- [ ] หลังยืนยันครบ เปลี่ยนหัวเอกสารจาก provisional เป็น VERIFIED AS-BUILT พร้อมวันที่/ผู้ตรวจ

## 9. แหล่งอ้างอิง

- [STMicroelectronics UM1974, STM32 Nucleo-144 boards (MB1137)](https://www.st.com/resource/en/user_manual/dm00244518-stm32-nucleo-144-boards-mb1137-stmicroelectronics.pdf),
  ตาราง pin assignment สำหรับ NUCLEO-F429ZI/F439ZI
- `NaritVendingV1/stm32/Src/nucleo_motion.c` สำหรับ timer และ GPIO mapping
- `firmware/nucleo_f439zi/README.md` และ binary safe-link สำหรับสถานะ firmware ที่ deploy ได้
- ป้าย terminal/logic-voltage และคู่มือของ driver serial/lot ที่ติดตั้งจริงเป็นข้อมูลลำดับสูงสุด
