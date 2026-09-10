# ระบบเครือข่ายสำหรับ NaritVendingMachine HMI

## เป้าหมาย

ให้ผู้ใช้ต่อพอร์ต Management LAN ของ IRIV Pi เข้ากับวง LAN ที่มี DHCP แล้วเปิด HMI ด้วยชื่อคงที่:

`http://naritvendingmachine.local/`

เว็บ bind ที่ `0.0.0.0:80` อยู่แล้ว จึงรับการเชื่อมต่อจากทุก IPv4 address ของเครื่อง ส่วนชื่อ `.local` ประกาศด้วย mDNS/Avahi และไม่ผูกกับวง `192.168.70.0/24`

## สถาปัตยกรรมที่แนะนำ

- `eth0` เป็น Management LAN: ใช้ DHCP เพื่อรับ IP, gateway และ DNS ของวงที่นำเครื่องไปเสียบ
- `eth1` เป็น OT/IRIV I/O network: คง static IP เดิมและ **ไม่มี default gateway**
- Avahi ประกาศ hostname `naritvendingmachine.local` และบริการ HTTP port 80
- Controller และ Web ยังรันในเครื่องเดียวกันผ่าน local IPC การเปลี่ยน Management IP จึงไม่เปลี่ยน motion authority
- เก็บ IP ปัจจุบันไว้เป็น maintenance fallback และแสดง IP ที่ได้รับในหน้า System Control & Health

ห้าม bridge, NAT หรือ share Internet จาก `eth0` ไป `eth1` เพราะจะทำลายการแยก OT network

## ติดตั้งชื่อเครื่อง

คำสั่งนี้อาจทำให้ชื่อ SSH เดิมเปลี่ยน จึงไม่รวมไว้ในการ Deploy อัตโนมัติ:

```bash
cd /home/admin/NaritVendingV1
sudo bash scripts/configure_hmi_hostname.sh --apply
```

หลังทำแล้วทดสอบจากคอมพิวเตอร์ใน LAN เดียวกัน:

```text
http://naritvendingmachine.local/
```

## เงื่อนไขของเครือข่ายปลายทาง

1. LAN ต้องมี DHCP หรือกำหนด DHCP reservation ให้ MAC address ของ `eth0`
2. Client กับ HMI ต้องอยู่ broadcast/VLAN ที่อนุญาต mDNS UDP 5353 multicast `224.0.0.251`
3. Firewall ต้องอนุญาต TCP 80 จาก Management LAN
4. หากองค์กรปิด mDNS ให้ผู้ดูแล DNS สร้าง record `naritvendingmachine` ชี้ไป DHCP reservation แล้วเข้า `http://naritvendingmachine/`
5. หาก LAN ไม่มี DHCP และต้องการเสียบตรงกับโน้ตบุ๊ก ควรเพิ่มโหมด fallback link-local หรือ maintenance access point เป็นงานแยก และต้องทดสอบไม่ให้กระทบ `eth1`

## Acceptance tests

- เปลี่ยนไปอย่างน้อยสองวง DHCP แล้วชื่อ `.local` ยังเปิด HMI ได้
- Refresh/deep link เช่น `#sequence-monitor` ใช้งานได้
- ถอด Management LAN แล้ว motion ที่ทำงานอยู่เข้าสู่สถานะตาม communication safety policy
- `eth1` ยังเข้าถึง IRIV I/O ที่ static address เดิมและไม่มี default route
- รีบูตแล้ว Avahi, Web และ Controller กลับมาทำงาน
- ทดสอบด้วย Windows, tablet และ mobile ที่จะใช้จริง เพราะบางเครือข่ายปิด multicast

ชื่อ `.local` ช่วยค้นหาเครื่องในวง LAN แต่ไม่ใช่กลไกความปลอดภัย การอนุญาต motion ยังคงต้องผ่าน Controller, E-Stop, alarms, homing และ interlocks ตามเดิม
