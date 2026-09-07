# Safety และ Recovery

เส้นทางคำสั่งคือ Web → CommandEnvelope → Controller IPC → SafetyInterlock → Motion/NUCLEO ห้าม Web เขียน GPIO หรือสร้าง pulse

DI10 เป็น NC fail-safe input: Active หรือ Modbus stale จะ Stop ทุกแกน, Disarm NUCLEO, ยกเลิก Arm/Demo, ล้าง Homed และ Disable Motion

## สิ่งที่ห้าม bypass

- Physical E-Stop และ DI10
- Physical/software Stop
- Driver alarm
- NUCLEO USB watchdog/handshake failure
- IRIV communication failure
- Controller communication fault

Allow Unhomed และ Ignore Position Limits ใช้ได้เฉพาะ Manual Commissioning และไม่สามารถข้ามรายการข้างต้น

## Recovery checklist

1. แก้สาเหตุทางกล/ไฟฟ้าก่อน
2. ปลด E-Stop และยืนยัน DI10 `HIGH / CLEAR`
3. ยืนยัน IRIV I/O และ NUCLEO Online
4. Clear Alarm
5. Enable Motion
6. Home ใหม่
7. เริ่มด้วยความเร็วต่ำ

หลัง Controller หรือ NUCLEO restart ต้องถือว่า reference อาจสูญหายและ Home ใหม่ก่อน absolute motion

## เมื่อคำสั่งถูกปฏิเสธ

1. ห้ามกดซ้ำต่อเนื่องโดยไม่อ่านสาเหตุ
2. ตรวจข้อความ interlock และ Event Log
3. ตรวจ `busy`, active command, E-Stop, stop latch และ alarm
4. ตรวจ Home เฉพาะแกนที่คำสั่งต้องใช้
5. หากเปลี่ยน target/speed ของ GOTO ให้ Validate → Preview → Arm ใหม่
6. หากเป็น Min/Max หรือ Jog หลังเปลี่ยน speed ปุ่มควรพร้อมทันทีเมื่อแกนนั้น Home และ safety clear

## เมื่อ motion ยาวหยุดกลางทาง

Controller แบ่ง motion ยาวเป็น USB segments และตรวจ safety ทุกช่วง หากหยุดกลางทางให้ตรวจ limit, E-Stop, Stop, driver alarm และ USB heartbeat ห้ามคาดเดาตำแหน่งหรือสั่งต่อจนกว่าจะยืนยัน position/reference หากมี safety interruption ระบบอาจล้าง Homed และต้อง Home ใหม่

Software stop ของ Z ไม่ป้องกันกรณี Pi, USB, STM32 หรือ driver ล้มเหลว ต้องต่อ Enable/power ของ Z ผ่าน safety-rated relay/contactor
