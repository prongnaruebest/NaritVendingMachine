from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "pdf" / "narit-vending-control-box-wiring.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

FONT = r"C:\Windows\Fonts\tahoma.ttf"
FONT_B = r"C:\Windows\Fonts\tahomabd.ttf"
pdfmetrics.registerFont(TTFont("TH", FONT))
pdfmetrics.registerFont(TTFont("THB", FONT_B))

PAGE = landscape(A3)
W, H = PAGE
M = 28
INK = HexColor("#17202A")
BLUE = HexColor("#1769AA")
CYAN = HexColor("#DFF3FF")
GREEN = HexColor("#DFF4E4")
ORANGE = HexColor("#F9E5C7")
RED = HexColor("#B83227")
PINK = HexColor("#FBE1DF")
GRAY = HexColor("#EFF2F4")
MID = HexColor("#64727D")
YELLOW = HexColor("#FFF4C2")


def wrap(text, font="TH", size=9, width=180):
    words = str(text).split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def text(c, x, y, s, size=9, font="TH", color=INK, maxw=None, leading=None):
    c.setFillColor(color)
    c.setFont(font, size)
    lines = wrap(s, font, size, maxw) if maxw else str(s).split("\n")
    lead = leading or size * 1.35
    for i, line in enumerate(lines):
        c.drawString(x, y - i * lead, line)
    return y - len(lines) * lead


def centered(c, x, y, s, size=9, font="TH", color=INK):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawCentredString(x, y, s)


def box(c, x, y, w, h, title, body="", fill=GRAY, stroke=MID, title_size=10):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
    centered(c, x + w / 2, y + h - 16, title, title_size, "THB")
    if body:
        lines = wrap(body, "TH", 8, w - 14)
        start = y + h - 31
        for i, line in enumerate(lines[:5]):
            centered(c, x + w / 2, start - i * 11, line, 8)


def arrow(c, x1, y1, x2, y2, label="", color=INK, dashed=False):
    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.5)
    if dashed:
        c.setDash(5, 3)
    c.line(x1, y1, x2, y2)
    import math
    a = math.atan2(y2-y1, x2-x1)
    for off in (2.55, -2.55):
        c.line(x2, y2, x2 + 8*math.cos(a+off), y2 + 8*math.sin(a+off))
    c.restoreState()
    if label:
        c.setFillColor(white)
        tw = stringWidth(label, "TH", 7.5)
        c.rect((x1+x2)/2-tw/2-3, (y1+y2)/2-5, tw+6, 11, fill=1, stroke=0)
        centered(c, (x1+x2)/2, (y1+y2)/2-2, label, 7.5, color=color)


def header(c, title, subtitle, page_no, rev="A - PRELIMINARY"):
    c.setFillColor(INK)
    c.rect(0, H-55, W, 55, fill=1, stroke=0)
    text(c, M, H-24, title, 17, "THB", white)
    text(c, M, H-43, subtitle, 8.5, "TH", HexColor("#DDE6EC"))
    c.setFillColor(white)
    c.setFont("THB", 9)
    c.drawRightString(W-M, H-24, f"NARIT VENDING | {rev}")
    c.setFont("TH", 8)
    c.drawRightString(W-M, H-42, f"หน้า {page_no}/5 | 18 Aug 2026")


def footer(c):
    c.setStrokeColor(MID); c.setLineWidth(.5); c.line(M, 22, W-M, 22)
    text(c, M, 10, "แบบนี้เป็นแบบ Preliminary สำหรับจัดตู้และทำ Label - ต้องตรวจรุ่น, datasheet, กระแสโหลด, ระบบกราวด์ และทดสอบโดยช่างไฟ/วิศวกรก่อนจ่ายไฟ", 7.2, color=RED)


def table(c, x, y_top, widths, rows, row_h=22, header_rows=1, font_size=7.5):
    y = y_top
    for ri, row in enumerate(rows):
        h = row_h
        c.setFillColor(INK if ri < header_rows else (GRAY if ri % 2 == 0 else white))
        c.rect(x, y-h, sum(widths), h, fill=1, stroke=0)
        xx = x
        for ci, cell in enumerate(row):
            c.setStrokeColor(HexColor("#AAB4BA")); c.rect(xx, y-h, widths[ci], h, fill=0, stroke=1)
            col = white if ri < header_rows else INK
            lines = wrap(cell, "THB" if ri < header_rows else "TH", font_size, widths[ci]-8)
            for li, line in enumerate(lines[:2]):
                text(c, xx+4, y-9-li*9, line, font_size, "THB" if ri < header_rows else "TH", col)
            xx += widths[ci]
        y -= h
    return y


c = canvas.Canvas(str(OUT), pagesize=PAGE)
c.setTitle("Narit Vending Control Box - Block and Wiring Diagram")
c.setAuthor("OpenAI Codex - Preliminary engineering drawing")

# PAGE 1 - architecture
header(c, "Block Diagram - ตู้คอนโทรล Narit Vending", "ฐานการออกแบบ: 1-phase 220-230 VAC, L/N/PE | แยก Power, Control และ Motion", 1)
box(c, 36, 378, 110, 92, "X1 - AC IN", "L / N / PE\n220-230 VAC 1-phase", YELLOW)
box(c, 182, 378, 105, 92, "QF1", "MCB 2P C16A\nMain isolating breaker", PINK)
box(c, 323, 378, 125, 92, "SPD1", "Type 2, 1P+N\nต่อขนาน L/N ลง PE\nต้องเพิ่มถ้ายังไม่มี", ORANGE)
box(c, 484, 378, 125, 92, "VP1", "Over/under-voltage protector\nอุปกรณ์จอดิจิทัลเดิม\nต่ออนุกรม L/N", ORANGE)
box(c, 645, 378, 110, 92, "K1", "2P contactor\nตัดกำลัง Motion\nจาก E-Stop", PINK)
for a,b in [(146,182),(287,323),(448,484),(609,645)]: arrow(c,a,424,b,424,"L/N")
arrow(c, 86,378,86,335,"PE", HexColor("#14853B"))
box(c, 36, 270, 140, 55, "PE BAR", "ตู้ / ประตู / DIN / PSU frame / shield clamp", GREEN)

box(c, 815, 420, 150, 72, "PS2 - 60 VDC", "PSU กำลังสำหรับ HBS860H x2\nขนาดกระแส: TBD จากโหลด", CYAN)
box(c, 815, 306, 150, 72, "PS1 - 24 VDC", "Delta LYTE II 120 W (จากภาพ)\nControl + I/O + DM542*", CYAN)
arrow(c,755,430,815,456,"AC หลัง K1")
arrow(c,609,398,780,342,"AC control")

box(c, 1010, 438, 150, 56, "D2 - HBS860H AXIS X", "+60/0V | A+/A-/B+/B- | Encoder", CYAN)
box(c, 1010, 366, 150, 56, "D3 - HBS860H AXIS Y", "+60/0V | A+/A-/B+/B- | Encoder", CYAN)
box(c, 1010, 294, 150, 56, "D1 - DM542 AXIS Z", "20-50 VDC เท่านั้น\nห้ามต่อ 60 VDC", YELLOW)
arrow(c,965,456,1010,466,"F2.1 +60")
arrow(c,965,342,1010,322,"F1.3 +24*")
arrow(c,965,456,1010,394,"F2.2 +60")

box(c, 410, 174, 190, 70, "U1 - IRIV PiControl CM4", "Main logic / UI / Network\nรับไฟ 24 VDC ตาม terminal รุ่นจริง", GREEN)
box(c, 665, 174, 190, 70, "U2 - IRIV IO Controller", "Remote I/O / sensors / actuators\nเชื่อม U1 ผ่าน Ethernet หรือ RS485", GREEN)
box(c, 920, 156, 200, 100, "MC1 - Motion Controller (อนาคต)", "PUL/DIR/ENA แบบ differential\nAxis X -> D2 | Axis Y -> D3 | Axis Z -> D1\nLinux/CM4 ไม่ควรสร้าง pulse โดยตรง", YELLOW)
arrow(c,600,209,665,209,"Ethernet / RS485")
arrow(c,855,209,920,209,"Command / status", dashed=True)
for yy, target_y in [(229,466),(209,394),(189,322)]:
    arrow(c,1120,yy,1165,target_y,"PUL/DIR/ENA",BLUE,True)
arrow(c,815,330,600,210,"+24 / 0V")
arrow(c,815,330,760,244,"+24 / 0V")

text(c, 38, 135, "Design decisions", 10, "THB")
notes = [
    "1. SPD1 และ VP1 ทำหน้าที่ต่างกัน: SPD ลด surge ชั่วขณะ; VP ตัดเมื่อแรงดันไฟเกิน/ตกค้างนาน",
    "2. กด E-Stop ให้ K1 ตกและตัด PSU motion; คง PS1/U1/U2 ไว้เพื่อบันทึก fault และ shutdown อย่างปลอดภัย",
    "3. DM542E ตาม Leadshine ใช้ 20-50 VDC (แนะนำ 24-48 VDC); ต่อ 24 V ได้เมื่อคำนวณกำลัง PS1 แล้วผ่าน มิฉะนั้นเพิ่ม PSU 36/48 V แยก",
    "4. สาย encoder และ PUL/DIR ใช้ twisted pair shielded แยกรางจาก AC/สายมอเตอร์ และต่อ shield เข้าจุด clamp/PE ตามคู่มือ",
]
yy=118
for n in notes:
    yy=text(c, 38, yy, n, 8.2, maxw=1120, leading=11)-1
footer(c); c.showPage()

# PAGE 2 - power wiring
header(c, "Power Wiring - AC, 24 VDC, 60 VDC และ PE", "เส้นทึบ = ติดตั้งปัจจุบัน | เส้นประ = อุปกรณ์แนะนำ/เผื่อเพิ่ม | ค่า fuse/MCB ปลายทางต้องคำนวณจาก nameplate", 2)

rows = [
 ["จาก", "ขั้วต้นทาง", "Wire ID", "ผ่าน", "ขั้วปลายทาง", "สาย/สีแนะนำ", "หมายเหตุ"],
 ["X1", "1:L", "W001", "QF1 pole 1", "QF1-1", "Brown 2.5 mm2", "ไฟเข้าหลัก"],
 ["X1", "2:N", "W002", "QF1 pole 2", "QF1-3", "Light blue 2.5 mm2", "ตัดทั้ง L และ N"],
 ["X1", "3:PE", "PE001", "PE bar", "PE-01", "Green/yellow >=2.5 mm2", "ต่อก่อนและถอดทีหลัง"],
 ["QF1", "2:L-out", "W011", "TB-AC-L", "VP1 L-IN + SPD1 L", "Brown 2.5 mm2", "SPD ต่อขนาน; สายสั้นตรง"],
 ["QF1", "4:N-out", "W012", "TB-AC-N", "VP1 N-IN + SPD1 N", "Light blue 2.5 mm2", "SPD PE -> PE bar"],
 ["VP1", "L/N OUT", "W021/022", "QF2 branch", "PS1 L/N", "Brown/blue 1.5 mm2", "QF2 แนะนำ 2P C2A; ยืนยัน inrush"],
 ["VP1", "L/N OUT", "W023/024", "E-Stop + K1 + QF3", "PS2 L/N", "Brown/blue 2.5 mm2", "QF3 size ตาม PSU60 nameplate"],
 ["PS1", "+24V / 0V", "W101/102", "TB24 + F1.1", "U1 PWR+/PWR-", "Red/dark blue 0.75 mm2", "ยืนยันชื่อ terminal จากรุ่นจริง"],
 ["PS1", "+24V / 0V", "W103/104", "TB24 + F1.2", "U2 7-35V/GND", "Red/dark blue 0.75 mm2", "จากภาพ U2 ระบุ 7-35V"],
 ["PS1", "+24V / 0V", "W105/106", "TB24 + F1.3", "D1 VDC/GND", "Red/dark blue 1.5 mm2", "ใช้ได้เฉพาะ PS1 capacity ผ่าน"],
 ["PS2", "+60V / 0V", "W201/202", "TB60 + F2.1 DC", "D2 +VDC/GND", "Orange/gray 2.5 mm2", "Fuse DC-rated ใกล้ distribution"],
 ["PS2", "+60V / 0V", "W203/204", "TB60 + F2.2 DC", "D3 +VDC/GND", "Orange/gray 2.5 mm2", "ห้ามรวม 0V กับ PE โดยพลการ"],
 ["PE bar", "PE-02..08", "PE010..", "Bonding", "Door/DIN/PSU/D1-D3", "Green/yellow", "ใช้ star/short bonding"],
]
table(c, 32, H-78, [85,92,72,116,120,145,455], rows, row_h=28, font_size=7.3)

text(c, 35, 176, "Single-line arrangement", 10, "THB")
box(c, 35, 82, 98, 70, "X1", "L N PE", YELLOW)
box(c, 165, 82, 98, 70, "QF1", "2P C16A", PINK)
box(c, 295, 82, 98, 70, "TB-AC", "L / N", GRAY)
box(c, 425, 82, 98, 70, "VP1", "OV/UV", ORANGE)
box(c, 555, 82, 98, 70, "QF2", "PS1 branch", PINK)
box(c, 685, 82, 98, 70, "PS1", "24 VDC", CYAN)
box(c, 825, 82, 98, 70, "K1/QF3", "Motion branch", PINK)
box(c, 965, 82, 98, 70, "PS2", "60 VDC", CYAN)
box(c, 1100, 82, 70, 70, "D2/D3", "F2.1/F2.2", CYAN)
for a,b,l in [(133,165,"L/N"),(263,295,"L/N"),(393,425,"L/N"),(523,555,"L/N"),(653,685,"L/N"),(523,825,"L/N"),(923,965,"L/N"),(1063,1100,"60V")]: arrow(c,a,117,b,117,l)
arrow(c,345,82,345,48,"SPD1 -> PE",ORANGE,True)
footer(c); c.showPage()

# PAGE 3 - motion wiring
header(c, "Motion Wiring - PUL/DIR/ENA, Motor และ Encoder", "แนะนำ differential line driver 5 V จาก MC1 | Shield drain ต่อที่ PE clamp ฝั่งตู้เพียงจุดเดียว เว้นแต่คู่มือระบบกำหนดต่างออกไป", 3)

rows = [["Axis", "MC1 output", "Wire ID", "Drive terminal", "Cable/Pair", "Field connection / note"]]
for axis, drv, base in [("X","D2 HBS860H",301),("Y","D3 HBS860H",311),("Z","D1 DM542",321)]:
    rows += [
      [axis, f"{axis}_PUL+ / {axis}_PUL-", f"W{base}/W{base+1}", f"{drv}: PUL+ / PUL-", "Pair 1 shielded", "Pulse differential"],
      [axis, f"{axis}_DIR+ / {axis}_DIR-", f"W{base+2}/W{base+3}", f"{drv}: DIR+ / DIR-", "Pair 2 shielded", "Direction differential"],
      [axis, f"{axis}_ENA+ / {axis}_ENA-", f"W{base+4}/W{base+5}", f"{drv}: ENA+ / ENA-", "Pair 3 shielded", "Enable; อาจเว้นว่างตามคู่มือ"],
    ]
table(c, 35, H-78, [70,180,90,240,140,440], rows, row_h=25, font_size=7.4)

box(c, 46, 142, 170, 100, "MC1 - differential outputs", "X/Y/Z PUL+/-\nX/Y/Z DIR+/-\nX/Y/Z ENA+/-", GREEN)
box(c, 343, 172, 190, 70, "D2 - HBS860H Axis X", "PUL DIR ENA | ALM/PEND", CYAN)
box(c, 343, 82, 190, 70, "D3 - HBS860H Axis Y", "PUL DIR ENA | ALM/PEND", CYAN)
box(c, 670, 126, 180, 70, "D1 - DM542 Axis Z", "PUL DIR ENA", YELLOW)
arrow(c,216,205,343,207,"3 twisted pairs",BLUE)
arrow(c,216,178,343,117,"3 twisted pairs",BLUE)
arrow(c,216,162,670,161,"3 twisted pairs",BLUE)
box(c, 935, 172, 220, 70, "M2/M3 - Closed-loop stepper", "D2/D3: A+/A-/B+/B-\nEncoder EA+/EA-/EB+/EB-/VCC/EGND", GRAY)
box(c, 935, 82, 220, 70, "M1 - Stepper", "D1: A+/A-/B+/B-\nไม่มี encoder ที่ DM542", GRAY)
arrow(c,533,207,935,207,"Motor + encoder (แยกสาย)")
arrow(c,850,161,935,117,"Motor cable")

text(c, 46, 57, "หมายเหตุสัญญาณ: ถ้า MC1 เป็น 12/24 V single-ended ต้องใช้ค่า series resistor/การต่อ common-anode หรือ common-cathodeตามคู่มือของ drive รุ่นจริง ห้ามเดาค่า resistor จาก HBS รุ่นอื่น", 7.8, color=RED, maxw=1090)
footer(c); c.showPage()

# PAGE 4 - terminal and labels
header(c, "Terminal Plan และ Label Schedule", "รูปแบบป้าย: [Device]-[Terminal] ที่ปลายสายทั้งสองด้าน + Wire ID กลางสาย | ติดป้าย axis ที่ drive, motor และ connector", 4)
rows = [
 ["Terminal block", "Terminal", "Function", "Label / wire", "Destination", "Color"],
 ["X1", "1 / 2 / 3", "Incoming L / N / PE", "L-IN / N-IN / PE-IN", "QF1 / PE bar", "Brown / light blue / G-Y"],
 ["TB-AC", "L1 / N1", "Protected AC distribution", "AC-L / AC-N", "VP1, branches", "Brown / light blue"],
 ["TB24", "+01 / 0-01", "24 V to U1", "+24-U1 / 0V-U1", "IRIV PiControl", "Red / dark blue"],
 ["TB24", "+02 / 0-02", "24 V to U2", "+24-U2 / 0V-U2", "IRIV IO", "Red / dark blue"],
 ["TB24", "+03 / 0-03", "24 V to D1", "+24-D1 / 0V-D1", "DM542", "Red / dark blue"],
 ["TB60", "+01 / 0-01", "60 V to Axis X", "+60-X / 0V60-X", "HBS860H D2", "Orange / gray"],
 ["TB60", "+02 / 0-02", "60 V to Axis Y", "+60-Y / 0V60-Y", "HBS860H D3", "Orange / gray"],
 ["TB-MOT-X", "1..10", "A+/A-/B+/B-/EA+/EA-/EB+/EB-/5V/EGND", "X-MOT-* / X-ENC-*", "Motor X", "Numbered + shield"],
 ["TB-MOT-Y", "1..10", "A+/A-/B+/B-/EA+/EA-/EB+/EB-/5V/EGND", "Y-MOT-* / Y-ENC-*", "Motor Y", "Numbered + shield"],
 ["TB-MOT-Z", "1..4", "A+/A-/B+/B-", "Z-MOT-A+...", "Motor Z", "Numbered + shield"],
 ["PE", "01..08", "Protective earth / shield clamp", "PE-xx", "Door, DIN, PSU, chassis", "Green/yellow"],
]
table(c, 35, H-78, [120,100,280,210,260,175], rows, row_h=29, font_size=7.7)

text(c, 38, 204, "Device tags", 10, "THB")
tags = [
 ["Tag", "อุปกรณ์", "Tag", "อุปกรณ์", "Tag", "อุปกรณ์"],
 ["QF1", "Main MCB 2P C16", "SPD1", "Surge protective device Type 2", "VP1", "Over/under voltage protector"],
 ["PS1", "24 VDC PSU", "PS2", "60 VDC PSU", "K1", "Motion power contactor"],
 ["U1", "IRIV PiControl CM4", "U2", "IRIV IO Controller", "MC1", "Future motion controller"],
 ["D1", "DM542 Axis Z", "D2", "HBS860H Axis X", "D3", "HBS860H Axis Y"],
]
table(c, 38, 188, [70,270,70,270,70,380], tags, row_h=26, font_size=7.6)
footer(c); c.showPage()

# PAGE 5 - checks and source basis
header(c, "Commissioning Checklist, Open Items และ Reference Basis", "ห้ามจ่ายไฟก่อนปิดรายการ Critical open items ทั้งหมด", 5)
left = 38
text(c,left,H-82,"Critical open items",11,"THB",RED)
items = [
 "[ ] ถ่ายรูป nameplate ด้านข้าง/ขั้วของ HBS860H ทั้ง 2 ตัว และ PSU 60 V ให้ชัดเจน",
 "[ ] ยืนยันว่า PSU60 เป็น 1 ตัวจ่าย 2 drive หรือ 2 PSU แยก drive และระบุกำลัง W/A",
 "[ ] ยืนยันรุ่น DM542/DM542E และกระแสมอเตอร์ Z; คำนวณว่า PS1 24 V 120 W เพียงพอหรือไม่",
 "[ ] ยืนยัน input power terminal และกระแสสูงสุดของ IRIV PiControl/IRIV IO จาก revision จริง",
 "[ ] เลือก Motion Controller และชนิด output: differential 5 V (แนะนำ) หรือ 24 V single-ended",
 "[ ] เลือกขนาด QF2/QF3/F1.x/F2.x ตาม nameplate, inrush, cable ampacity และ breaking capacity",
 "[ ] ยืนยันระบบไฟหน้างาน TN-S/TT, ค่า prospective fault current และหลักดิน/PE continuity",
 "[ ] เพิ่ม E-Stop, contactor K1, feedback auxiliary contact และ safety function ตาม risk assessment ของเครื่อง",
]
yy=H-105
for it in items:
    yy=text(c,left,yy,it,8.5,maxw=590,leading=13)-3

text(c,680,H-82,"Pre-power checks",11,"THB",BLUE)
checks = [
 "[ ] Lockout/tagout; ตรวจไม่มีแรงดันก่อนทำสาย",
 "[ ] Torque terminal ตาม datasheet และทำ pull test ทุกเส้น",
 "[ ] Megger เฉพาะวงจรที่ผู้ผลิตอนุญาต; ถอดอุปกรณ์อิเล็กทรอนิกส์/SPD ก่อน",
 "[ ] PE continuity: ตัวตู้ ประตู DIN rail PSU frame และ shield clamp",
 "[ ] ตรวจ polarity +24/0V, +60/0V ก่อนเสียบ drive/controller",
 "[ ] เปิด QF1 โดยยังไม่ต่อโหลดปลายทาง; วัด AC หลัง VP1 และ DC PSU",
 "[ ] เปิดทีละ branch พร้อม current limit/fuse ที่เหมาะสม",
 "[ ] ทดสอบ E-Stop: motion power ต้องดับ แต่ control power ยังอยู่",
 "[ ] ทดสอบ axis ทีละแกนที่ความเร็วต่ำ; ตรวจ DIR, limit, ALM และ encoder",
]
yy=H-105
for it in checks:
    yy=text(c,680,yy,it,8.5,maxw=480,leading=13)-3

text(c,38,205,"Reference basis (ตรวจเมื่อจัดทำแบบ 18 Aug 2026)",10,"THB")
refs = [
 "Leadshine DM542E official product page: operating 20-50 VDC, recommended 24-48 VDC, PUL/DIR control - https://www.leadshine.com/product-detail/DM542E.html",
 "Cytron IRIV PiControl CM4 datasheet: isolated DI, analog inputs, RS485 and terminal/interface details - https://cdn.robotshop.com/media/C/Cyt/RB-Cyt-425/pdf/iriv-picontrol-ir40-cm4-industrial-controller-cm4-wireless-4gb-ram-32gb-emmc-datasheet.pdf",
 "Cytron IRIV IO Controller datasheet Rev 1.0 (July 2024) - https://www.electrokit.com/upload/quick/96/2c/0543_IRIV-IO-Controller-Datasheet.pdf",
 "Leadshine HBS86/HBS86H manual used only as interface-family reference; NOT proof for HBS860H voltage/resistor values. Actual HBS860H manual/nameplate remains required.",
]
yy=188
for i,r in enumerate(refs,1):
    yy=text(c,38,yy,f"{i}. {r}",7.4,maxw=1110,leading=11)-2

text(c,38,90,"สถานะเอกสาร",9,"THB")
text(c,38,72,"PRELIMINARY - ใช้สำหรับวางระบบ, ระบุสาย และขอข้อมูลเพิ่มเท่านั้น ไม่ใช่แบบ IFC (Issued for Construction)",9,"THB",RED)
text(c,680,90,"Revision note",9,"THB")
text(c,680,72,"Rev A: Initial block, power, motion and label schedule from cabinet photo and provided equipment list.",8)
footer(c); c.save()
print(OUT)
