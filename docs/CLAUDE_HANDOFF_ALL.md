# NARIT Vending — Handoff Entry Point

เอกสาร handoff รุ่นเดิมถูกแทนที่แล้ว เพราะอ้าง Raspberry Pi GPIO, driver และ runtime
ที่ไม่ตรงกับตู้ IRIV + NUCLEO ปัจจุบัน

ให้เริ่มจากเอกสารต่อไปนี้ตามลำดับ:

1. [HANDOFF_CURRENT_TH.md](HANDOFF_CURRENT_TH.md)
2. [ARCHITECTURE_TH.md](ARCHITECTURE_TH.md)
3. [IRIV_WIRING_TH.md](IRIV_WIRING_TH.md)
4. [STM32_NMOS_CURRENT_WIRING_TH.md](STM32_NMOS_CURRENT_WIRING_TH.md)

ข้อห้าม: อย่า discard dirty worktree, อย่าเปิดเผย credential และอย่า flash/ARM/MOVE
จนกว่า production enablement gate ใน `ARCHITECTURE_TH.md` จะผ่านครบ

