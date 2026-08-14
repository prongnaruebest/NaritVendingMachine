from __future__ import annotations

import json
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "NaritVending_Architecture_Thai.pdf"
CONFIG_PATH = ROOT / "machine_config.json"
FONT_NAME = "TahomaThai"
FONT_PATH = Path("C:/Windows/Fonts/tahoma.ttf")
BOLD_FONT_NAME = "TahomaThaiBold"
BOLD_FONT_PATH = Path("C:/Windows/Fonts/tahomabd.ttf")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
    pdfmetrics.registerFont(TTFont(BOLD_FONT_NAME, str(BOLD_FONT_PATH)))


def styles() -> StyleSheet1:
    base = getSampleStyleSheet()
    base.add(
        ParagraphStyle(
            name="TitleThai",
            parent=base["Title"],
            fontName=BOLD_FONT_NAME,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#0b2a4a"),
            alignment=TA_CENTER,
            spaceAfter=12,
        )
    )
    base.add(
        ParagraphStyle(
            name="HeadingThai",
            parent=base["Heading1"],
            fontName=BOLD_FONT_NAME,
            fontSize=15,
            leading=20,
            textColor=colors.HexColor("#123d6a"),
            spaceBefore=8,
            spaceAfter=8,
        )
    )
    base.add(
        ParagraphStyle(
            name="SubHeadingThai",
            parent=base["Heading2"],
            fontName=BOLD_FONT_NAME,
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#164c83"),
            spaceBefore=4,
            spaceAfter=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="BodyThai",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#1b1f23"),
            spaceAfter=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="SmallThai",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#4f5d73"),
        )
    )
    return base


def page_frame(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.HexColor("#eaf2fb"))
    canvas.rect(0, height - 28 * mm, width, 28 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#123d6a"))
    canvas.setFont(BOLD_FONT_NAME, 12)
    canvas.drawString(18 * mm, height - 17 * mm, "Narit Vending Machine - Architecture & Flow")
    canvas.setFillColor(colors.HexColor("#60758f"))
    canvas.setFont(FONT_NAME, 9)
    canvas.drawRightString(width - 18 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def axis_table(config: dict) -> Table:
    rows = [["แกน", "Pulse Pin", "Dir Pin", "Min Limit", "Max Limit", "Steps/mm", "Max Travel (mm)"]]
    for axis_name in ("x", "y", "z"):
        axis = config["axes"][axis_name]
        rows.append(
            [
                axis_name.upper(),
                axis["pulse_pin"],
                axis["direction_pin"],
                axis["head_limit_pin"],
                axis["tail_limit_pin"],
                axis["steps_per_mm"],
                axis["max_travel_mm"],
            ]
        )
    table = Table(rows, colWidths=[18 * mm, 20 * mm, 18 * mm, 22 * mm, 22 * mm, 25 * mm, 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163e6c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT_NAME),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9eb6d2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f9fe")]),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def slot_summary_table(config: dict) -> Table:
    rows = [["ช่วง Slot", "รายละเอียด"]]
    slot_ranges = [
        ("1-10", "ตำแหน่งสินค้าแถวต้น"),
        ("11-20", "ตำแหน่งสินค้าแถวกลาง"),
        ("21-30", "ตำแหน่งสินค้าแถวท้าย"),
    ]
    for code_range, detail in slot_ranges:
        rows.append([code_range, detail])
    rows.append(["ค่าตั้งต้น", "ทุก slot เริ่มที่ X=0, Y=0, Z=0 และแก้ผ่านหน้าเว็บได้"])
    table = Table(rows, colWidths=[35 * mm, 130 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163e6c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT_NAME),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9eb6d2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f9fe")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return table


def box(drawing: Drawing, x: float, y: float, w: float, h: float, text: str, fill: str = "#eaf2fb") -> None:
    drawing.add(Rect(x, y, w, h, rx=8, ry=8, fillColor=colors.HexColor(fill), strokeColor=colors.HexColor("#1e5c96"), strokeWidth=1.2))
    lines = text.split("\n")
    offset = (len(lines) - 1) * 6
    for index, line in enumerate(lines):
        drawing.add(String(x + w / 2, y + h / 2 + offset / 2 - index * 12, line, fontName=FONT_NAME, fontSize=9, textAnchor="middle", fillColor=colors.HexColor("#173b5f")))


def arrow(drawing: Drawing, x1: float, y1: float, x2: float, y2: float) -> None:
    drawing.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#1e5c96"), strokeWidth=1.1))
    head = Polygon(
        [x2, y2, x2 - 4, y2 + 8, x2 + 4, y2 + 8] if y2 > y1 else [x2, y2, x2 - 4, y2 - 8, x2 + 4, y2 - 8],
        fillColor=colors.HexColor("#1e5c96"),
        strokeColor=colors.HexColor("#1e5c96"),
    )
    drawing.add(head)


def flowchart_web() -> Drawing:
    d = Drawing(170 * mm, 95 * mm)
    box(d, 8 * mm, 70 * mm, 42 * mm, 16 * mm, "ผู้ใช้เปิดเว็บ\nNaritVendingMachine")
    box(d, 64 * mm, 70 * mm, 42 * mm, 16 * mm, "Flask Web App\nwebapp.py")
    box(d, 120 * mm, 70 * mm, 42 * mm, 16 * mm, "MotionService\nจัดคิวคำสั่ง")
    box(d, 64 * mm, 38 * mm, 42 * mm, 16 * mm, "MotionController\nสั่งงานแกน X/Y/Z")
    box(d, 120 * mm, 38 * mm, 42 * mm, 16 * mm, "machine_config.json\nอ่าน/บันทึก slot")
    box(d, 64 * mm, 6 * mm, 42 * mm, 16 * mm, "AxisController\nPulse/Dir/Limit")
    arrow(d, 50 * mm, 78 * mm, 64 * mm, 78 * mm)
    arrow(d, 106 * mm, 78 * mm, 120 * mm, 78 * mm)
    arrow(d, 85 * mm, 70 * mm, 85 * mm, 54 * mm)
    arrow(d, 141 * mm, 70 * mm, 141 * mm, 54 * mm)
    arrow(d, 85 * mm, 38 * mm, 85 * mm, 22 * mm)
    return d


def flowchart_home() -> Drawing:
    d = Drawing(170 * mm, 120 * mm)
    box(d, 55 * mm, 98 * mm, 60 * mm, 16 * mm, "เริ่มคำสั่ง Home แกน")
    box(d, 55 * mm, 74 * mm, 60 * mm, 16 * mm, "ตรวจ E-stop และ Stop Request")
    box(d, 55 * mm, 50 * mm, 60 * mm, 16 * mm, "หมุนทิศไปหา Min Limit\nแล้วปล่อย pulse ทีละ step")
    box(d, 55 * mm, 26 * mm, 60 * mm, 16 * mm, "ชน Min Limit แล้ว backoff\nออกจากสวิตช์เล็กน้อย")
    box(d, 55 * mm, 2 * mm, 60 * mm, 16 * mm, "ตั้งตำแหน่งแกน = 0 mm\nและ is_homed = True", fill="#dff7ea")
    arrow(d, 85 * mm, 98 * mm, 85 * mm, 90 * mm)
    arrow(d, 85 * mm, 74 * mm, 85 * mm, 66 * mm)
    arrow(d, 85 * mm, 50 * mm, 85 * mm, 42 * mm)
    arrow(d, 85 * mm, 26 * mm, 85 * mm, 18 * mm)
    return d


def flowchart_slot() -> Drawing:
    d = Drawing(170 * mm, 95 * mm)
    box(d, 8 * mm, 70 * mm, 40 * mm, 16 * mm, "กดปุ่ม Go To Slot")
    box(d, 58 * mm, 70 * mm, 46 * mm, 16 * mm, "อ่านค่า slot\nX/Y/Z จาก config")
    box(d, 114 * mm, 70 * mm, 48 * mm, 16 * mm, "ถ้า Z ต่ำกว่า safe_z\nยก Z ขึ้นก่อน")
    box(d, 36 * mm, 34 * mm, 48 * mm, 16 * mm, "เคลื่อน X และ Y\nไปยังพิกัดเป้าหมาย")
    box(d, 98 * mm, 34 * mm, 48 * mm, 16 * mm, "เคลื่อน Z ลง\nไปยังจุด slot")
    box(d, 67 * mm, 4 * mm, 48 * mm, 16 * mm, "อัปเดตสถานะ realtime\nส่งกลับหน้าเว็บ", fill="#dff7ea")
    arrow(d, 48 * mm, 78 * mm, 58 * mm, 78 * mm)
    arrow(d, 104 * mm, 78 * mm, 114 * mm, 78 * mm)
    arrow(d, 138 * mm, 70 * mm, 138 * mm, 50 * mm)
    arrow(d, 60 * mm, 70 * mm, 60 * mm, 50 * mm)
    arrow(d, 84 * mm, 34 * mm, 84 * mm, 20 * mm)
    arrow(d, 122 * mm, 34 * mm, 98 * mm, 12 * mm)
    return d


def build_story() -> list:
    register_fonts()
    style = styles()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    story = []
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph("เอกสารอธิบายโครงสร้างและการทำงานของระบบ Narit Vending Machine", style["TitleThai"]))
    story.append(Paragraph("เอกสารนี้สรุปภาพรวมของโค้ด, โครงสร้างไฟล์, วิธีไหลของคำสั่งจากหน้าเว็บไปยังมอเตอร์, และ flowchart สำคัญสำหรับใช้ทำความเข้าใจหรือส่งต่อทีมพัฒนา", style["BodyThai"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("1. ภาพรวมระบบ", style["HeadingThai"]))
    story.append(Paragraph("ระบบนี้ทำงานบน Raspberry Pi โดยให้ Pi เป็น web server สำหรับควบคุมเครื่องจ่ายสินค้า ผู้ใช้เปิดหน้าเว็บผ่านชื่อเครื่อง NaritVendingMachine แล้วสั่ง Home, Jog, Go To Slot, Save Slot และ Stop ได้จาก browser โดยข้อมูลตำแหน่งและสถานะของแกน X/Y/Z จะอัปเดตแบบ realtime ผ่าน API ภายในระบบเดียวกัน", style["BodyThai"]))
    story.append(Paragraph("โค้ดแบ่งออกเป็น 3 ชั้นหลัก คือ ชั้น motion control, ชั้น command/API, และชั้น web UI ซึ่งแยกความรับผิดชอบค่อนข้างชัดเจน ทำให้จูนเครื่องจริงหรือขยายฟังก์ชันในอนาคตได้ง่าย", style["BodyThai"]))

    story.append(Paragraph("2. โครงสร้างไฟล์สำคัญ", style["HeadingThai"]))
    files = [
        ("main.py", "จุดเริ่มต้นสำหรับ CLI โดยเรียกไปที่ narit_vending.cli.main"),
        ("narit_vending/motion.py", "แกนหลักของระบบ ควบคุม X/Y/Z, home, move, limit, stop, slot config"),
        ("narit_vending/webapp.py", "Flask web server และ REST API สำหรับหน้าเว็บ"),
        ("narit_vending/templates/index.html", "โครงสร้างหน้าเว็บควบคุม"),
        ("narit_vending/static/app.js", "logic ฝั่ง browser สำหรับเรียก API และอัปเดต realtime"),
        ("narit_vending/static/style.css", "รูปแบบหน้าจอ theme blue dark"),
        ("machine_config.json", "ค่าตั้งของแกนและตำแหน่ง slot 1-30"),
        ("deploy/narit-vending-web.service", "service ของ systemd สำหรับ auto-start หลังบูต"),
        ("scripts/setup_pi.sh", "สคริปต์ติดตั้ง dependency, ตั้ง hostname และเปิด service"),
        ("scripts/deploy_to_pi.ps1", "สคริปต์ deploy จาก Windows ไปยัง Raspberry Pi ผ่าน SSH"),
    ]
    file_rows = [["ไฟล์", "หน้าที่"]]
    file_rows.extend(files)
    file_table = Table(file_rows, colWidths=[62 * mm, 113 * mm])
    file_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163e6c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT_NAME),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9eb6d2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f9fe")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(file_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("3. ค่าคอนฟิกเครื่อง", style["HeadingThai"]))
    story.append(Paragraph("machine_config.json เก็บรายละเอียดของพิน, จำนวน steps ต่อมิลลิเมตร, ระยะวิ่งสูงสุดของแต่ละแกน, ลำดับการ home และตำแหน่งของ slot 1-30 ซึ่งหน้าเว็บจะอ่านและบันทึกค่าจากไฟล์นี้โดยตรง", style["BodyThai"]))
    story.append(axis_table(config))
    story.append(Spacer(1, 4 * mm))
    story.append(slot_summary_table(config))

    story.append(PageBreak())
    story.append(Paragraph("4. การทำงานของชั้น Motion Control", style["HeadingThai"]))
    story.append(Paragraph("ใน motion.py มี dataclass สำคัญ 3 ตัว ได้แก่ AxisConfig สำหรับเก็บค่าของแกน, SlotPosition สำหรับเก็บตำแหน่งสินค้า, และ MachineConfig สำหรับรวมค่าทั้งเครื่อง จากนั้น AxisController จะเป็นผู้ปล่อย pulse, คุมทิศทาง, อ่าน limit switch และอัปเดต position_steps / position_mm ของแกนเดียว", style["BodyThai"]))
    story.append(Paragraph("MotionController เป็นชั้นรวมที่ใช้เรียกแกนทั้งสามตัวพร้อมกัน มีหน้าที่ Home รายแกน, Home ทั้งเครื่อง, Jog/Move แบบมิลลิเมตร, Go To Slot, Save Slot และ Stop Request เมื่อผู้ใช้กดปุ่ม STOP จากหน้าเว็บ", style["BodyThai"]))
    story.append(Paragraph("เงื่อนไขความปลอดภัยในชั้นนี้ได้แก่ การตรวจ E-stop, การตรวจ stop_requested, การเช็ก limit min/max ก่อนและระหว่างขยับ, และ software travel limit จากค่า max_travel_mm หลังจากแกนถูก home แล้ว", style["BodyThai"]))
    story.append(Paragraph("5. การทำงานของชั้น Web/API", style["HeadingThai"]))
    story.append(Paragraph("webapp.py สร้าง Flask application และใช้ MotionService เป็นตัวคุมการเรียกคำสั่ง เพื่อรวม business logic เช่น สถานะ busy, การจดจำ error ล่าสุด, การ save config กลับลงไฟล์ และการ expose API ให้ browser เรียกใช้งาน", style["BodyThai"]))
    story.append(Paragraph("app.js ใน browser จะ poll /api/status ทุก 500 ms เพื่ออัปเดตค่าตำแหน่ง X/Y/Z, สถานะ homed, limit switch, E-stop, รายการ slot และข้อความ error ล่าสุด ทำให้ผู้ใช้เห็นผลตอบสนองของเครื่องแบบเกือบ realtime", style["BodyThai"]))
    story.append(Paragraph("6. Flowchart ภาพรวมคำสั่งจากหน้าเว็บ", style["HeadingThai"]))
    story.append(flowchart_web())
    story.append(Paragraph("คำอธิบาย: ผู้ใช้กดปุ่มบนหน้าเว็บ -> Flask รับคำสั่ง -> MotionService จัดการธุรกิจและสถานะ -> MotionController ส่งคำสั่งลงแต่ละแกน -> ระบบอ่านหรือเขียน machine_config.json เมื่อเกี่ยวข้องกับ slot", style["SmallThai"]))

    story.append(PageBreak())
    story.append(Paragraph("7. Flowchart การ Home แกน", style["HeadingThai"]))
    story.append(flowchart_home())
    story.append(Paragraph("คำอธิบาย: เมื่อกด Home ระบบจะหมุนไปทาง min limit ของแกนนั้น ปล่อย pulse ทีละ step จนชนสวิตช์ แล้วถอยออกเล็กน้อยเพื่อ release สวิตช์ จากนั้นตั้งตำแหน่งแกนเป็น 0 mm และทำเครื่องหมายว่าแกนนี้ถูก home แล้ว", style["SmallThai"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("8. Flowchart การไปยัง Slot", style["HeadingThai"]))
    story.append(flowchart_slot())
    story.append(Paragraph("คำอธิบาย: การไปยัง slot จะอ่านค่าตำแหน่ง X/Y/Z จาก config ก่อน ถ้าแกน Z อยู่ต่ำกว่า safe_z ระบบจะยก Z ขึ้นเพื่อหลบการชน จากนั้นจึงวิ่ง X/Y ไปตำแหน่งเป้าหมาย แล้วค่อยเลื่อน Z ลงไปยังตำแหน่ง slot สุดท้ายส่งสถานะใหม่กลับหน้าเว็บ", style["SmallThai"]))

    story.append(Paragraph("9. ลำดับการเริ่มระบบเมื่อเปิดเครื่อง", style["HeadingThai"]))
    startup_rows = [
        ["ลำดับ", "รายละเอียด"],
        ["1", "Raspberry Pi บูตขึ้นและ systemd เรียก service narit-vending-web.service"],
        ["2", "service สั่ง Python ใน virtual environment ให้รัน narit_vending.webapp"],
        ["3", "Flask โหลด machine_config.json และสร้าง MotionController"],
        ["4", "ผู้ใช้เปิด URL NaritVendingMachine.local แล้วเข้าหน้าเว็บได้ทันที"],
        ["5", "เมื่อกดปุ่มต่าง ๆ browser จะยิง API ไปยัง Flask และอัปเดตสถานะกลับมา"],
    ]
    startup_table = Table(startup_rows, colWidths=[18 * mm, 157 * mm])
    startup_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163e6c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT_NAME),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9eb6d2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f9fe")]),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(startup_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("10. ข้อสังเกตในการดูแลต่อ", style["HeadingThai"]))
    story.append(Paragraph("หากทีมจะขยายระบบต่อ ควรแยกส่วน long-running motion ไปทำงานใน worker thread หรือ queue ที่อนุญาตให้คำสั่ง STOP แทรกได้ง่ายขึ้น, เพิ่ม logging ของทุก motion command, และจัดเก็บ profile ของสินค้าแต่ละ slot เช่น เวลา dispense หรือ sequence พิเศษในไฟล์ config เพิ่มเติม", style["BodyThai"]))
    story.append(Paragraph("เอกสารนี้จัดทำจากโค้ดใน workspace ปัจจุบัน เพื่อใช้เป็นเอกสารอธิบายระบบสำหรับพัฒนา ทดสอบ และส่งมอบงาน", style["BodyThai"]))
    return story


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=34 * mm,
        bottomMargin=18 * mm,
        title="Narit Vending Architecture",
        author="OpenAI Codex",
    )
    doc.build(build_story(), onFirstPage=page_frame, onLaterPages=page_frame)
    print(OUTPUT)


if __name__ == "__main__":
    main()
