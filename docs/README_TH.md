# ศูนย์รวมเอกสาร NaritVendingMachine

อัปเดตสถานะเอกสาร: 10 กันยายน 2026

เอกสารในโฟลเดอร์นี้อธิบายระบบ HMI, Controller, IRIV I/O และ STM32 NUCLEO-F439ZI สำหรับเครื่องจริง ก่อนใช้ข้อมูลด้านสายไฟหรือความปลอดภัยต้องตรวจเทียบกับเครื่อง As-Built เสมอ

## ข้อตกลงวิศวกรรมและการทำงานร่วมกับ AI

ก่อนแก้ไขโค้ด คอนฟิก หรือส่งต่องาน ต้องอ่านและปฏิบัติตามข้อตกลงร่วมต่อไปนี้:

- **[AGENTS.md](../AGENTS.md)** — กฎบังคับสำหรับคน, Codex และ Antigravity
- **[ENGINEERING_WORKFLOW_AND_HANDOFF_TH.md](ENGINEERING_WORKFLOW_AND_HANDOFF_TH.md)** — แนวทางออกแบบ เขียนโค้ด คอมเมนต์ ทดสอบ Deploy และส่งต่องาน

## เริ่มอ่านจากที่นี่

| เอกสาร | ใช้สำหรับ |
|---|---|
| [AGENTS.md](../AGENTS.md) | กฎบังคับสำหรับคน, Codex และ Antigravity |
| [ENGINEERING_WORKFLOW_AND_HANDOFF_TH.md](ENGINEERING_WORKFLOW_AND_HANDOFF_TH.md) | แนวทางออกแบบ เขียนโค้ด คอมเมนต์ ทดสอบ Deploy และส่งต่องาน |
| [USER_MANUAL_TH.md](USER_MANUAL_TH.md) | คู่มือเปิดเครื่อง, Home, Jog, Min/Max, GOTO, Slot และการตั้งความเร็ว |
| [SAFETY_AND_RECOVERY_TH.md](SAFETY_AND_RECOVERY_TH.md) | เงื่อนไข interlock, E-Stop, Stop และขั้นตอนกู้ระบบ |
| [PROJECT_STRUCTURE_TH.md](PROJECT_STRUCTURE_TH.md) | โครงสร้าง source code, process ownership และ data flow |
| [API_REFERENCE.md](API_REFERENCE.md) | Endpoint สำคัญของ Web/Controller |
| [DEMO_SLOT_SAMPLING_TH.md](DEMO_SLOT_SAMPLING_TH.md) | การทดสอบ Demo Slot Sampling แบบมีขอบเขต |
| [ARCHITECTURE_TH.md](ARCHITECTURE_TH.md) | สถาปัตยกรรมฉบับละเอียดและข้อมูลส่งต่องาน |
| [IRIV_WIRING_TH.md](IRIV_WIRING_TH.md) | การเชื่อมต่อ IRIV PiControl, IRIV I/O และ NUCLEO |
| [STM32_NMOS_CURRENT_WIRING_TH.md](STM32_NMOS_CURRENT_WIRING_TH.md) | Pin map และวงจร STEP/DIR ผ่าน NMOS |

## สถานะสำคัญของระบบปัจจุบัน

- Web ส่งคำสั่งผ่าน Controller IPC เท่านั้น
- Controller เป็นเจ้าของ motion, safety, IRIV I/O, NUCLEO USB และ MQTT
- NUCLEO ใช้ USB Serial และ protocol v3 ในเครื่องที่ deploy ปัจจุบัน
- คำสั่ง MOVE ยาวถูกแบ่งเป็น segment ตาม `max_move_steps`; ค่า fallback คือ 10,000 pulses ต่อ USB frame
- การเปลี่ยน speed มีผลกับคำสั่งถัดไป ไม่ retime คำสั่งที่กำลังทำงาน
- GOTO ที่ผ่าน Validate/Preview/Arm แล้วจะถูก invalidate เมื่อ target หรือ speed เปลี่ยน
- X/Y มีการตัดกำลัง 60 V ทางกายภาพเมื่อ E-Stop; Z ยังต้องมี safety-rated relay/contactor เพื่อให้การหยุดไม่พึ่งซอฟต์แวร์เพียงอย่างเดียว

## กฎการใช้เอกสาร

1. เอกสารไม่ได้แทนการตรวจพื้นที่และการควบคุมโดยผู้ปฏิบัติงาน
2. ห้ามใช้ automated test สั่งมอเตอร์จริง
3. ห้าม bypass E-Stop, driver alarm, USB watchdog หรือ communication fault
4. หากเอกสารขัดกับ configuration ที่ deploy หรือเครื่อง As-Built ให้หยุดและตรวจสอบก่อนใช้งาน
