import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

# Load existing workbook to preserve all existing user data!
excel_path = "Composite_Sheet_Calculator.xlsx"
wb = openpyxl.load_workbook(excel_path)

sheet_name = "เช็ค Drawing (Check Drawing)"
if sheet_name in wb.sheetnames:
    del wb[sheet_name]

# Insert after summary (index 1)
ws = wb.create_sheet(title=sheet_name, index=1)
ws.views.sheetView[0].showGridLines = True

# Palettes
NAVY = "1B365D"
STEEL_BLUE = "2E5B88"
HEADER_BG = "243342"
LIGHT_BLUE = "E8F1F5"
BORDER_GRAY = "BDC3C7"
BORDER_DARK = "34495E"
SUCCESS_GREEN = "D4EFDF"
WARNING_YELLOW = "FCF3CF"
DANGER_RED = "FADBD8"
INPUT_YELLOW = "FEF9E7"
SUMMARY_BG = "F8F9FA"

font_title = Font(name="Segoe UI", size=15, bold=True, color="1B365D")
font_subtitle = Font(name="Segoe UI", size=10, italic=True, color="5D6D7E")
font_section = Font(name="Segoe UI", size=11, bold=True, color="1B365D")
font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
font_regular = Font(name="Segoe UI", size=10)
font_bold = Font(name="Segoe UI", size=10, bold=True)
font_kpi_num = Font(name="Segoe UI", size=18, bold=True, color="1B365D")
font_kpi_green = Font(name="Segoe UI", size=18, bold=True, color="1E8449")
font_kpi_orange = Font(name="Segoe UI", size=18, bold=True, color="B9770E")

thin_side = Side(border_style="thin", color=BORDER_GRAY)
medium_side = Side(border_style="medium", color=BORDER_DARK)
double_bottom = Side(border_style="double", color=BORDER_DARK)

cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
header_border = Border(left=thin_side, right=thin_side, top=medium_side, bottom=medium_side)
card_border = Border(left=medium_side, right=medium_side, top=medium_side, bottom=medium_side)
total_border = Border(top=thin_side, bottom=double_bottom, left=thin_side, right=thin_side)

align_center = Alignment(horizontal="center", vertical="center")
align_left = Alignment(horizontal="left", vertical="center")
align_right = Alignment(horizontal="right", vertical="center")
align_wrap = Alignment(horizontal="center", vertical="center", wrap_text=True)

fill_hdr = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid")
fill_inner_grp = PatternFill(start_color="D4E6F1", end_color="D4E6F1", fill_type="solid")
fill_outer_grp = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
fill_acrylic_grp = PatternFill(start_color="D1F2EB", end_color="D1F2EB", fill_type="solid")
fill_done = PatternFill(start_color="D4EFDF", end_color="D4EFDF", fill_type="solid")
fill_pending = PatternFill(start_color="FCF3CF", end_color="FCF3CF", fill_type="solid")
fill_input = PatternFill(start_color=INPUT_YELLOW, end_color=INPUT_YELLOW, fill_type="solid")

# 1. Title Block
ws.merge_cells("A1:L1")
ws["A1"] = "📋 รายการตรวจสอบสถานะการทำ 2D Drawing ชิ้นงาน (Drawing Progress Checklist)"
ws["A1"].font = font_title
ws["A1"].alignment = align_left
ws.row_dimensions[1].height = 26

ws.merge_cells("A2:L2")
ws["A2"] = "โครงการ: Narit Vending Machine | ตรวจสอบความครบถ้วนของแบบสั่งผลิต (2D Drawing), แผ่นคลี่ตัด (Flatten / DXF), และเลขที่แบบ (DWG No.)"
ws["A2"].font = font_subtitle
ws["A2"].alignment = align_left
ws.row_dimensions[2].height = 18

# 2. Top Summary KPI Cards (Rows 4 - 7)
# Card 1: Total Parts
ws.merge_cells("B4:C4")
ws["B4"] = "จำนวนชิ้นงานทั้งหมด\n(Total Parts)"
ws["B4"].font = Font(name="Segoe UI", size=9, bold=True, color="1B365D")
ws["B4"].alignment = align_wrap
ws["B4"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")

ws.merge_cells("B5:C7")
ws["B5"] = '=COUNTA(C11:C31)'
ws["B5"].font = font_kpi_num
ws["B5"].alignment = align_center
ws["B5"].fill = PatternFill(start_color=SUMMARY_BG, end_color=SUMMARY_BG, fill_type="solid")
ws["B5"].number_format = '0 " ชิ้น"'

for r in range(4, 8):
    for c in ["B", "C"]:
        ws[f"{c}{r}"].border = card_border

# Card 2: Drawing Completed
ws.merge_cells("E4:F4")
ws["E4"] = "Drawing เสร็จแล้ว ✅\n(Completed)"
ws["E4"].font = Font(name="Segoe UI", size=9, bold=True, color="1E8449")
ws["E4"].alignment = align_wrap
ws["E4"].fill = PatternFill(start_color=SUCCESS_GREEN, end_color=SUCCESS_GREEN, fill_type="solid")

ws.merge_cells("E5:F7")
ws["E5"] = '=COUNTIF(H11:H31, "เสร็จแล้ว")'
ws["E5"].font = font_kpi_green
ws["E5"].alignment = align_center
ws["E5"].fill = PatternFill(start_color=SUCCESS_GREEN, end_color=SUCCESS_GREEN, fill_type="solid")
ws["E5"].number_format = '0 " ชิ้น"'

for r in range(4, 8):
    for c in ["E", "F"]:
        ws[f"{c}{r}"].border = card_border

# Card 3: Pending / In Progress
ws.merge_cells("H4:I4")
ws["H4"] = "ยังไม่ได้ทำ / กำลังทำ ⏳\n(Pending / In Progress)"
ws["H4"].font = Font(name="Segoe UI", size=9, bold=True, color="B9770E")
ws["H4"].alignment = align_wrap
ws["H4"].fill = PatternFill(start_color=WARNING_YELLOW, end_color=WARNING_YELLOW, fill_type="solid")

ws.merge_cells("H5:I7")
ws["H5"] = '=B5-E5'
ws["H5"].font = font_kpi_orange
ws["H5"].alignment = align_center
ws["H5"].fill = PatternFill(start_color=WARNING_YELLOW, end_color=WARNING_YELLOW, fill_type="solid")
ws["H5"].number_format = '0 " ชิ้น"'

for r in range(4, 8):
    for c in ["H", "I"]:
        ws[f"{c}{r}"].border = card_border

# Card 4: Overall Progress %
ws.merge_cells("K4:L4")
ws["K4"] = "ความคืบหน้ารวม 📊\n(Overall Progress)"
ws["K4"].font = Font(name="Segoe UI", size=9, bold=True, color="1B365D")
ws["K4"].alignment = align_wrap
ws["K4"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")

ws.merge_cells("K5:L7")
ws["K5"] = '=IF(B5>0, E5/B5, 0)'
ws["K5"].font = font_kpi_green
ws["K5"].alignment = align_center
ws["K5"].fill = PatternFill(start_color=SUMMARY_BG, end_color=SUMMARY_BG, fill_type="solid")
ws["K5"].number_format = '0.0%'

for r in range(4, 8):
    for c in ["K", "L"]:
        ws[f"{c}{r}"].border = card_border

# 3. Table Headers (Row 10)
headers = [
    ("A10", "ลำดับ\nNo.", 6),
    ("B10", "หมวดหมู่วัสดุ / ส่วนงาน\nSection / Group", 22),
    ("C10", "รหัส / ชื่อชิ้นงาน (SOLIDWORKS)\nPart Name", 30),
    ("D10", "ลักษณะชิ้นงาน / ตำแหน่ง\nDescription", 28),
    ("E10", "จำนวน\nQty", 8),
    ("F10", "กว้างคลี่ (W)\n(mm)", 12),
    ("G10", "ยาวคลี่ (L)\n(mm)", 12),
    ("H10", "สถานะ Drawing 2D\n(Drawing Status)", 18),
    ("I10", "แบบคลี่ตัด (Flatten / DXF)\n(Sheet Metal Blank)", 22),
    ("J10", "รหัสแบบ Drawing No.\n(Document / DWG No.)", 24),
    ("K10", "วันที่เสร็จ / อัปเดต\nDate", 14),
    ("L10", "หมายเหตุ / ตำแหน่งจัดเก็บไฟล์\nRemarks & File Path", 32),
]

ws.row_dimensions[10].height = 32
for cell_id, title_h, _ in headers:
    cell = ws[cell_id]
    cell.value = title_h
    cell.font = font_header
    cell.fill = fill_hdr
    cell.alignment = align_wrap
    cell.border = header_border

# Checklist Items
# Group 1: Inner Parts (9 items, rows 11 - 19)
# Note: we link Qty, W, L directly to the 'ฝั่งใน (Inner)' sheet!
inner_items = [
    (11, "ฝั่งใน (Inner)", "Partition-Inner 3-st", "แผ่นกั้นภายในตู้ 3", "='ฝั่งใน (Inner)'!D12", "='ฝั่งใน (Inner)'!E12", "='ฝั่งใน (Inner)'!F12", "ยังไม่ทำ", "ยังไม่มี", "", "", "แผ่นกั้นตรง มีเจาะรูยึด"),
    (12, "ฝั่งใน (Inner)", "Partition-Inner 1-st", "แผ่นกั้นภายในตู้ 1", "='ฝั่งใน (Inner)'!D13", "='ฝั่งใน (Inner)'!E13", "='ฝั่งใน (Inner)'!F13", "ยังไม่ทำ", "ยังไม่มี", "", "", "แผ่นกั้นตรง"),
    (13, "ฝั่งใน (Inner)", "Partition-Inner-Box-1-st", "กล่อง/โครงกั้นภายใน 1", "='ฝั่งใน (Inner)'!D14", "='ฝั่งใน (Inner)'!E14", "='ฝั่งใน (Inner)'!F14", "ยังไม่ทำ", "ยังไม่มี", "", "", "พับขึ้นรูปกล่อง เช็ค Blank Size"),
    (14, "ฝั่งใน (Inner)", "Partition-Inner 2-st", "แผ่นกั้นภายในตู้ 2", "='ฝั่งใน (Inner)'!D15", "='ฝั่งใน (Inner)'!E15", "='ฝั่งใน (Inner)'!F15", "ยังไม่ทำ", "ยังไม่มี", "", "", "แผ่นกั้นตรง"),
    (15, "ฝั่งใน (Inner)", "Door Right-Inner 1-Bending-st", "ฝาในประตูขวา พับ 1 (ซับใน)", "='ฝั่งใน (Inner)'!D16", "='ฝั่งใน (Inner)'!E16", "='ฝั่งใน (Inner)'!F16", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (16, "ฝั่งใน (Inner)", "Cover Back 2-Inner-Bending-st", "ฝาครอบหลังใน 2 พับ", "='ฝั่งใน (Inner)'!D17", "='ฝั่งใน (Inner)'!E17", "='ฝั่งใน (Inner)'!F17", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (17, "ฝั่งใน (Inner)", "Cover Back 1-Inner-Bending-st", "ฝาครอบหลังใน 1 พับ", "='ฝั่งใน (Inner)'!D18", "='ฝั่งใน (Inner)'!E18", "='ฝั่งใน (Inner)'!F18", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (18, "ฝั่งใน (Inner)", "Door left-inner-Bending-st", "ฝาในประตูซ้าย พับ (ซับใน)", "='ฝั่งใน (Inner)'!D19", "='ฝั่งใน (Inner)'!E19", "='ฝั่งใน (Inner)'!F19", "เสร็จแล้ว", "มีแล้ว", "Door left-inner-Bending-st.SLDDRW", "28-Sep-2026", "พบไฟล์ .SLDDRW และ .pdf ใน Model"),
    (19, "ฝั่งใน (Inner)", "Door left-inner-Bending", "ฝาในประตูซ้าย พับ", 1, 512, 1750, "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
]

# Group 2: Outer Parts (9 items, rows 20 - 28)
# Linked to 'ฝั่งนอก (Outer)' sheet
outer_items = [
    (20, "ฝั่งนอก (Outer)", "Cover top-Bending-st-2psc", "ฝาครอบบน (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D12", "='ฝั่งนอก (Outer)'!E12", "='ฝั่งนอก (Outer)'!F12", "ยังไม่ทำ", "ยังไม่มี", "", "", "มี 2 ชิ้น (2psc) / พับขอบ"),
    (21, "ฝั่งนอก (Outer)", "Cover Back 1-Bending-st-2psc", "ฝาครอบหลัง 1 (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D13", "='ฝั่งนอก (Outer)'!E13", "='ฝั่งนอก (Outer)'!F13", "ยังไม่ทำ", "ยังไม่มี", "", "", "มี 2 ชิ้น (2psc) / พับขอบ"),
    (22, "ฝั่งนอก (Outer)", "Door left-Bending-st", "ฝาประตูซ้ายนอก (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D14", "='ฝั่งนอก (Outer)'!E14", "='ฝั่งนอก (Outer)'!F14", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (23, "ฝั่งนอก (Outer)", "Cover Left Side-Bending-st", "ฝาครอบข้างซ้าย (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D15", "='ฝั่งนอก (Outer)'!E15", "='ฝั่งนอก (Outer)'!F15", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (24, "ฝั่งนอก (Outer)", "Cover Left Side 2-Bending-st", "ฝาครอบข้างซ้าย 2 (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D16", "='ฝั่งนอก (Outer)'!E16", "='ฝั่งนอก (Outer)'!F16", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (25, "ฝั่งนอก (Outer)", "Cover Front 1-Bending-st", "ฝาครอบหน้า 1 (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D17", "='ฝั่งนอก (Outer)'!E17", "='ฝั่งนอก (Outer)'!F17", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (26, "ฝั่งนอก (Outer)", "Cover Front 2-Bending-st", "ฝาครอบหน้า 2 (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D18", "='ฝั่งนอก (Outer)'!E18", "='ฝั่งนอก (Outer)'!F18", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (27, "ฝั่งนอก (Outer)", "Cover Right Side 1-Bending-st", "ฝาครอบข้างขวา 1 (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D19", "='ฝั่งนอก (Outer)'!E19", "='ฝั่งนอก (Outer)'!F19", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
    (28, "ฝั่งนอก (Outer)", "Cover Right Side 2-Bending-st", "ฝาครอบข้างขวา 2 (พับขึ้นรูป)", "='ฝั่งนอก (Outer)'!D20", "='ฝั่งนอก (Outer)'!E20", "='ฝั่งนอก (Outer)'!F20", "ยังไม่ทำ", "ยังไม่มี", "", "", "ชิ้นงานพับขอบ Bending"),
]

# Group 3: Acrylic Parts (3 items, rows 29 - 31)
# Linked to 'อะคริลิก (Acrylic)' sheet
acrylic_items = [
    (29, "อะคริลิก (Acrylic)", "Arcylic Cover Front 2-st", "ฝาครอบหน้า 2 (อะคริลิกใส/ป้ายไฟ)", "='อะคริลิก (Acrylic)'!D12", "='อะคริลิก (Acrylic)'!E12", "='อะคริลิก (Acrylic)'!F12", "ยังไม่ทำ", "ยังไม่มี", "", "", "ตัดเลเซอร์ Laser Cut / ขัดขอบ"),
    (30, "อะคริลิก (Acrylic)", "Arcylic Cover Front-st", "ฝาครอบหน้า (อะคริลิกใส/ช่องมอง)", "='อะคริลิก (Acrylic)'!D13", "='อะคริลิก (Acrylic)'!E13", "='อะคริลิก (Acrylic)'!F13", "ยังไม่ทำ", "ยังไม่มี", "", "", "ตัดเลเซอร์ Laser Cut / ขัดขอบ"),
    (31, "อะคริลิก (Acrylic)", "Arcylic Cover Right -side-st", "ฝาครอบข้างขวา (อะคริลิกใส/แสดงผล)", "='อะคริลิก (Acrylic)'!D14", "='อะคริลิก (Acrylic)'!E14", "='อะคริลิก (Acrylic)'!F14", "เสร็จแล้ว", "มีแล้ว", "NAR2093-0413A", "28-Sep-2026", "พบไฟล์ Flatten.pdf ใน Drawing"),
]

all_items = inner_items + outer_items + acrylic_items

# Data Validation for Status: เสร็จแล้ว, กำลังทำ, ยังไม่ทำ, รอเช็คขนาด
dv_status = DataValidation(type="list", formula1='"เสร็จแล้ว,กำลังทำ,ยังไม่ทำ,รอเช็คขนาด"', allow_blank=True)
dv_status.error = "กรุณาเลือกสถานะจากรายการที่กำหนด"
dv_status.errorTitle = "สถานะไม่ถูกต้อง"
dv_status.prompt = "เลือกสถานะการทำ Drawing"
dv_status.promptTitle = "Drawing Status"
ws.add_data_validation(dv_status)

# Data Validation for Flatten: มีแล้ว, ยังไม่มี, ไม่ต้องมี
dv_flatten = DataValidation(type="list", formula1='"มีแล้ว,ยังไม่มี,ไม่ต้องมี"', allow_blank=True)
ws.add_data_validation(dv_flatten)

for idx, (row, grp, p_name, desc, f_qty, f_w, f_l, status, flatten, dwg_no, dt, remark) in enumerate(all_items, 1):
    ws.row_dimensions[row].height = 22
    
    ws[f"A{row}"] = idx
    ws[f"A{row}"].alignment = align_center
    ws[f"A{row}"].font = font_regular
    ws[f"A{row}"].border = cell_border
    
    ws[f"B{row}"] = grp
    ws[f"B{row}"].alignment = align_center
    ws[f"B{row}"].font = font_bold
    ws[f"B{row}"].border = cell_border
    if "Inner" in grp:
        ws[f"B{row}"].fill = fill_inner_grp
    elif "Outer" in grp:
        ws[f"B{row}"].fill = fill_outer_grp
    else:
        ws[f"B{row}"].fill = fill_acrylic_grp
        
    ws[f"C{row}"] = p_name
    ws[f"C{row}"].alignment = align_left
    ws[f"C{row}"].font = font_bold
    ws[f"C{row}"].border = cell_border
    
    ws[f"D{row}"] = desc
    ws[f"D{row}"].alignment = align_left
    ws[f"D{row}"].font = font_regular
    ws[f"D{row}"].border = cell_border
    
    ws[f"E{row}"] = f_qty
    ws[f"E{row}"].alignment = align_center
    ws[f"E{row}"].font = font_bold
    ws[f"E{row}"].border = cell_border
    ws[f"E{row}"].number_format = "#,##0"
    
    ws[f"F{row}"] = f_w
    ws[f"F{row}"].alignment = align_right
    ws[f"F{row}"].font = font_regular
    ws[f"F{row}"].border = cell_border
    ws[f"F{row}"].number_format = "#,##0"
    
    ws[f"G{row}"] = f_l
    ws[f"G{row}"].alignment = align_right
    ws[f"G{row}"].font = font_regular
    ws[f"G{row}"].border = cell_border
    ws[f"G{row}"].number_format = "#,##0"
    
    # Status
    ws[f"H{row}"] = status
    ws[f"H{row}"].alignment = align_center
    ws[f"H{row}"].font = font_bold
    ws[f"H{row}"].border = cell_border
    if status == "เสร็จแล้ว":
        ws[f"H{row}"].fill = fill_done
    else:
        ws[f"H{row}"].fill = fill_pending
    dv_status.add(ws[f"H{row}"])
    
    # Flatten
    ws[f"I{row}"] = flatten
    ws[f"I{row}"].alignment = align_center
    ws[f"I{row}"].font = font_regular
    ws[f"I{row}"].border = cell_border
    dv_flatten.add(ws[f"I{row}"])
    
    # DWG No
    ws[f"J{row}"] = dwg_no
    ws[f"J{row}"].alignment = align_left
    ws[f"J{row}"].font = font_regular
    ws[f"J{row}"].fill = fill_input
    ws[f"J{row}"].border = cell_border
    
    # Date
    ws[f"K{row}"] = dt
    ws[f"K{row}"].alignment = align_center
    ws[f"K{row}"].font = font_subtitle
    ws[f"K{row}"].fill = fill_input
    ws[f"K{row}"].border = cell_border
    
    # Remark
    ws[f"L{row}"] = remark
    ws[f"L{row}"].alignment = align_left
    ws[f"L{row}"].font = font_subtitle
    ws[f"L{row}"].fill = fill_input
    ws[f"L{row}"].border = cell_border

# Instructions / Legend (Rows 33 - 38)
ws.merge_cells("A33:L33")
ws["A33"] = "💡 คำแนะนำในการใช้งานตารางเช็ค Drawing (Drawing Checklist Instructions)"
ws["A33"].font = font_section

notes = [
    "1. คอลัมน์ 'สถานะ Drawing 2D' (H) สามารถคลิกเลือกจาก Dropdown ได้: 'เสร็จแล้ว', 'กำลังทำ', 'ยังไม่ทำ', 'รอเช็คขนาด'",
    "2. คอลัมน์ 'แบบคลี่ตัด (Flatten / DXF)' (I) ใช้เช็คว่ามีการ Export แบบคลี่ Blank Size สำหรับส่งเครื่องตัด CNC Laser/Router แล้วหรือยัง",
    "3. ขนาดกว้างคลี่ (W) และยาวคลี่ (L) ลิงก์ตรงกับแท็บ 'ฝั่งใน', 'ฝั่งนอก', และ 'อะคริลิก' อัตโนมัติ (แก้ไขที่แท็บต้นทางแล้วค่าจะเปลี่ยนตาม)",
    "4. การ์ดสรุป KPI ด้านบนจะคำนวณจำนวนชิ้นงานที่ทำเสร็จแล้ว และเปอร์เซ็นต์ความคืบหน้า (Overall Progress %) ให้แบบ Real-time",
    "5. ชิ้นส่วนที่ตรวจพบไฟล์แบบในเครื่องแล้ว: 'Door left-inner-Bending-st' (.SLDDRW) และ 'Arcylic Cover Right -side-st' (NAR2093-0413A) ถูกตั้งค่าเริ่มต้นเป็น 'เสร็จแล้ว'"
]

for idx, n in enumerate(notes, 34):
    ws.merge_cells(f"A{idx}:L{idx}")
    ws[f"A{idx}"] = n
    ws[f"A{idx}"].font = font_regular
    ws[f"A{idx}"].alignment = align_left

# Set Col widths
col_w = {
    "A": 7,
    "B": 20,
    "C": 32,
    "D": 30,
    "E": 10,
    "F": 14,
    "G": 14,
    "H": 20,
    "I": 24,
    "J": 26,
    "K": 16,
    "L": 35
}
for col, w in col_w.items():
    ws.column_dimensions[col].width = w

wb.save(excel_path)
print("Successfully added Check Drawing tab without losing any user data!")
