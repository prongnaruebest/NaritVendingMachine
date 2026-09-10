# แนวทางพัฒนาและส่งต่องาน NaritVendingMachine

เอกสารนี้เป็นข้อตกลงร่วมสำหรับผู้พัฒนา, Codex, Antigravity และ AI ตัวอื่นที่ทำงานกับโปรเจกต์นี้ เป้าหมายคือให้ทุกคนเข้าใจเหตุผลเบื้องหลังสถาปัตยกรรม ทำงานต่อกันได้ และไม่ลดระดับความปลอดภัยของเครื่องจักรเพื่อแก้ปัญหาเฉพาะหน้า

## 1. หลักการออกแบบ

ระบบนี้เป็น Industrial HMI สำหรับเครื่องจริง ไม่ใช่เว็บไซต์สาธิต การออกแบบจึงเรียงลำดับความสำคัญดังนี้:

1. ความปลอดภัยและการหยุดแบบ fail-safe
2. ความถูกต้องของ state และคำสั่ง
3. การวิเคราะห์สาเหตุและการกู้คืน
4. ความเข้าใจง่ายของผู้ควบคุม
5. ประสิทธิภาพและความสวยงาม

Controller เป็น machine authority เพียงจุดเดียว Web UI มีหน้าที่แสดงผล รับ intent และส่ง CommandEnvelope ผ่าน API เท่านั้น ส่วน NUCLEO รับผิดชอบ pulse generation และ watchdog ตาม capability ที่ handshake ได้จริง

## 2. กฎการแก้โค้ด

- เริ่มจากตรวจ `git status` และระบุไฟล์ dirty ที่เป็นของเครื่องจริงหรือของงานอื่น
- ห้าม reset, overwrite หรือรวมไฟล์เหล่านั้นใน commit โดยไม่ทราบเจ้าของและผลกระทบ
- อ่านเส้นทางคำสั่งตั้งแต่ UI → API → Controller → transport/NUCLEO ก่อนแก้ motion bug
- แก้ที่ชั้นซึ่งเป็นเจ้าของ invariant ห้ามใช้ frontend workaround เพื่อหลบ Controller safety
- API payload, หน่วย, timeout, request ID และ capability ต้องมี contract ชัดเจน
- Hardware adapters ต้องแยกจาก business logic เพื่อให้ test ด้วย mock ได้
- State ที่หน้าเว็บแสดงต้องมาจาก Controller snapshot; localStorage ใช้ได้เฉพาะ preference ที่ไม่มีอำนาจเหนือเครื่อง

## 3. แนวทางเขียนคอมเมนต์

ควรเขียนคอมเมนต์เมื่อโค้ดมีสิ่งใดสิ่งหนึ่งต่อไปนี้:

- safety invariant หรือเหตุผลที่ห้ามเปลี่ยนลำดับ
- เงื่อนไข race, timeout, heartbeat หรือการ serialize command
- protocol compatibility/fallback
- conversion ทางกลหรือหน่วยวิศวกรรม
- recovery behavior ที่ดูเหมือนสามารถย่อได้แต่ย่อไม่ได้
- browser lifecycle เช่น blur, page hidden และ hold-to-run stop

ตัวอย่างที่ดี:

```python
# Clear homed state after raw jog because Controller position is no longer
# referenced to a verified sensor coordinate.
axis_state.is_homed = False
```

ตัวอย่างที่ไม่ควรเขียน:

```python
# Set is_homed to false
axis_state.is_homed = False
```

คอมเมนต์ต้องอธิบายเหตุผล ไม่ใช่แปล syntax หาก behavior เปลี่ยน ต้องแก้ทั้งโค้ด คอมเมนต์ เอกสาร และ test ให้ตรงกัน

## 4. รูปแบบโค้ดและชื่อข้อมูล

- ใช้ชื่อที่มีหน่วย เช่น `speed_mm_s`, `pulse_hz`, `timeout_ms`, `control_period_us`
- หลีกเลี่ยง boolean ที่กำกวม เช่น `state` หรือ `flag`; ใช้ `motion_enabled`, `estop_active`
- แยก saved configuration, effective configuration และ hardware-reported capability ให้ชัด
- ฟังก์ชันหนึ่งควรมีหน้าที่เดียว และคืน error ที่ผู้ใช้/ระบบวิเคราะห์สาเหตุได้
- UI component ต้องไม่มี state สำเนาที่ขัดกับ shared store
- สีไม่ใช่ช่องทางเดียวในการสื่อสถานะ ต้องมีข้อความหรือสัญลักษณ์ร่วมด้วย

## 5. Definition of Done

งานหนึ่งถือว่าเสร็จเมื่อ:

- behavior ตรงกับคำขอและไม่ละเมิด safety architecture
- มี regression test สำหรับ bug หรือ test สำหรับ behavior ใหม่
- JavaScript/Python/configuration ผ่าน validation ที่เกี่ยวข้อง
- หน้าเว็บที่แก้ไม่มี console error และไม่มี document horizontal overflow ใน viewport ที่เกี่ยวข้อง
- เอกสารและตัวอย่าง configuration ได้รับการปรับเมื่อ contract เปลี่ยน
- deploy เฉพาะส่วนที่เกี่ยวข้องและ health check ผ่าน
- ไม่เกิด motion จริงจาก automated test หรือ deploy
- commit และ push เฉพาะไฟล์ของ logical change นั้น
- รายงานสิ่งที่ยังไม่ได้ทดสอบกับฮาร์ดแวร์จริงอย่างตรงไปตรงมา

## 6. การ Commit และส่งต่องาน

ทุก logical change ที่จบแล้วต้องมี commit ของตัวเอง ใช้ Conventional Commit และเขียน subject ให้บอกผลลัพธ์ ไม่ใช่บอกเพียงว่า “update code” ก่อน commit ให้ตรวจ staged diff เสมอ และห้ามใช้ `git add .` เมื่อ worktree มีไฟล์ของเครื่องจริงค้างอยู่

ข้อความส่งต่องานขั้นต่ำต้องประกอบด้วย:

- เป้าหมายและเหตุผลของการเปลี่ยน
- ไฟล์/โมดูลที่เป็นเจ้าของ behavior
- invariants และข้อห้ามสำคัญ
- API/configuration/protocol ที่ได้รับผลกระทบ
- tests และผลลัพธ์
- commit hash และสถานะ deploy
- สถานะ Controller/NUCLEO/IRIV I/O
- สิ่งที่ยังไม่ได้ทดสอบจริงและขั้นตอนถัดไป

## 7. การทำงานร่วมกันระหว่าง AI

- AI ตัวใหม่ต้องอ่าน `AGENTS.md` และ source-of-truth documents ก่อนเริ่มงาน
- อย่าเชื่อเอกสารเก่ามากกว่าสถานะ API/configuration ปัจจุบัน ให้ตรวจ revision และ capability ก่อน
- ห้ามทำงานซ้ำหรือแก้ไฟล์เดียวกันพร้อมกันโดยไม่มีการแบ่ง ownership
- หากพบความขัดแย้ง ให้หยุดเฉพาะส่วนที่ขัดแย้ง เก็บหลักฐาน และรายงานก่อนรวมงาน
- AI ที่แก้โค้ดต้องรับผิดชอบ test และเอกสารของการเปลี่ยนนั้นด้วย
- การ review ควรเน้น safety regression, stale state, command serialization, unit conversion และ failure recovery ก่อน style

## 8. Checklist ก่อนทดสอบกับเครื่องจริง

- Controller, NUCLEO, IRIV I/O และ USB handshake ออนไลน์
- E-Stop/Stop/driver alarm/communication watchdog อ่านค่าได้จริง
- ตรวจทิศทาง แกน ความเร็ว และพื้นที่เคลื่อนที่
- ผู้ควบคุมยืนยันพื้นที่ปลอดภัยอย่างชัดเจน
- เริ่มทีละแกนด้วยความเร็วต่ำและมีผู้ควบคุมอยู่ที่ปุ่มหยุด
- บันทึกผล, alarm, position error และ configuration revision
- หยุดทันทีเมื่อผลไม่ตรงที่คาด ห้ามเพิ่มความเร็วเพื่อฝืน fault

เอกสารนี้ต้องปรับตามระบบจริงทุกครั้งที่ architecture, safety rule, deployment workflow หรือ ownership boundary เปลี่ยน

