# Handoff Package Manifest

Package: `NARIT_VENDING_HANDOFF_20260903.zip`

รวม:

- `README.md`
- architecture, handoff, wiring และ API documentation
- root Python application, tests, scripts และ systemd deployment files
- IRIV machine/hardware configuration
- `NaritVendingV1` deployable profile รวม STM32 source
- Nucleo firmware README, safe-link artifacts และ unflashed motion candidate

ไม่รวม:

- `.git`, `.venv`, IDE settings และ caches
- local/remote backups
- logs, temporary output และ generated scratch files
- `NaritVendingMOCKUP` ซึ่งเป็นคนละ hardware profile
- `/etc/narit-vending.env` และ credentials ทุกชนิด

Package นี้เป็น source snapshot สำหรับ review/ส่งต่อ ไม่ใช่คำสั่งอนุญาตให้ flash หรือ
เคลื่อนมอเตอร์ ผู้รับช่วงต้องอ่าน `HANDOFF_CURRENT_TH.md` และ safety gate ก่อน

