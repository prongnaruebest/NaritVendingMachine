# รายงาน Deploy NUCLEO-G491RE วันที่ 2026-09-20

## ขอบเขต

Deploy Controller/Web release `61ef6a957a8e-c4051c40de67` และทดสอบ Flash firmware Protocol v4 โดยไม่สั่ง Home, Jog, GOTO, Dispense หรือ Demo Sampling

## ผล Controller/Web

- Controller และ Web services ทำงานปกติ
- `/health/live` เป็น `UP`
- configuration revision คือ `5b9251d300995610ff7672311637f50413836bd0009fbbbfd92dd63eb860979e`
- Controller เริ่มต้นโดย `motion_enabled = false`
- automated tests บน development host ผ่าน `515 tests` และ `22 subtests`

## เครื่องมือ Flash และ rollback

- `stlink-tools 1.6.1` ของ Debian ไม่รู้จัก STM32G491RE chip ID `0x479`
- สร้าง `stlink` จาก upstream commit `a7bfb83000567f775b3780dac24ae6f02e449327` แยกไว้ที่ `/opt/stlink-g491`
- สำรอง Flash เดิมครบ 524,288 bytes ก่อนเขียนทุกครั้ง
- SHA-256 rollback image: `cc9d3ff468dae158433f2d887ae7e0b902724574d5fad8312b8e97b3acfbdf9c`
- Backup อยู่ที่ `/home/admin/NaritVendingV1/backups/pre-c5e8b32-20260920-161023/firmware/`

## ผล Flash candidate

- Candidate SHA-256: `750bb9600caccc68b5c12ffa2ad535fa5e438028a5a364ee9db1d23d07fcaa34`
- `st-flash` เขียนสำเร็จและอ่านกลับมาเทียบกับ candidate ตรงกันทุก byte
- หลัง boot Controller ไม่ได้รับ heartbeat จาก NUCLEO ผ่าน ST-LINK VCP และรายงาน `Nucleo heartbeat timed out`
- ไม่พบ capability handshake จึงไม่ผ่าน release gate และไม่มีการเปิด Motion

## การ rollback

- เขียน rollback image เดิมกลับครบ 512 KiB
- อ่าน Flash หลัง rollback และเทียบตรงกันทุก byte
- หลัง rollback NUCLEO กลับมา online, Protocol 4, safe และ disarmed
- IRIV I/O online, X/Y driver alarm ไม่ active และ Motion ยังคง disabled

## งานที่ต้องทำต่อ

ตรวจ firmware startup path ของ candidate โดยเน้น clock, USART/VCP initialization, interrupt/DMA configuration, heartbeat scheduling และ watchdog boot state ก่อนสร้าง artifact ใหม่ ห้าม Flash ซ้ำจน host-side tests, clean build และ serial-handshake bench gate ผ่าน

## Root cause ที่ยืนยันภายหลัง

Debugger ยืนยันว่า CPU ติดอยู่ใน `TIM6_DAC_IRQHandler` ขณะ `HAL_TIM_Base_Start_IT()` ยังไม่คืนค่ากลับมาที่ startup code สาเหตุคือ TIM6 update interrupt เกิดขึ้นทันที แต่ `NucleoG491ControlTimer.running` ยังเป็น 0 ทำให้ handler return โดยไม่ clear UIF และเกิด interrupt storm ก่อนเริ่ม serial link

แก้โดยตั้ง `running = 1` ก่อน enable timer interrupt และ rollback ค่าเป็น 0 หาก HAL start ล้มเหลว พร้อมเพิ่ม C host regression test ที่บังคับให้ ISR เกิดภายใน `HAL_TIM_Base_Start_IT()` เพื่อป้องกันบัคนี้ย้อนกลับมา
