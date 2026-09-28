import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

# Sheet 1: Main Calculator
ws = wb.active
ws.title = "คำนวณแผ่นคอมโพสิต"
ws.views.sheetView[0].showGridLines = True

# Palettes
NAVY = "1B365D"
STEEL_BLUE = "2E5B88"
LIGHT_BLUE = "E8F1F5"
HEADER_BG = "2C3E50"
INPUT_YELLOW = "FEF9E7"
ACCENT_GREEN = "1E8449"
LIGHT_GREEN = "E8F8F5"
SUMMARY_BG = "F4F6F6"
BORDER_GRAY = "BDC3C7"
BORDER_DARK = "34495E"

font_title = Font(name="Segoe UI", size=16, bold=True, color="1B365D")
font_subtitle = Font(name="Segoe UI", size=10, italic=True, color="5D6D7E")
font_section = Font(name="Segoe UI", size=12, bold=True, color="1B365D")
font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
font_regular = Font(name="Segoe UI", size=10)
font_bold = Font(name="Segoe UI", size=10, bold=True)
font_highlight_big = Font(name="Segoe UI", size=20, bold=True, color="1E8449")
font_summary_label = Font(name="Segoe UI", size=10, bold=True, color="2C3E50")

fill_header = PatternFill(start_color=STEEL_BLUE, end_color=STEEL_BLUE, fill_type="solid")
fill_sub_header = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
fill_input = PatternFill(start_color=INPUT_YELLOW, end_color=INPUT_YELLOW, fill_type="solid")
fill_summary = PatternFill(start_color=SUMMARY_BG, end_color=SUMMARY_BG, fill_type="solid")
fill_result_box = PatternFill(start_color=LIGHT_GREEN, end_color=LIGHT_GREEN, fill_type="solid")

thin_side = Side(border_style="thin", color=BORDER_GRAY)
medium_side = Side(border_style="medium", color=BORDER_DARK)
double_bottom = Side(border_style="double", color=BORDER_DARK)

cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
header_border = Border(left=thin_side, right=thin_side, top=medium_side, bottom=medium_side)
total_border = Border(top=thin_side, bottom=double_bottom, left=thin_side, right=thin_side)
result_card_border = Border(left=medium_side, right=medium_side, top=medium_side, bottom=medium_side)

align_center = Alignment(horizontal="center", vertical="center")
align_left = Alignment(horizontal="left", vertical="center")
align_right = Alignment(horizontal="right", vertical="center")
align_wrap = Alignment(horizontal="center", vertical="center", wrap_text=True)

# Title block
ws.merge_cells("A1:J1")
ws["A1"] = "ตารางคำนวณจำนวนแผ่นอลูมิเนียมคอมโพสิต (Composite Sheet Requirement Calculator)"
ws["A1"].font = font_title
ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
ws.row_dimensions[1].height = 28

ws.merge_cells("A2:J2")
ws["A2"] = "โครงการ: Narit Vending Machine | กำหนดขนาดคลี่ (Blank Size) เพื่อคำนวณพื้นที่และจำนวนแผ่นมาตรฐาน"
ws["A2"].font = font_subtitle
ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
ws.row_dimensions[2].height = 18

# Configuration & Summary Cards (Rows 4 - 8)
# Left Box: Sheet Specification (ตั้งค่าขนาดแผ่นมาตรฐาน)
ws.merge_cells("B4:D4")
ws["B4"] = "⚙️ ข้อมูลแผ่นมาตรฐาน (Standard Sheet Config)"
ws["B4"].font = font_section
ws["B4"].alignment = align_left

sheet_configs = [
    (5, "ความกว้างแผ่นมาตรฐาน (Sheet Width)", 1220, " มม. (mm)", True),
    (6, "ความยาวแผ่นมาตรฐาน (Sheet Length)", 2440, " มม. (mm)", True),
    (7, "พื้นที่ต่อ 1 แผ่นมาตรฐาน (Area/Sheet)", "=(C5*C6)/1000000", " ตร.ม. (m²)", False),
    (8, "เผื่อเศษตัด/พับ/โครงสร้าง (Waste Factor)", 0.15, " (15%)", True),
]

for r_idx, label, val, unit, is_input in sheet_configs:
    ws[f"B{r_idx}"] = label
    ws[f"B{r_idx}"].font = font_regular
    ws[f"B{r_idx}"].alignment = align_left
    ws[f"B{r_idx}"].border = cell_border
    
    ws[f"C{r_idx}"] = val
    ws[f"C{r_idx}"].font = font_bold if not is_input else font_regular
    ws[f"C{r_idx}"].alignment = align_right
    ws[f"C{r_idx}"].border = cell_border
    if is_input:
        ws[f"C{r_idx}"].fill = fill_input
        if isinstance(val, float):
            ws[f"C{r_idx}"].number_format = "0.0%"
        else:
            ws[f"C{r_idx}"].number_format = "#,##0"
    else:
        ws[f"C{r_idx}"].number_format = "0.0000"
        
    ws[f"D{r_idx}"] = unit
    ws[f"D{r_idx}"].font = font_subtitle
    ws[f"D{r_idx}"].alignment = align_left
    ws[f"D{r_idx}"].border = cell_border

# Right Box: Summary of Calculation (สรุปผลการคำนวณ)
ws.merge_cells("F4:H4")
ws["F4"] = "📊 ผลลัพธ์การคำนวณ (Calculation Summary)"
ws["F4"].font = font_section
ws["F4"].alignment = align_left

summary_rows = [
    (5, "จำนวนชิ้นงานทั้งหมด (Total Quantity)", "=SUM(D12:D23)", "ชิ้น (pcs)"),
    (6, "พื้นที่ชิ้นงานสุทธิ (Net Total Area)", "=SUM(G12:G23)", "ตร.ม. (m²)"),
    (7, "พื้นที่รวมเผื่อเศษตัด (Gross Area with Waste)", "=G6*(1+C8)", "ตร.ม. (m²)"),
    (8, "จำนวนแผ่นตามทฤษฎี (Theoretical Sheets)", "=G7/C7", "แผ่น (sheets)"),
]

for r_idx, label, formula, unit in summary_rows:
    ws[f"F{r_idx}"] = label
    ws[f"F{r_idx}"].font = font_summary_label
    ws[f"F{r_idx}"].alignment = align_left
    ws[f"F{r_idx}"].border = cell_border
    
    ws[f"G{r_idx}"] = formula
    ws[f"G{r_idx}"].font = font_bold
    ws[f"G{r_idx}"].alignment = align_right
    ws[f"G{r_idx}"].border = cell_border
    if r_idx == 5:
        ws[f"G{r_idx}"].number_format = "#,##0"
    elif r_idx in [6, 7]:
        ws[f"G{r_idx}"].number_format = "#,##0.0000"
    elif r_idx == 8:
        ws[f"G{r_idx}"].number_format = "0.00"
        
    ws[f"H{r_idx}"] = unit
    ws[f"H{r_idx}"].font = font_subtitle
    ws[f"H{r_idx}"].alignment = align_left
    ws[f"H{r_idx}"].border = cell_border

# Grand Result Card (Recommended Sheets)
ws.merge_cells("I4:J5")
ws["I4"] = "จำนวนแผ่นที่แนะนำสั่งซื้อ\n(Recommended to Order)"
ws["I4"].font = Font(name="Segoe UI", size=10, bold=True, color="1B365D")
ws["I4"].alignment = align_wrap
ws["I4"].fill = fill_sub_header

ws.merge_cells("I6:J8")
ws["I6"] = "=ROUNDUP(G8, 0)"
ws["I6"].font = font_highlight_big
ws["I6"].alignment = align_center
ws["I6"].fill = fill_result_box
ws["I6"].number_format = '0 " แผ่น"'

for r in range(4, 9):
    for c in ["I", "J"]:
        ws[f"{c}{r}"].border = result_card_border

# Parts Table Headers (Row 11)
headers = [
    ("A11", "ลำดับ\nNo.", 6),
    ("B11", "รหัส / ชื่อชิ้นงาน\nPart Name", 30),
    ("C11", "ลักษณะชิ้นงาน / ตำแหน่ง\nDescription", 24),
    ("D11", "จำนวน\nQty (pcs)", 12),
    ("E11", "กว้างคลี่ (W)\nWidth (mm)", 15),
    ("F11", "ยาวคลี่ (L)\nLength (mm)", 15),
    ("G11", "พื้นที่รวม\nTotal Area (m²)", 16),
    ("H11", "สัดส่วนต่อแผ่น\n% of 1 Sheet", 15),
    ("I11", "หมายเหตุการตัด / พับ\nRemarks & Bending Note", 26),
]

ws.row_dimensions[11].height = 32

for cell_id, title, col_w in headers:
    cell = ws[cell_id]
    cell.value = title
    cell.font = font_header
    cell.fill = fill_header
    cell.alignment = align_wrap
    cell.border = header_border

# Default Parts List from user prompt
parts = [
    ("Partition-Inner 3-st", "แผ่นกั้นภายในตู้ 3 (สเตนเลส/โครงสร้าง)", 1, "", "", "แผ่นกั้นตรง / มีเจาะรูยึด"),
    ("Partition-Inner 1-st", "แผ่นกั้นภายในตู้ 1", 1, "", "", "แผ่นกั้นตรง"),
    ("Partition-Inner-Box-1-st", "กล่อง/โครงกั้นภายใน 1", 1, "", "", "มีพับขึ้นรูปกล่อง (เช็ค Blank Size)"),
    ("Partition-Inner 2-st", "แผ่นกั้นภายในตู้ 2", 1, "", "", "แผ่นกั้นตรง"),
    ("Door Right-Inner 1-Bending-st", "ฝาในประตูขวา พับ 1 (สเตนเลส/ซับใน)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Back 2-Inner-Bending-st", "ฝาครอบหลังใน 2 พับ", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Back 1-Inner-Bending-st", "ฝาครอบหลังใน 1 พับ", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Door left-inner-Bending-st", "ฝาในประตูซ้าย พับ (สเตนเลส/ซับใน)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Door left-inner-Bending", "ฝาในประตูซ้าย พับ", 1, "", "", "ชิ้นงานพับขอบ Bending"),
]

# Additional blank rows for flexibility
extra_rows = [
    ("", "สำรองชิ้นส่วนเพิ่มเติม (Extra Part 1)", 0, "", "", ""),
    ("", "สำรองชิ้นส่วนเพิ่มเติม (Extra Part 2)", 0, "", "", ""),
    ("", "สำรองชิ้นส่วนเพิ่มเติม (Extra Part 3)", 0, "", "", ""),
]

start_row = 12
for idx, (p_name, p_desc, qty, w, l, remark) in enumerate(parts, 1):
    row = start_row + idx - 1
    ws.row_dimensions[row].height = 22
    
    ws[f"A{row}"] = idx
    ws[f"A{row}"].alignment = align_center
    ws[f"A{row}"].font = font_regular
    ws[f"A{row}"].border = cell_border
    
    ws[f"B{row}"] = p_name
    ws[f"B{row}"].alignment = align_left
    ws[f"B{row}"].font = font_bold
    ws[f"B{row}"].border = cell_border
    
    ws[f"C{row}"] = p_desc
    ws[f"C{row}"].alignment = align_left
    ws[f"C{row}"].font = font_regular
    ws[f"C{row}"].border = cell_border
    
    ws[f"D{row}"] = qty
    ws[f"D{row}"].alignment = align_center
    ws[f"D{row}"].font = font_regular
    ws[f"D{row}"].fill = fill_input
    ws[f"D{row}"].border = cell_border
    ws[f"D{row}"].number_format = "#,##0"
    
    ws[f"E{row}"] = w
    ws[f"E{row}"].alignment = align_right
    ws[f"E{row}"].font = font_regular
    ws[f"E{row}"].fill = fill_input
    ws[f"E{row}"].border = cell_border
    ws[f"E{row}"].number_format = "#,##0"
    
    ws[f"F{row}"] = l
    ws[f"F{row}"].alignment = align_right
    ws[f"F{row}"].font = font_regular
    ws[f"F{row}"].fill = fill_input
    ws[f"F{row}"].border = cell_border
    ws[f"F{row}"].number_format = "#,##0"
    
    # Area Formula: Qty * (Width * Length) / 1,000,000 (m²)
    # Only calculate if Width and Length are provided
    ws[f"G{row}"] = f'=IF(AND(ISNUMBER(E{row}),ISNUMBER(F{row}),E{row}>0,F{row}>0), D{row}*(E{row}*F{row})/1000000, 0)'
    ws[f"G{row}"].alignment = align_right
    ws[f"G{row}"].font = font_bold
    ws[f"G{row}"].border = cell_border
    ws[f"G{row}"].number_format = "#,##0.0000"
    
    # Proportion of 1 Standard Sheet
    ws[f"H{row}"] = f'=IF($C$7>0, G{row}/$C$7, 0)'
    ws[f"H{row}"].alignment = align_right
    ws[f"H{row}"].font = font_regular
    ws[f"H{row}"].border = cell_border
    ws[f"H{row}"].number_format = "0.0%"
    
    ws[f"I{row}"] = remark
    ws[f"I{row}"].alignment = align_left
    ws[f"I{row}"].font = font_subtitle
    ws[f"I{row}"].border = cell_border

# Extra rows
for idx, (p_name, p_desc, qty, w, l, remark) in enumerate(extra_rows, len(parts) + 1):
    row = start_row + idx - 1
    ws.row_dimensions[row].height = 20
    ws[f"A{row}"] = idx
    ws[f"A{row}"].alignment = align_center
    ws[f"A{row}"].font = font_subtitle
    ws[f"A{row}"].border = cell_border
    
    ws[f"B{row}"] = p_name
    ws[f"B{row}"].alignment = align_left
    ws[f"B{row}"].font = font_subtitle
    ws[f"B{row}"].border = cell_border
    
    ws[f"C{row}"] = p_desc
    ws[f"C{row}"].alignment = align_left
    ws[f"C{row}"].font = font_subtitle
    ws[f"C{row}"].border = cell_border
    
    ws[f"D{row}"] = qty
    ws[f"D{row}"].alignment = align_center
    ws[f"D{row}"].font = font_regular
    ws[f"D{row}"].fill = fill_input
    ws[f"D{row}"].border = cell_border
    ws[f"D{row}"].number_format = "#,##0"
    
    ws[f"E{row}"] = w
    ws[f"E{row}"].alignment = align_right
    ws[f"E{row}"].font = font_regular
    ws[f"E{row}"].fill = fill_input
    ws[f"E{row}"].border = cell_border
    ws[f"E{row}"].number_format = "#,##0"
    
    ws[f"F{row}"] = l
    ws[f"F{row}"].alignment = align_right
    ws[f"F{row}"].font = font_regular
    ws[f"F{row}"].fill = fill_input
    ws[f"F{row}"].border = cell_border
    ws[f"F{row}"].number_format = "#,##0"
    
    ws[f"G{row}"] = f'=IF(AND(ISNUMBER(E{row}),ISNUMBER(F{row}),E{row}>0,F{row}>0), D{row}*(E{row}*F{row})/1000000, 0)'
    ws[f"G{row}"].alignment = align_right
    ws[f"G{row}"].font = font_bold
    ws[f"G{row}"].border = cell_border
    ws[f"G{row}"].number_format = "#,##0.0000"
    
    ws[f"H{row}"] = f'=IF($C$7>0, G{row}/$C$7, 0)'
    ws[f"H{row}"].alignment = align_right
    ws[f"H{row}"].font = font_regular
    ws[f"H{row}"].border = cell_border
    ws[f"H{row}"].number_format = "0.0%"
    
    ws[f"I{row}"] = remark
    ws[f"I{row}"].alignment = align_left
    ws[f"I{row}"].font = font_subtitle
    ws[f"I{row}"].border = cell_border

# Total Row (Row 24)
tot_row = 24
ws.row_dimensions[tot_row].height = 24
ws.merge_cells(f"A{tot_row}:C{tot_row}")
ws[f"A{tot_row}"] = "รวมทั้งหมด (Grand Total)"
ws[f"A{tot_row}"].font = font_bold
ws[f"A{tot_row}"].alignment = align_center

ws[f"D{tot_row}"] = f"=SUM(D12:D23)"
ws[f"D{tot_row}"].font = font_bold
ws[f"D{tot_row}"].alignment = align_center
ws[f"D{tot_row}"].number_format = "#,##0"

ws[f"E{tot_row}"] = "-"
ws[f"E{tot_row}"].alignment = align_center
ws[f"E{tot_row}"].font = font_subtitle

ws[f"F{tot_row}"] = "-"
ws[f"F{tot_row}"].alignment = align_center
ws[f"F{tot_row}"].font = font_subtitle

ws[f"G{tot_row}"] = f"=SUM(G12:G23)"
ws[f"G{tot_row}"].font = Font(name="Segoe UI", size=11, bold=True, color="1B365D")
ws[f"G{tot_row}"].alignment = align_right
ws[f"G{tot_row}"].number_format = "#,##0.0000"

ws[f"H{tot_row}"] = f"=SUM(H12:H23)"
ws[f"H{tot_row}"].font = font_bold
ws[f"H{tot_row}"].alignment = align_right
ws[f"H{tot_row}"].number_format = "0.0%"

ws[f"I{tot_row}"] = ""

for col in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
    ws[f"{col}{tot_row}"].border = total_border
    ws[f"{col}{tot_row}"].fill = fill_sub_header

# Instructions box below table (Row 26 - 32)
ws.merge_cells("A26:I26")
ws["A26"] = "💡 คำแนะนำในการใช้งานและคำนวณขนาด (Instructions & Technical Notes)"
ws["A26"].font = font_section

notes = [
    "1. เซลล์สีเหลืองอ่อน (คอลัมน์ D, E, F) คือช่องที่ท่านต้องกรอกข้อมูล: จำนวน (Qty), กว้างคลี่ (Width mm), ยาวคลี่ (Length mm)",
    "2. สำหรับชิ้นงานพับ (Bending): ให้ใช้ขนาด 'แผ่นคลี่' (Flat Pattern Blank Size) ซึ่งรวมระยะปีกพับและเผื่อการเซาะร่องพับ (V-Groove)",
    "3. ขนาดแผ่นมาตรฐานเริ่มต้นตั้งไว้ที่ 1,220 x 2,440 มม. (4 x 8 ฟุต) พื้นที่ 2.9768 ตร.ม./แผ่น สามารถเปลี่ยนขนาดได้ที่ช่อง C5 และ C6",
    "4. ค่าเผื่อเศษตัด (Waste Factor) เริ่มต้นตั้งไว้ที่ 15% (ช่อง C8) สามารถปรับลดเหลือ 10% หากตัด Nesting ได้ชิด หรือเพิ่มเป็น 20% หากมีเศษเหลือมุม",
    "5. สูตรจะคำนวณพื้นที่สุทธิ (Net Area), พื้นที่รวมเผื่อเศษ (Gross Area), และปัดเศษขึ้นเป็นจำนวนแผ่นเต็มที่ต้องใช้จริงโดยอัตโนมัติ"
]

for idx, note in enumerate(notes, 27):
    ws.merge_cells(f"A{idx}:I{idx}")
    ws[f"A{idx}"] = note
    ws[f"A{idx}"].font = font_regular
    ws[f"A{idx}"].alignment = align_left

# Set column widths
col_widths = {
    "A": 7,
    "B": 32,
    "C": 32,
    "D": 14,
    "E": 16,
    "F": 16,
    "G": 18,
    "H": 16,
    "I": 30,
    "J": 14
}
for col, w in col_widths.items():
    ws.column_dimensions[col].width = w

# Sheet 2: Reference Guide for Composite Sheets
ws2 = wb.create_sheet(title="ขนาดแผ่นมาตรฐานและแนวทาง")
ws2.views.sheetView[0].showGridLines = True

ws2.merge_cells("A1:F1")
ws2["A1"] = "ข้อมูลอ้างอิงขนาดแผ่นอลูมิเนียมคอมโพสิต (Aluminum Composite Sheet Standards)"
ws2["A1"].font = font_title
ws2.row_dimensions[1].height = 28

guide_headers = ["ขนาดมาตรฐาน (Standard Size)", "กว้าง (W) มม.", "ยาว (L) มม.", "พื้นที่ (ตร.ม./แผ่น)", "ความหนารวมทั่วไป", "การใช้งานที่นิยม"]
for c_idx, gh in enumerate(guide_headers, 1):
    cell = ws2.cell(row=3, column=c_idx)
    cell.value = gh
    cell.font = font_header
    cell.fill = fill_header
    cell.alignment = align_wrap
    cell.border = header_border
ws2.row_dimensions[3].height = 25

sizes_data = [
    ("4 x 8 ฟุต (มาตรฐานสากล - นิยมที่สุด)", 1220, 2440, "=B4*C4/1000000", "3 มม. / 4 มม.", "โครงสร้างตู้, พาร์ทิชัน, ป้าย"),
    ("1.25 x 2.50 เมตร (ไซส์ยุโรป)", 1250, 2500, "=B5*C5/1000000", "4 มม.", "งานอาคาร, ผนังตู้ขนาดใหญ่"),
    ("4 x 10 ฟุต (แผ่นยาว)", 1220, 3050, "=B6*C6/1000000", "4 มม.", "ฝาหลังตู้สูง, ชิ้นส่วนยาวต่อเนื่อง"),
    ("5 x 10 ฟุต (แผ่นหน้ากว้าง)", 1500, 3000, "=B7*C7/1000000", "4 มม.", "ชิ้นงานขนาดใหญ่ลดรอยต่อ"),
]

for r_idx, row_vals in enumerate(sizes_data, 4):
    for c_idx, val in enumerate(row_vals, 1):
        cell = ws2.cell(row=r_idx, column=c_idx)
        cell.value = val
        cell.font = font_regular
        cell.border = cell_border
        if c_idx in [2, 3]:
            cell.alignment = align_right
            cell.number_format = "#,##0"
        elif c_idx == 4:
            cell.alignment = align_right
            cell.number_format = "0.0000"
            cell.font = font_bold
        elif c_idx == 1:
            cell.alignment = align_left
            cell.font = font_bold
        else:
            cell.alignment = align_left

# Tips for bending composite sheets
ws2.merge_cells("A10:F10")
ws2["A10"] = "📐 เทคนิคการคำนวณขนาดคลี่สำหรับงานพับแผ่นคอมโพสิต (V-Groove Bending Allowance)"
ws2["A10"].font = font_section

bending_tips = [
    "1. การพับแผ่นอลูมิเนียมคอมโพสิต นิยมใช้ใบเซาะร่อง V-Groove 90° หรือ 135° ด้านหลัง โดยเหลือชั้นแกนพลาสติกและอลูมิเนียมผิวหน้าไว้ประมาณ 0.5 - 0.8 มม.",
    "2. ระยะปีกพับ (Bending Flange): ควรมีความกว้างอย่างน้อย 20 - 30 มม. เพื่อให้จับยึดรีเวทหรือสกรูได้แข็งแรง",
    "3. การหาขนาด Blank Size (กว้าง x ยาว ก่อนพับ):",
    "   - หากพับขึ้นขอบ 2 ข้าง ซ้าย-ขวา ข้างละ F มม. และแผ่นตรงกลางกว้าง W มม. -> กว้างคลี่ = W + (2 x F) - K-factor (ปกติเผื่อลดลงประมาณ 1-2 มม. ต่อมุมพับ)",
    "   - เพื่อความปลอดภัยในการสั่งแผ่น สามารถใช้ขนาด กว้างรวมปีก (W + 2F) ได้เลยโดยถือเป็นระยะเผื่อตัดแต่งขอบ",
    "4. ความหนาของแผ่นคอมโพสิตที่แนะนำสำหรับภายในตู้ Vending: 3 มม. (ผิวอลูมิเนียม 0.21 - 0.30 มม.) เพื่อน้ำหนักเบาและพับง่าย"
]

for idx, tip in enumerate(bending_tips, 11):
    ws2.merge_cells(f"A{idx}:F{idx}")
    ws2[f"A{idx}"] = tip
    ws2[f"A{idx}"].font = font_regular
    ws2[f"A{idx}"].alignment = align_left

ws2.column_dimensions["A"].width = 35
ws2.column_dimensions["B"].width = 16
ws2.column_dimensions["C"].width = 16
ws2.column_dimensions["D"].width = 20
ws2.column_dimensions["E"].width = 18
ws2.column_dimensions["F"].width = 35

output_path = "Composite_Sheet_Calculator.xlsx"
wb.save(output_path)
print(f"Successfully generated {output_path}")
