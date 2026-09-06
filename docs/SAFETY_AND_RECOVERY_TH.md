# Safety และ Recovery

เส้นทางคำสั่งคือ Web → CommandEnvelope → Controller IPC → SafetyInterlock → Motion/NUCLEO ห้าม Web เขียน GPIO หรือสร้าง pulse

DI10 เป็น NC fail-safe input: Active หรือ Modbus stale จะ Stop ทุกแกน, Disarm NUCLEO, ยกเลิก Arm/Demo, ล้าง Homed และ Disable Motion

## Recovery checklist

1. แก้สาเหตุทางกล/ไฟฟ้าก่อน
2. ปลด E-Stop และยืนยัน DI10 `HIGH / CLEAR`
3. ยืนยัน IRIV I/O และ NUCLEO Online
4. Clear Alarm
5. Enable Motion
6. Home ใหม่
7. เริ่มด้วยความเร็วต่ำ

Software stop ของ Z ไม่ป้องกันกรณี Pi, USB, STM32 หรือ driver ล้มเหลว ต้องต่อ Enable/power ของ Z ผ่าน safety-rated relay/contactor

