# คู่มือ Release Migration และ Rollback

เอกสารนี้ใช้กับ NaritVendingMachine ซึ่งเป็นระบบควบคุมเครื่องจักรจริง การตรวจ source,
สร้าง artifact และ rehearsal ไม่ใช่การอนุญาตให้เคลื่อนมอเตอร์ และไม่ยืนยันความปลอดภัยเชิงกล

## 1. สถานะความพร้อมปัจจุบัน

ส่วนที่มี automated tests แล้ว:

- สร้าง code-only ZIP จาก clean Git worktree
- SHA-256 manifest ของทุกไฟล์
- ตรวจไฟล์ซ้ำ, path traversal, checksum และไฟล์ configuration ที่ไม่ควรติดไปกับ release
- แตกไฟล์ลง staging แบบไม่ทับ release เดิม
- ตรวจ Python source และ configuration compatibility แบบ read-only
- activation/health/rollback state machine ด้วย fake runtime
- systemd adapter และ migration interruption recovery ด้วย fake services

ส่วนที่ **ยังห้ามใช้กับ production**:

- ยังไม่มี executor สำหรับ one-time migration ที่สำรอง SQLite และ systemd units จริงแบบครบวงจร
- `scripts/deploy_to_iriv.ps1` ยังเป็น legacy in-place deployment และยังไม่รู้จัก `releases/current/shared`
- service files ปัจจุบันยังชี้ `/home/admin/NaritVendingV1` โดยตรง
- ยังไม่ได้ rehearsal กับ clone ของ filesystem จาก IRIV Pi
- ยังไม่ได้ทำ read-only production smoke test รอบสุดท้าย

ดังนั้นห้ามรัน `scripts/activate_release.py --execute` บนเครื่องจริงจนกว่ารายการข้างต้นจะปิดครบ

## 2. Target directory layout

```text
/home/admin/NaritVendingV1/
├── current -> releases/<release-id>       source ที่ active
├── releases/
│   └── <release-id>/                      immutable source + release-manifest.json
└── shared/
    ├── .venv/                             Python runtime
    ├── release-state.json                 activation state
    └── config/
        ├── machine_config.iriv.json
        ├── hardware_config.iriv.json
        ├── controller_history.sqlite3
        ├── demo_results.sqlite3
        └── backups/config/
```

Source release ห้ามบรรจุ configuration หรือฐานข้อมูล เครื่องจริงต้องใช้ข้อมูลใน `shared/`
เพื่อให้ rollback source code ไม่ย้อน configuration และไม่ทำประวัติการทดสอบสูญหาย
Python runtime canonical path คือ `/home/admin/NaritVendingV1/shared/.venv`

## 3. Mandatory operator gate

ก่อนมี service interruption ผู้ควบคุมต้องยืนยันและบันทึกว่า:

- เครื่องหยุดนิ่ง ไม่มี active command และ motion queue ว่าง
- Motion Authority เป็น Disabled
- E-Stop, physical Stop และ driver alarm แสดงสถานะตรงกับวงจรจริง
- ไม่มีผู้ปฏิบัติงานอยู่ในพื้นที่เสี่ยง
- ยอมรับช่วงเวลาที่ Controller และ Web จะ offline
- configuration revision และ release ID ได้รับการอนุมัติ
- มี backup ที่ตรวจคืนค่าได้ของ configuration, SQLite และ systemd units

ถ้าข้อใดข้อหนึ่งไม่ผ่าน ให้หยุดกระบวนการโดยไม่ stop services

## 4. Read-only production inventory

คำสั่งต่อไปนี้อ่านสถานะเท่านั้นและต้องเก็บ output ไว้กับบันทึกการเปลี่ยนแปลง:

```bash
systemctl is-active narit-vending-controller-iriv.service
systemctl is-active narit-vending-web-iriv.service
systemctl cat narit-vending-controller-iriv.service
systemctl cat narit-vending-web-iriv.service
curl --fail --silent --show-error http://127.0.0.1/health/live
curl --silent --show-error http://127.0.0.1/health/ready
readlink -f /home/admin/NaritVendingV1/current 2>/dev/null || true
```

`/health/ready` อาจตอบ 503 เมื่อยังไม่ Home หรือ interlock ทำงานได้โดยไม่แปลว่า Deploy ล้มเหลว
แต่ `/health/live` ต้องตอบสำเร็จ

## 5. Build และตรวจ release บนเครื่องพัฒนา

```powershell
python scripts/quality_gate.py
python scripts/build_release.py
python scripts/verify_release.py <release.zip> <release.manifest.json>
```

ต้องบันทึก `release_id`, Git commit, configuration revision และ archive SHA-256 ไว้ด้วยกัน
ห้าม build จาก dirty worktree

## 6. Stage และตรวจ compatibility

หลังส่ง ZIP และ manifest ไปยัง staging area ของ target แล้ว ให้ตรวจและแตกไฟล์ด้วย:

```bash
python3 scripts/verify_release.py <release.zip> <release.manifest.json> \
  --stage-root /home/admin/NaritVendingV1/releases \
  --machine-config /home/admin/NaritVendingV1/machine_config.iriv.json \
  --hardware-config /home/admin/NaritVendingV1/hardware_config.iriv.json
```

ใน layout เดิม configuration ยังอยู่ที่ base directory ตัว verifier อ่านเท่านั้น หลัง migration
จึงเปลี่ยนพาธเป็น `shared/config/...` ห้าม stage ทับ release ID เดิม

## 7. Rehearsal ก่อน production migration

รัน local fake-service rehearsal:

```powershell
python scripts/rehearse_release_migration.py
```

ผลที่ต้องเห็น:

- success scenario ลงท้าย `COMPLETE`
- candidate health failure ลงท้าย `ROLLED_BACK`
- ไม่มี Home, Jog, GOTO, Dispense หรือ Demo command

จากนั้นต้อง rehearsal เพิ่มกับ filesystem clone ของ IRIV Pi โดยตรวจว่า configuration และ SQLite
ยังอ่านได้, legacy service restore ได้ และ symlink ชี้ release ที่คาดไว้

## 8. One-time production migration — blocked gate

ยังไม่อนุญาตให้ดำเนินการส่วนนี้อัตโนมัติ จนกว่าจะมี executor และ tests ครบขั้นตอนต่อไปนี้:

1. สร้างและตรวจ backup configuration
2. ใช้ SQLite online backup สำหรับฐานข้อมูลทั้งสองไฟล์
3. สำรอง installed systemd units และ permissions
4. Stop Web แล้วจึง Stop Controller
5. สร้าง `shared/` โดยไม่ลบ legacy files
6. ย้าย `.venv` และสร้าง compatibility symlink สำหรับ legacy rollback
7. สร้าง `current` symlink ไป candidate ที่ verified แล้ว
8. ติดตั้ง units จาก `deploy/release-layout/`
9. daemon-reload แล้ว Start Controller ก่อน Web
10. ตรวจ service activity และ `/health/live`
11. ถ้าไม่ผ่าน ให้ restore units/layout เดิมและตรวจ health ซ้ำ

ห้ามใช้การ copy SQLite ขณะที่มี writer ทำงานแทน online backup

## 9. Activation หลัง migration สำเร็จแล้วเท่านั้น

เริ่มด้วย dry-run เสมอ:

```bash
python3 scripts/activate_release.py <release-id> \
  --releases-root /home/admin/NaritVendingV1/releases \
  --state-file /home/admin/NaritVendingV1/shared/release-state.json \
  --current-link /home/admin/NaritVendingV1/current \
  --machine-config /home/admin/NaritVendingV1/shared/config/machine_config.iriv.json \
  --hardware-config /home/admin/NaritVendingV1/shared/config/hardware_config.iriv.json \
  --controller-service narit-vending-controller-iriv.service \
  --web-service narit-vending-web-iriv.service
```

Dry-run ต้องลงท้ายว่ามีการ validate แต่ไม่มี symlink หรือ service ถูกเปลี่ยน การใช้ `--execute`
ต้องเกิดใน maintenance window หลังผู้ควบคุมยืนยัน และต้องใช้ confirmation token ที่ CLI กำหนด

## 10. Rollback interpretation

| State | ความหมาย | การดำเนินการ |
|---|---|---|
| `HEALTHY` | candidate ผ่าน service และ live health | ทำ read-only acceptance ต่อ |
| `ROLLED_BACK` | candidate ไม่ผ่าน แต่ release เดิมกลับมา healthy | เก็บ logs และห้ามลองซ้ำโดยไม่วิเคราะห์ |
| `FAILED` | candidate และ rollback ไม่ผ่าน | คง Motion Disabled, ใช้ recovery checklist และตรวจหน้างาน |
| `MIGRATING` / `STARTING` ค้าง | process ถูกตัดกลาง migration | ใช้ explicit interruption recovery ก่อนเริ่มใหม่ |

Rollback source code ไม่อนุญาตให้ย้อน configuration โดยอัตโนมัติ เพราะ configuration คือ machine
authority ที่ต้องมี revision, validation และ backup ของตัวเอง

## 11. Post-activation checks ที่ไม่ทำให้มอเตอร์เคลื่อน

- ตรวจ systemd services เป็น active
- ตรวจ `/health/live`
- บันทึก `/health/ready` โดยไม่บังคับให้เป็น 200
- ตรวจ Controller, NUCLEO, IRIV I/O, protocol และ configuration revision จาก HMI/API
- เปิดทุก workspace และตรวจ browser console
- ตรวจ E-Stop display จากสถานะจริงโดยไม่สั่ง motion
- ยืนยันว่าไม่มี command ถูกสร้างจาก deployment

การ Home, Jog, Move Min/Max, GOTO Slot, Dispense และ Demo Sampling ต้องเป็นขั้น acceptance
แยกต่างหากหลังผู้ควบคุมยืนยันพื้นที่ปลอดภัย

## 12. Evidence ที่ต้องเก็บ

- วันที่ เวลา ผู้ดำเนินการ และ maintenance approval
- Git commit, release ID, archive SHA-256 และ configuration revision
- manifest และผล verify/stage
- backup paths และผล integrity check ของ SQLite
- systemd unit ก่อนและหลัง migration
- `/health/live`, `/health/ready` และ service status ก่อน/หลัง
- release state สุดท้ายและ rollback detail ถ้ามี
