import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()
default_sheet = wb.active

# ----------------- Styles & Colors -----------------
NAVY = "1B365D"
STEEL_BLUE = "2E5B88"
LIGHT_BLUE = "E8F1F5"
HEADER_BG = "2C3E50"

# Outer Theme (Brick/Red)
OUTER_HEADER_BG = "78281F"
OUTER_LIGHT = "FADBD8"

# Inner Theme (Deep Blue)
INNER_HEADER_BG = "1B4F72"
INNER_LIGHT = "D4E6F1"

# Acrylic Theme (Teal / Cyan)
ACRYLIC_HEADER_BG = "0E6655"
ACRYLIC_LIGHT = "D1F2EB"

INPUT_YELLOW = "FEF9E7"
ACCENT_GREEN = "1E8449"
LIGHT_GREEN = "E8F8F5"
SUMMARY_BG = "F4F6F6"
BORDER_GRAY = "BDC3C7"
BORDER_DARK = "34495E"

font_title = Font(name="Segoe UI", size=15, bold=True, color="1B365D")
font_subtitle = Font(name="Segoe UI", size=10, italic=True, color="5D6D7E")
font_section = Font(name="Segoe UI", size=11, bold=True, color="1B365D")
font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
font_regular = Font(name="Segoe UI", size=10)
font_bold = Font(name="Segoe UI", size=10, bold=True)
font_highlight_big = Font(name="Segoe UI", size=18, bold=True, color="1E8449")
font_summary_label = Font(name="Segoe UI", size=10, bold=True, color="2C3E50")

fill_input = PatternFill(start_color=INPUT_YELLOW, end_color=INPUT_YELLOW, fill_type="solid")
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

col_widths = {
    "A": 7,
    "B": 32,
    "C": 28,
    "D": 12,
    "E": 15,
    "F": 15,
    "G": 16,
    "H": 15,
    "I": 28,
    "J": 14
}

def create_parts_sheet(ws, title, subtitle, header_color, light_color, parts, material_name="คอมโพสิต", default_sheet_w=1220, default_sheet_l=2440, extra_count=3):
    ws.views.sheetView[0].showGridLines = True
    fill_hdr = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
    fill_sub_hdr = PatternFill(start_color=light_color, end_color=light_color, fill_type="solid")
    
    # Title
    ws.merge_cells("A1:J1")
    ws["A1"] = title
    ws["A1"].font = font_title
    ws["A1"].alignment = align_left
    ws.row_dimensions[1].height = 26

    ws.merge_cells("A2:J2")
    ws["A2"] = subtitle
    ws["A2"].font = font_subtitle
    ws["A2"].alignment = align_left
    ws.row_dimensions[2].height = 18

    # Left Config Box (Rows 4-8)
    ws.merge_cells("B4:D4")
    ws["B4"] = f"⚙️ ข้อมูลแผ่นมาตรฐาน - {material_name} (Standard Sheet Config)"
    ws["B4"].font = font_section
    ws["B4"].alignment = align_left

    sheet_configs = [
        (5, f"ความกว้างแผ่นมาตรฐาน (Sheet Width)", default_sheet_w, " มม. (mm)", True),
        (6, f"ความยาวแผ่นมาตรฐาน (Sheet Length)", default_sheet_l, " มม. (mm)", True),
        (7, f"พื้นที่ต่อ 1 แผ่นมาตรฐาน (Area/Sheet)", "=(C5*C6)/1000000", " ตร.ม. (m²)", False),
        (8, f"เผื่อเศษตัด/พับ/โครงสร้าง (Waste Factor)", 0.15, " (15%)", True),
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

    # Right Summary Box
    total_parts_count = len(parts) + extra_count
    end_data_row = 11 + total_parts_count

    ws.merge_cells("F4:H4")
    ws["F4"] = "📊 ผลลัพธ์การคำนวณ (Calculation Summary)"
    ws["F4"].font = font_section
    ws["F4"].alignment = align_left

    summary_rows = [
        (5, "จำนวนชิ้นงานทั้งหมด (Total Quantity)", f"=SUM(D12:D{end_data_row})", "ชิ้น (pcs)"),
        (6, "พื้นที่ชิ้นงานสุทธิ (Net Total Area)", f"=SUM(G12:G{end_data_row})", "ตร.ม. (m²)"),
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

    # Grand Result Card
    ws.merge_cells("I4:J5")
    ws["I4"] = f"จำนวนแผ่น {material_name} ที่ต้องใช้\n(Recommended to Order)"
    ws["I4"].font = Font(name="Segoe UI", size=9, bold=True, color="1B365D")
    ws["I4"].alignment = align_wrap
    ws["I4"].fill = fill_sub_hdr

    ws.merge_cells("I6:J8")
    ws["I6"] = "=ROUNDUP(G8, 0)"
    ws["I6"].font = font_highlight_big
    ws["I6"].alignment = align_center
    ws["I6"].fill = fill_result_box
    ws["I6"].number_format = '0 " แผ่น"'

    for r in range(4, 9):
        for c in ["I", "J"]:
            ws[f"{c}{r}"].border = result_card_border

    # Headers
    headers = [
        ("A11", "ลำดับ\nNo.", 6),
        ("B11", "รหัส / ชื่อชิ้นงาน (SOLIDWORKS)\nPart Name", 32),
        ("C11", "ลักษณะชิ้นงาน / ตำแหน่ง\nDescription", 28),
        ("D11", "จำนวน\nQty (pcs)", 12),
        ("E11", "กว้างคลี่ (W)\nWidth (mm)", 15),
        ("F11", "ยาวคลี่ (L)\nLength (mm)", 15),
        ("G11", "พื้นที่รวม\nTotal Area (m²)", 16),
        ("H11", "สัดส่วนต่อแผ่น\n% of Sheet", 14),
        ("I11", "หมายเหตุการตัด / พับ / ติดตั้ง\nRemarks & Notes", 28),
    ]

    ws.row_dimensions[11].height = 30
    for cell_id, title_h, _ in headers:
        cell = ws[cell_id]
        cell.value = title_h
        cell.font = font_header
        cell.fill = fill_hdr
        cell.alignment = align_wrap
        cell.border = header_border

    # Data Rows
    start_row = 12
    for idx, (p_name, p_desc, qty, w, l, remark) in enumerate(parts, 1):
        row = start_row + idx - 1
        ws.row_dimensions[row].height = 21
        
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
        
        # Area Formula
        ws[f"G{row}"] = f'=IF(AND(ISNUMBER(E{row}),ISNUMBER(F{row}),E{row}>0,F{row}>0), D{row}*(E{row}*F{row})/1000000, 0)'
        ws[f"G{row}"].alignment = align_right
        ws[f"G{row}"].font = font_bold
        ws[f"G{row}"].border = cell_border
        ws[f"G{row}"].number_format = "#,##0.0000"
        
        # Proportion of 1 Sheet
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
    for e_idx in range(1, extra_count + 1):
        row = start_row + len(parts) + e_idx - 1
        ws.row_dimensions[row].height = 20
        ws[f"A{row}"] = len(parts) + e_idx
        ws[f"A{row}"].alignment = align_center
        ws[f"A{row}"].font = font_subtitle
        ws[f"A{row}"].border = cell_border
        
        ws[f"B{row}"] = f"สำรองชิ้นส่วนเพิ่มเติม {e_idx} (Extra Part)"
        ws[f"B{row}"].alignment = align_left
        ws[f"B{row}"].font = font_subtitle
        ws[f"B{row}"].border = cell_border
        
        ws[f"C{row}"] = "-"
        ws[f"C{row}"].alignment = align_left
        ws[f"C{row}"].font = font_subtitle
        ws[f"C{row}"].border = cell_border
        
        ws[f"D{row}"] = 0
        ws[f"D{row}"].alignment = align_center
        ws[f"D{row}"].font = font_regular
        ws[f"D{row}"].fill = fill_input
        ws[f"D{row}"].border = cell_border
        ws[f"D{row}"].number_format = "#,##0"
        
        ws[f"E{row}"] = ""
        ws[f"E{row}"].alignment = align_right
        ws[f"E{row}"].font = font_regular
        ws[f"E{row}"].fill = fill_input
        ws[f"E{row}"].border = cell_border
        ws[f"E{row}"].number_format = "#,##0"
        
        ws[f"F{row}"] = ""
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
        
        ws[f"I{row}"] = ""
        ws[f"I{row}"].alignment = align_left
        ws[f"I{row}"].font = font_subtitle
        ws[f"I{row}"].border = cell_border

    # Total Row
    tot_row = end_data_row + 1
    ws.row_dimensions[tot_row].height = 24
    ws.merge_cells(f"A{tot_row}:C{tot_row}")
    ws[f"A{tot_row}"] = "รวมทั้งหมด (Sub-Total)"
    ws[f"A{tot_row}"].font = font_bold
    ws[f"A{tot_row}"].alignment = align_center

    ws[f"D{tot_row}"] = f"=SUM(D12:D{end_data_row})"
    ws[f"D{tot_row}"].font = font_bold
    ws[f"D{tot_row}"].alignment = align_center
    ws[f"D{tot_row}"].number_format = "#,##0"

    ws[f"E{tot_row}"] = "-"
    ws[f"E{tot_row}"].alignment = align_center
    ws[f"E{tot_row}"].font = font_subtitle

    ws[f"F{tot_row}"] = "-"
    ws[f"F{tot_row}"].alignment = align_center
    ws[f"F{tot_row}"].font = font_subtitle

    ws[f"G{tot_row}"] = f"=SUM(G12:G{end_data_row})"
    ws[f"G{tot_row}"].font = Font(name="Segoe UI", size=11, bold=True, color=header_color)
    ws[f"G{tot_row}"].alignment = align_right
    ws[f"G{tot_row}"].number_format = "#,##0.0000"

    ws[f"H{tot_row}"] = f"=SUM(H12:H{end_data_row})"
    ws[f"H{tot_row}"].font = font_bold
    ws[f"H{tot_row}"].alignment = align_right
    ws[f"H{tot_row}"].number_format = "0.0%"

    ws[f"I{tot_row}"] = ""

    for col in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
        ws[f"{col}{tot_row}"].border = total_border
        ws[f"{col}{tot_row}"].fill = fill_sub_hdr

    for col, w in col_widths.items():
        ws.column_dimensions[col].width = w

    return end_data_row, tot_row


# -------------------------------------------------------------
# 1. Sheet: สรุปภาพรวมทั้งตู้ (Grand Summary)
# -------------------------------------------------------------
ws_summary = wb.create_sheet(title="สรุปภาพรวมทั้งตู้ (Summary)")
ws_summary.views.sheetView[0].showGridLines = True

ws_summary.merge_cells("A1:G1")
ws_summary["A1"] = "📊 สรุปภาพรวมการสั่งซื้อแผ่นคอมโพสิตและอะคริลิก (Bill of Materials)"
ws_summary["A1"].font = font_title
ws_summary.row_dimensions[1].height = 28

ws_summary.merge_cells("A2:G2")
ws_summary["A2"] = "โครงการ: Narit Vending Machine | สรุปแยกตามชนิดวัสดุ: แผ่นคอมโพสิต (ฝั่งใน + ฝั่งนอก) และ แผ่นอะคริลิกใส (Acrylic)"
ws_summary["A2"].font = font_subtitle
ws_summary.row_dimensions[2].height = 20

# Summary Table Header
sum_headers = ["หมวดหมู่วัสดุ / ส่วนงาน (Material & Section)", "จำนวนชิ้นงาน (Qty)", "พื้นที่สุทธิ (Net Area m²)", "พื้นที่เผื่อเศษ (Gross Area m²)", "แผ่นตามทฤษฎี", "สั่งซื้อ (แผ่น)", "หมายเหตุ"]
ws_summary.row_dimensions[4].height = 26
fill_navy = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
for c_idx, sh in enumerate(sum_headers, 1):
    c = ws_summary.cell(row=4, column=c_idx)
    c.value = sh
    c.font = font_header
    c.fill = fill_navy
    c.alignment = align_wrap
    c.border = header_border

# Composite Rows (Inner & Outer)
# Row 5: Inner (9 parts + 3 extras -> Tot row 24)
# Row 6: Outer (9 parts + 3 extras -> Tot row 24)
# Row 7: Total Composite
# Row 8: Acrylic (3 parts + 3 extras -> Tot row 18)
sections_summary = [
    (5, "1. แผ่นคอมโพสิต - ฝั่งใน (Inner Composite)", "='ฝั่งใน (Inner)'!D24", "='ฝั่งใน (Inner)'!G6", "='ฝั่งใน (Inner)'!G7", "='ฝั่งใน (Inner)'!G8", "='ฝั่งใน (Inner)'!I6", "แผ่นกั้น Partition, กล่องใน, ฝาหลังใน, ซับในประตู"),
    (6, "2. แผ่นคอมโพสิต - ฝั่งนอก (Outer Composite)", "='ฝั่งนอก (Outer)'!D24", "='ฝั่งนอก (Outer)'!G6", "='ฝั่งนอก (Outer)'!G7", "='ฝั่งนอก (Outer)'!G8", "='ฝั่งนอก (Outer)'!I6", "ฝาบน, ฝาหลัง, ฝาข้างซ้าย-ขวา, บานประตูหน้านอก"),
]

for r_idx, name, f_qty, f_net, f_gross, f_theo, f_rec, remark in sections_summary:
    ws_summary.row_dimensions[r_idx].height = 22
    ws_summary[f"A{r_idx}"] = name
    ws_summary[f"A{r_idx}"].font = font_bold
    ws_summary[f"A{r_idx}"].border = cell_border
    
    ws_summary[f"B{r_idx}"] = f_qty
    ws_summary[f"B{r_idx}"].font = font_bold
    ws_summary[f"B{r_idx}"].alignment = align_center
    ws_summary[f"B{r_idx}"].border = cell_border
    ws_summary[f"B{r_idx}"].number_format = '#,##0 " ชิ้น"'
    
    ws_summary[f"C{r_idx}"] = f_net
    ws_summary[f"C{r_idx}"].font = font_regular
    ws_summary[f"C{r_idx}"].alignment = align_right
    ws_summary[f"C{r_idx}"].border = cell_border
    ws_summary[f"C{r_idx}"].number_format = '#,##0.0000 " m²"'
    
    ws_summary[f"D{r_idx}"] = f_gross
    ws_summary[f"D{r_idx}"].font = font_regular
    ws_summary[f"D{r_idx}"].alignment = align_right
    ws_summary[f"D{r_idx}"].border = cell_border
    ws_summary[f"D{r_idx}"].number_format = '#,##0.0000 " m²"'
    
    ws_summary[f"E{r_idx}"] = f_theo
    ws_summary[f"E{r_idx}"].font = font_regular
    ws_summary[f"E{r_idx}"].alignment = align_right
    ws_summary[f"E{r_idx}"].border = cell_border
    ws_summary[f"E{r_idx}"].number_format = '0.00'
    
    ws_summary[f"F{r_idx}"] = f_rec
    ws_summary[f"F{r_idx}"].font = font_bold
    ws_summary[f"F{r_idx}"].alignment = align_center
    ws_summary[f"F{r_idx}"].border = cell_border
    ws_summary[f"F{r_idx}"].number_format = '0 " แผ่น"'
    
    ws_summary[f"G{r_idx}"] = remark
    ws_summary[f"G{r_idx}"].font = font_subtitle
    ws_summary[f"G{r_idx}"].border = cell_border

# Row 7: Grand Subtotal for Aluminum Composite (Inner + Outer)
r_idx = 7
ws_summary.row_dimensions[r_idx].height = 24
ws_summary[f"A{r_idx}"] = "⭐ รวมแผ่นคอมโพสิตทั้งตู้ (Total Composite)"
ws_summary[f"A{r_idx}"].font = font_bold
ws_summary[f"A{r_idx}"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
ws_summary[f"A{r_idx}"].border = total_border

ws_summary[f"B{r_idx}"] = "=B5+B6"
ws_summary[f"B{r_idx}"].font = font_bold
ws_summary[f"B{r_idx}"].alignment = align_center
ws_summary[f"B{r_idx}"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
ws_summary[f"B{r_idx}"].border = total_border
ws_summary[f"B{r_idx}"].number_format = '#,##0 " ชิ้น"'

ws_summary[f"C{r_idx}"] = "=C5+C6"
ws_summary[f"C{r_idx}"].font = font_bold
ws_summary[f"C{r_idx}"].alignment = align_right
ws_summary[f"C{r_idx}"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
ws_summary[f"C{r_idx}"].border = total_border
ws_summary[f"C{r_idx}"].number_format = '#,##0.0000 " m²"'

ws_summary[f"D{r_idx}"] = "=D5+D6"
ws_summary[f"D{r_idx}"].font = font_bold
ws_summary[f"D{r_idx}"].alignment = align_right
ws_summary[f"D{r_idx}"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
ws_summary[f"D{r_idx}"].border = total_border
ws_summary[f"D{r_idx}"].number_format = '#,##0.0000 " m²"'

ws_summary[f"E{r_idx}"] = "=E5+E6"
ws_summary[f"E{r_idx}"].font = font_bold
ws_summary[f"E{r_idx}"].alignment = align_right
ws_summary[f"E{r_idx}"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
ws_summary[f"E{r_idx}"].border = total_border
ws_summary[f"E{r_idx}"].number_format = '0.00'

ws_summary[f"F{r_idx}"] = "=ROUNDUP(D7/'ฝั่งใน (Inner)'!C7, 0)"
ws_summary[f"F{r_idx}"].font = Font(name="Segoe UI", size=11, bold=True, color="1E8449")
ws_summary[f"F{r_idx}"].alignment = align_center
ws_summary[f"F{r_idx}"].fill = PatternFill(start_color=LIGHT_GREEN, end_color=LIGHT_GREEN, fill_type="solid")
ws_summary[f"F{r_idx}"].border = total_border
ws_summary[f"F{r_idx}"].number_format = '0 " แผ่น"'

ws_summary[f"G{r_idx}"] = "คำนวณรวม Nesting ตัดคอมโพสิตทั้งตู้"
ws_summary[f"G{r_idx}"].font = font_subtitle
ws_summary[f"G{r_idx}"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
ws_summary[f"G{r_idx}"].border = total_border

# Row 8: Acrylic Row
r_idx = 8
ws_summary.row_dimensions[r_idx].height = 24
ws_summary[f"A{r_idx}"] = "3. แผ่นอะคริลิกใส (Acrylic Sheet)"
ws_summary[f"A{r_idx}"].font = font_bold
ws_summary[f"A{r_idx}"].border = cell_border

ws_summary[f"B{r_idx}"] = "='อะคริลิก (Acrylic)'!D18"
ws_summary[f"B{r_idx}"].font = font_bold
ws_summary[f"B{r_idx}"].alignment = align_center
ws_summary[f"B{r_idx}"].border = cell_border
ws_summary[f"B{r_idx}"].number_format = '#,##0 " ชิ้น"'

ws_summary[f"C{r_idx}"] = "='อะคริลิก (Acrylic)'!G6"
ws_summary[f"C{r_idx}"].font = font_regular
ws_summary[f"C{r_idx}"].alignment = align_right
ws_summary[f"C{r_idx}"].border = cell_border
ws_summary[f"C{r_idx}"].number_format = '#,##0.0000 " m²"'

ws_summary[f"D{r_idx}"] = "='อะคริลิก (Acrylic)'!G7"
ws_summary[f"D{r_idx}"].font = font_regular
ws_summary[f"D{r_idx}"].alignment = align_right
ws_summary[f"D{r_idx}"].border = cell_border
ws_summary[f"D{r_idx}"].number_format = '#,##0.0000 " m²"'

ws_summary[f"E{r_idx}"] = "='อะคริลิก (Acrylic)'!G8"
ws_summary[f"E{r_idx}"].font = font_regular
ws_summary[f"E{r_idx}"].alignment = align_right
ws_summary[f"E{r_idx}"].border = cell_border
ws_summary[f"E{r_idx}"].number_format = '0.00'

ws_summary[f"F{r_idx}"] = "='อะคริลิก (Acrylic)'!I6"
ws_summary[f"F{r_idx}"].font = Font(name="Segoe UI", size=11, bold=True, color="0E6655")
ws_summary[f"F{r_idx}"].alignment = align_center
ws_summary[f"F{r_idx}"].fill = PatternFill(start_color=ACRYLIC_LIGHT, end_color=ACRYLIC_LIGHT, fill_type="solid")
ws_summary[f"F{r_idx}"].border = cell_border
ws_summary[f"F{r_idx}"].number_format = '0 " แผ่น"'

ws_summary[f"G{r_idx}"] = "ฝาครอบอะคริลิกด้านหน้าและด้านข้าง (แผ่นใส/ตกแต่ง)"
ws_summary[f"G{r_idx}"].font = font_subtitle
ws_summary[f"G{r_idx}"].border = cell_border


# Two Recommendation Cards (Row 11 - 15)
# Card 1: Composite Total
ws_summary.merge_cells("A11:C12")
ws_summary["A11"] = "📦 แผ่นอลูมิเนียมคอมโพสิต (Total Composite)\nสั่งซื้อรวมทั้งตู้ (Inner + Outer)"
ws_summary["A11"].font = font_section
ws_summary["A11"].alignment = align_center
ws_summary["A11"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")

ws_summary.merge_cells("A13:C15")
ws_summary["A13"] = "=F7"
ws_summary["A13"].font = font_highlight_big
ws_summary["A13"].alignment = align_center
ws_summary["A13"].fill = fill_result_box
ws_summary["A13"].number_format = '0 " แผ่น"'

for r in range(11, 16):
    for c in ["A", "B", "C"]:
        ws_summary[f"{c}{r}"].border = result_card_border

# Card 2: Acrylic Total
ws_summary.merge_cells("E11:G12")
ws_summary["E11"] = "💎 แผ่นอะคริลิกใส (Acrylic Sheet)\nสำหรับฝาหน้าและฝาข้างขวา"
ws_summary["E11"].font = Font(name="Segoe UI", size=11, bold=True, color="0E6655")
ws_summary["E11"].alignment = align_center
ws_summary["E11"].fill = PatternFill(start_color=ACRYLIC_LIGHT, end_color=ACRYLIC_LIGHT, fill_type="solid")

ws_summary.merge_cells("E13:G15")
ws_summary["E13"] = "=F8"
ws_summary["E13"].font = Font(name="Segoe UI", size=18, bold=True, color="0E6655")
ws_summary["E13"].alignment = align_center
ws_summary["E13"].fill = PatternFill(start_color=ACRYLIC_LIGHT, end_color=ACRYLIC_LIGHT, fill_type="solid")
ws_summary["E13"].number_format = '0 " แผ่น"'

for r in range(11, 16):
    for c in ["E", "F", "G"]:
        ws_summary[f"{c}{r}"].border = result_card_border

ws_summary.column_dimensions["A"].width = 38
ws_summary.column_dimensions["B"].width = 18
ws_summary.column_dimensions["C"].width = 20
ws_summary.column_dimensions["D"].width = 20
ws_summary.column_dimensions["E"].width = 16
ws_summary.column_dimensions["F"].width = 20
ws_summary.column_dimensions["G"].width = 38


# -------------------------------------------------------------
# 2. Sheet: ฝั่งนอก (Outer) - เฉพาะแผ่นคอมโพสิต
# -------------------------------------------------------------
ws_outer = wb.create_sheet(title="ฝั่งนอก (Outer)")

outer_parts = [
    ("Cover top-Bending-st-2psc", "ฝาครอบบน (พับขึ้นรูป)", 2, "", "", "มี 2 ชิ้น (2psc) / พับขอบ Bending"),
    ("Cover Back 1-Bending-st-2psc", "ฝาครอบหลัง 1 (พับขึ้นรูป)", 2, "", "", "มี 2 ชิ้น (2psc) / พับขอบ Bending"),
    ("Door left-Bending-st", "ฝาประตูซ้ายนอก (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Left Side-Bending-st", "ฝาครอบข้างซ้าย (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Left Side 2-Bending-st", "ฝาครอบข้างซ้าย 2 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Front 1-Bending-st", "ฝาครอบหน้า 1 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Front 2-Bending-st", "ฝาครอบหน้า 2 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Right Side 1-Bending-st", "ฝาครอบข้างขวา 1 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Right Side 2-Bending-st", "ฝาครอบข้างขวา 2 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
]

create_parts_sheet(
    ws_outer,
    "ตารางคำนวณแผ่นคอมโพสิต - ชิ้นส่วนฝั่งนอก (Outer Parts)",
    "รายการชิ้นส่วนจาก SOLIDWORKS: ฝาบน, ฝาหลัง, ฝาข้าง, ประตู และฝาหน้า (เฉพาะแผ่นคอมโพสิต)",
    OUTER_HEADER_BG,
    OUTER_LIGHT,
    outer_parts,
    material_name="คอมโพสิต",
    extra_count=3
)


# -------------------------------------------------------------
# 3. Sheet: ฝั่งใน (Inner) - เฉพาะแผ่นคอมโพสิต
# -------------------------------------------------------------
ws_inner = wb.create_sheet(title="ฝั่งใน (Inner)")

inner_parts = [
    ("Partition-Inner 3-st", "แผ่นกั้นภายในตู้ 3", 1, "", "", "แผ่นกั้นตรง / มีเจาะรูยึด"),
    ("Partition-Inner 1-st", "แผ่นกั้นภายในตู้ 1", 1, "", "", "แผ่นกั้นตรง"),
    ("Partition-Inner-Box-1-st", "กล่อง/โครงกั้นภายใน 1", 1, "", "", "มีพับขึ้นรูปกล่อง (เช็ค Blank Size)"),
    ("Partition-Inner 2-st", "แผ่นกั้นภายในตู้ 2", 1, "", "", "แผ่นกั้นตรง"),
    ("Door Right-Inner 1-Bending-st", "ฝาในประตูขวา พับ 1 (ซับใน)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Back 2-Inner-Bending-st", "ฝาครอบหลังใน 2 พับ", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Back 1-Inner-Bending-st", "ฝาครอบหลังใน 1 พับ", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Door left-inner-Bending-st", "ฝาในประตูซ้าย พับ (ซับใน)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Door left-inner-Bending", "ฝาในประตูซ้าย พับ", 1, "", "", "ชิ้นงานพับขอบ Bending"),
]

create_parts_sheet(
    ws_inner,
    "ตารางคำนวณแผ่นคอมโพสิต - ชิ้นส่วนฝั่งใน (Inner Parts)",
    "รายการชิ้นส่วนภายในตู้: แผ่นกั้น Partition, กล่องใน, ซับในประตู และฝาหลังใน",
    INNER_HEADER_BG,
    INNER_LIGHT,
    inner_parts,
    material_name="คอมโพสิต",
    extra_count=3
)


# -------------------------------------------------------------
# 4. Sheet: อะคริลิก (Acrylic)
# -------------------------------------------------------------
ws_acrylic = wb.create_sheet(title="อะคริลิก (Acrylic)")

acrylic_parts = [
    ("Arcylic Cover Front 2-st", "ฝาครอบหน้า 2 (แผ่นอะคริลิกใส/ป้ายไฟ)", 1, "", "", "ตัดเลเซอร์ Laser Cut / ขัดขอบ"),
    ("Arcylic Cover Front-st", "ฝาครอบหน้า (แผ่นอะคริลิกใส/ช่องมอง)", 1, "", "", "ตัดเลเซอร์ Laser Cut / ขัดขอบ"),
    ("Arcylic Cover Right -side-st", "ฝาครอบข้างขวา (แผ่นอะคริลิกใส/แสดงผล)", 1, "", "", "ตัดเลเซอร์ Laser Cut / ขัดขอบ"),
]

create_parts_sheet(
    ws_acrylic,
    "ตารางคำนวณแผ่นอะคริลิก (Acrylic Sheet Requirement)",
    "รายการชิ้นส่วนอะคริลิกจาก SOLIDWORKS: ฝาครอบด้านหน้าและฝาครอบด้านข้าง",
    ACRYLIC_HEADER_BG,
    ACRYLIC_LIGHT,
    acrylic_parts,
    material_name="อะคริลิก",
    default_sheet_w=1220,
    default_sheet_l=2440,
    extra_count=3
)


# -------------------------------------------------------------
# 5. Sheet: ขนาดแผ่นมาตรฐานและแนวทาง (Guide)
# -------------------------------------------------------------
ws_guide = wb.create_sheet(title="ขนาดแผ่นมาตรฐานและแนวทาง")
ws_guide.views.sheetView[0].showGridLines = True

ws_guide.merge_cells("A1:F1")
ws_guide["A1"] = "ข้อมูลอ้างอิงขนาดแผ่นอลูมิเนียมคอมโพสิตและแผ่นอะคริลิก"
ws_guide["A1"].font = font_title
ws_guide.row_dimensions[1].height = 28

# Composite Standards
ws_guide.merge_cells("A3:F3")
ws_guide["A3"] = "1. ขนาดแผ่นอลูมิเนียมคอมโพสิตมาตรฐาน (Aluminum Composite Standard Sizes)"
ws_guide["A3"].font = font_section

guide_headers = ["ขนาดมาตรฐาน (Standard Size)", "กว้าง (W) มม.", "ยาว (L) มม.", "พื้นที่ (ตร.ม./แผ่น)", "ความหนารวมทั่วไป", "การใช้งานที่นิยม"]
for c_idx, gh in enumerate(guide_headers, 1):
    cell = ws_guide.cell(row=4, column=c_idx)
    cell.value = gh
    cell.font = font_header
    cell.fill = fill_navy
    cell.alignment = align_wrap
    cell.border = header_border
ws_guide.row_dimensions[4].height = 25

sizes_data = [
    ("4 x 8 ฟุต (มาตรฐานสากล - นิยมที่สุด)", 1220, 2440, "=B5*C5/1000000", "3 มม. / 4 มม.", "โครงสร้างตู้, พาร์ทิชัน, ฝาครอบ"),
    ("1.25 x 2.50 เมตร (ไซส์ยุโรป)", 1250, 2500, "=B6*C6/1000000", "4 มม.", "งานอาคาร, ผนังตู้ขนาดใหญ่"),
    ("4 x 10 ฟุต (แผ่นยาว)", 1220, 3050, "=B7*C7/1000000", "4 มม.", "ฝาหลังตู้สูง, ชิ้นส่วนยาวต่อเนื่อง"),
    ("5 x 10 ฟุต (แผ่นหน้ากว้าง)", 1500, 3000, "=B8*C8/1000000", "4 มม.", "ชิ้นงานขนาดใหญ่ลดรอยต่อ"),
]

for r_idx, row_vals in enumerate(sizes_data, 5):
    for c_idx, val in enumerate(row_vals, 1):
        cell = ws_guide.cell(row=r_idx, column=c_idx)
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

# Acrylic Standards
ws_guide.merge_cells("A10:F10")
ws_guide["A10"] = "2. ขนาดแผ่นอะคริลิกมาตรฐาน (Acrylic Sheet Standard Sizes)"
ws_guide["A10"].font = font_section

acrylic_headers = ["ขนาดแผ่นอะคริลิก", "กว้าง (W) มม.", "ยาว (L) มม.", "พื้นที่ (ตร.ม./แผ่น)", "ความหนาทั่วไป", "คุณสมบัติ/การใช้งาน"]
for c_idx, gh in enumerate(acrylic_headers, 1):
    cell = ws_guide.cell(row=11, column=c_idx)
    cell.value = gh
    cell.font = font_header
    cell.fill = PatternFill(start_color=ACRYLIC_HEADER_BG, end_color=ACRYLIC_HEADER_BG, fill_type="solid")
    cell.alignment = align_wrap
    cell.border = header_border
ws_guide.row_dimensions[11].height = 25

acrylic_sizes = [
    ("4 x 8 ฟุต (ขนาดเต็มแผ่นมาตรฐาน)", 1220, 2440, "=B12*C12/1000000", "2, 3, 5, 8 มม.", "งานตู้โชว์, บานหน้าต่าง, ฝาครอบใส"),
    ("4 x 6 ฟุต (ขนาดตัดแบ่ง)", 1220, 1830, "=B13*C13/1000000", "2, 3, 5 มม.", "ป้ายหน้าร้าน, ฝาครอบเครื่อง"),
    ("3 x 6 ฟุต (ขนาดยอดนิยม)", 915, 1830, "=B14*C14/1000000", "2, 3, 5 มม.", "ชิ้นงานขนาดกลาง ประหยัดเศษ"),
    ("2 x 4 ฟุต (แผ่นเล็ก)", 610, 1220, "=B15*C15/1000000", "2, 3, 5 มม.", "ชิ้นงานขนาดเล็ก, ป้ายไฟ"),
]

for r_idx, row_vals in enumerate(acrylic_sizes, 12):
    for c_idx, val in enumerate(row_vals, 1):
        cell = ws_guide.cell(row=r_idx, column=c_idx)
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

# Tips
ws_guide.merge_cells("A17:F17")
ws_guide["A17"] = "📐 เทคนิคและข้อแนะนำการตัดและการพับ (Fabrication Notes)"
ws_guide["A17"].font = font_section

bending_tips = [
    "1. แผ่นคอมโพสิต: ใช้ใบมีดเซาะร่อง V-Groove 90° หรือ 135° ด้านหลัง โดยเหลือชั้นพลาสติกและผิวหน้าไว้ประมาณ 0.5 - 0.8 มม. ก่อนพับขึ้นรูป",
    "2. แผ่นอะคริลิก (Arcylic): แนะนำให้ตัดด้วยเครื่อง Laser Cutting เพื่อให้ขอบเรียบเงาใส ไม่ต้องขัดแต่งเพิ่มเติม",
    "3. ระยะเผื่อคลี่ชิ้นงานพับ (Blank Size): สามารถใช้สูตร กว้างรวมปีกพับ (W + 2F) ในการคำนวณเบื้องต้น เพื่อความปลอดภัยของเศษตัด",
    "4. ค่าเผื่อเศษตัด (Waste Factor): สำหรับอะคริลิกแผ่นใส แนะนำตั้งเผื่อไว้ 15% - 20% เนื่องจากต้องเผื่อระยะแนวทางเดินลำแสงเลเซอร์และการเว้นขอบฟิล์มกันรอย"
]

for idx, tip in enumerate(bending_tips, 18):
    ws_guide.merge_cells(f"A{idx}:F{idx}")
    ws_guide[f"A{idx}"] = tip
    ws_guide[f"A{idx}"].font = font_regular
    ws_guide[f"A{idx}"].alignment = align_left

ws_guide.column_dimensions["A"].width = 35
ws_guide.column_dimensions["B"].width = 16
ws_guide.column_dimensions["C"].width = 16
ws_guide.column_dimensions["D"].width = 20
ws_guide.column_dimensions["E"].width = 18
ws_guide.column_dimensions["F"].width = 35

# Remove default empty sheet
if default_sheet in wb.worksheets:
    wb.remove(default_sheet)

output_path = "Composite_Sheet_Calculator.xlsx"
wb.save(output_path)
print(f"Successfully generated {output_path}")
