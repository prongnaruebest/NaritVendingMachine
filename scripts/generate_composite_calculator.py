import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

# Remove default sheet
default_sheet = wb.active

# ----------------- Styles & Colors -----------------
NAVY = "1B365D"
STEEL_BLUE = "2E5B88"
LIGHT_BLUE = "E8F1F5"
HEADER_BG = "2C3E50"
OUTER_HEADER_BG = "78281F"   # Red/Brick tone for Outer
OUTER_LIGHT = "FADBD8"
INNER_HEADER_BG = "1B4F72"   # Deep Blue tone for Inner
INNER_LIGHT = "D4E6F1"
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

def create_parts_sheet(ws, title, subtitle, header_color, light_color, parts, extra_count=3):
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
    ws["I4"] = "จำนวนแผ่นที่แนะนำสั่งซื้อ\n(Recommended to Order)"
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
        ("I11", "หมายเหตุการตัด / พับ\nRemarks & Bending Note", 28),
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
# 1. Sheet: สรุปรวมภาพรวมทั้งตู้ (Grand Summary)
# -------------------------------------------------------------
ws_summary = wb.create_sheet(title="สรุปภาพรวมทั้งตู้ (Summary)")
ws_summary.views.sheetView[0].showGridLines = True

ws_summary.merge_cells("A1:G1")
ws_summary["A1"] = "📊 สรุปภาพรวมจำนวนแผ่นคอมโพสิตทั้งตู้ (Inner & Outer Combined)"
ws_summary["A1"].font = font_title
ws_summary.row_dimensions[1].height = 28

ws_summary.merge_cells("A2:G2")
ws_summary["A2"] = "โครงการ: Narit Vending Machine | เปรียบเทียบและรวมการสั่งซื้อแผ่นคอมโพสิตฝั่งใน (Inner) และฝั่งนอก (Outer)"
ws_summary["A2"].font = font_subtitle
ws_summary.row_dimensions[2].height = 20

# Summary Table Header
sum_headers = ["หมวดหมู่ / โซน (Section)", "จำนวนชิ้นงาน (Qty)", "พื้นที่สุทธิ (Net Area m²)", "พื้นที่เผื่อเศษ (Gross Area m²)", "แผ่นตามทฤษฎี", "สั่งซื้อแยกฝั่ง (แผ่น)", "หมายเหตุ"]
ws_summary.row_dimensions[4].height = 26
fill_navy = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
for c_idx, sh in enumerate(sum_headers, 1):
    c = ws_summary.cell(row=4, column=c_idx)
    c.value = sh
    c.font = font_header
    c.fill = fill_navy
    c.alignment = align_wrap
    c.border = header_border

# Rows for Inner & Outer
sections_summary = [
    (5, "1. ชิ้นส่วนฝั่งใน (Inner Parts)", "='ฝั่งใน (Inner)'!D24", "='ฝั่งใน (Inner)'!G6", "='ฝั่งใน (Inner)'!G7", "='ฝั่งใน (Inner)'!G8", "='ฝั่งใน (Inner)'!I6", "แผ่นกั้น, ซับในประตู, ฝาครอบหลังใน"),
    (6, "2. ชิ้นส่วนฝั่งนอก (Outer Parts)", "='ฝั่งนอก (Outer)'!D27", "='ฝั่งนอก (Outer)'!G6", "='ฝั่งนอก (Outer)'!G7", "='ฝั่งนอก (Outer)'!G8", "='ฝั่งนอก (Outer)'!I6", "ฝาบน, ฝาหลัง, ฝาข้างซ้าย-ขวา, ประตูหน้า"),
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

# Row 7: Grand Total if cut separately
r_idx = 7
ws_summary.row_dimensions[r_idx].height = 24
ws_summary[f"A{r_idx}"] = "รวมแบบสั่งซื้อแยกฝั่ง (Separate Purchasing)"
ws_summary[f"A{r_idx}"].font = font_bold
ws_summary[f"A{r_idx}"].border = total_border

ws_summary[f"B{r_idx}"] = "=B5+B6"
ws_summary[f"B{r_idx}"].font = font_bold
ws_summary[f"B{r_idx}"].alignment = align_center
ws_summary[f"B{r_idx}"].border = total_border
ws_summary[f"B{r_idx}"].number_format = '#,##0 " ชิ้น"'

ws_summary[f"C{r_idx}"] = "=C5+C6"
ws_summary[f"C{r_idx}"].font = font_bold
ws_summary[f"C{r_idx}"].alignment = align_right
ws_summary[f"C{r_idx}"].border = total_border
ws_summary[f"C{r_idx}"].number_format = '#,##0.0000 " m²"'

ws_summary[f"D{r_idx}"] = "=D5+D6"
ws_summary[f"D{r_idx}"].font = font_bold
ws_summary[f"D{r_idx}"].alignment = align_right
ws_summary[f"D{r_idx}"].border = total_border
ws_summary[f"D{r_idx}"].number_format = '#,##0.0000 " m²"'

ws_summary[f"E{r_idx}"] = "=E5+E6"
ws_summary[f"E{r_idx}"].font = font_bold
ws_summary[f"E{r_idx}"].alignment = align_right
ws_summary[f"E{r_idx}"].border = total_border
ws_summary[f"E{r_idx}"].number_format = '0.00'

ws_summary[f"F{r_idx}"] = "=F5+F6"
ws_summary[f"F{r_idx}"].font = font_bold
ws_summary[f"F{r_idx}"].alignment = align_center
ws_summary[f"F{r_idx}"].border = total_border
ws_summary[f"F{r_idx}"].number_format = '0 " แผ่น"'

ws_summary[f"G{r_idx}"] = "ผลรวมแผ่นเมื่อปัดเศษแยกแต่ละฝั่ง"
ws_summary[f"G{r_idx}"].font = font_subtitle
ws_summary[f"G{r_idx}"].border = total_border

# Big Recommendation Card for Combined Nesting (แถว 9 - 14)
ws_summary.merge_cells("A10:C13")
ws_summary["A10"] = "💡 แนะนำการสั่งซื้อรวมทั้งตู้\n(Combined Nesting Optimization)\n\nหากตัดร่วมกันทั้งฝั่งในและฝั่งนอก จะลดเศษเหลือตามมุมได้มากที่สุด"
ws_summary["A10"].font = Font(name="Segoe UI", size=10, bold=True, color="1B365D")
ws_summary["A10"].alignment = align_wrap
ws_summary["A10"].fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")

for r in range(10, 14):
    for c in ["A", "B", "C"]:
        ws_summary[f"{c}{r}"].border = result_card_border

ws_summary.merge_cells("D10:E11")
ws_summary["D10"] = "พื้นที่รวมทั้งตู้ (Gross)"
ws_summary["D10"].font = font_bold
ws_summary["D10"].alignment = align_center
ws_summary["D10"].fill = PatternFill(start_color=SUMMARY_BG, end_color=SUMMARY_BG, fill_type="solid")

ws_summary.merge_cells("D12:E13")
ws_summary["D12"] = "=D7"
ws_summary["D12"].font = Font(name="Segoe UI", size=14, bold=True, color="1B365D")
ws_summary["D12"].alignment = align_center
ws_summary["D12"].fill = PatternFill(start_color=SUMMARY_BG, end_color=SUMMARY_BG, fill_type="solid")
ws_summary["D12"].number_format = '#,##0.00 " m²"'

for r in range(10, 14):
    for c in ["D", "E"]:
        ws_summary[f"{c}{r}"].border = result_card_border

ws_summary.merge_cells("F10:G11")
ws_summary["F10"] = "จำนวนแผ่นรวมที่ต้องใช้จริง\n(ROUNDUP รวมทั้งตู้)"
ws_summary["F10"].font = font_bold
ws_summary["F10"].alignment = align_wrap
ws_summary["F10"].fill = PatternFill(start_color=LIGHT_GREEN, end_color=LIGHT_GREEN, fill_type="solid")

ws_summary.merge_cells("F12:G13")
ws_summary["F12"] = "=ROUNDUP(D7/'ฝั่งใน (Inner)'!C7, 0)"
ws_summary["F12"].font = font_highlight_big
ws_summary["F12"].alignment = align_center
ws_summary["F12"].fill = fill_result_box
ws_summary["F12"].number_format = '0 " แผ่น"'

for r in range(10, 14):
    for c in ["F", "G"]:
        ws_summary[f"{c}{r}"].border = result_card_border

ws_summary.column_dimensions["A"].width = 34
ws_summary.column_dimensions["B"].width = 18
ws_summary.column_dimensions["C"].width = 20
ws_summary.column_dimensions["D"].width = 20
ws_summary.column_dimensions["E"].width = 16
ws_summary.column_dimensions["F"].width = 20
ws_summary.column_dimensions["G"].width = 38


# -------------------------------------------------------------
# 2. Sheet: ฝั่งนอก (Outer Parts)
# -------------------------------------------------------------
ws_outer = wb.create_sheet(title="ฝั่งนอก (Outer)")

outer_parts = [
    ("Cover top-Bending-st-2psc", "ฝาครอบบน (พับขึ้นรูป)", 2, "", "", "มี 2 ชิ้น (2psc) / พับขอบ Bending"),
    ("Cover Back 1-Bending-st-2psc", "ฝาครอบหลัง 1 (พับขึ้นรูป)", 2, "", "", "มี 2 ชิ้น (2psc) / พับขอบ Bending"),
    ("Door left-Bending-st", "ฝาประตูซ้ายนอก (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Left Side-Bending-st", "ฝาครอบข้างซ้าย (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Left Side 2-Bending-st", "ฝาครอบข้างซ้าย 2 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Front 1-Bending-st", "ฝาครอบหน้า 1 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Arcylic Cover Front 2-st", "ฝาครอบหน้า 2 (อะคริลิก/คอมโพสิต)", 1, "", "", "เช็คสเปกว่าใช้ อะคริลิก หรือ คอมโพสิต"),
    ("Arcylic Cover Front-st", "ฝาครอบหน้า (อะคริลิก/คอมโพสิต)", 1, "", "", "เช็คสเปกว่าใช้ อะคริลิก หรือ คอมโพสิต"),
    ("Cover Front 2-Bending-st", "ฝาครอบหน้า 2 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Arcylic Cover Right -side-st", "ฝาครอบข้างขวา (อะคริลิก/คอมโพสิต)", 1, "", "", "เช็คสเปกว่าใช้ อะคริลิก หรือ คอมโพสิต"),
    ("Cover Right Side 1-Bending-st", "ฝาครอบข้างขวา 1 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
    ("Cover Right Side 2-Bending-st", "ฝาครอบข้างขวา 2 (พับขึ้นรูป)", 1, "", "", "ชิ้นงานพับขอบ Bending"),
]

create_parts_sheet(
    ws_outer,
    "ตารางคำนวณแผ่นคอมโพสิต - ชิ้นส่วนฝั่งนอก (Outer Parts)",
    "รายการชิ้นส่วนจาก SOLIDWORKS: ฝาบน, ฝาหลัง, ฝาข้าง, ประตู และฝาหน้า",
    OUTER_HEADER_BG,
    OUTER_LIGHT,
    outer_parts,
    extra_count=3
)


# -------------------------------------------------------------
# 3. Sheet: ฝั่งใน (Inner Parts)
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
    extra_count=3
)


# -------------------------------------------------------------
# 4. Sheet: ขนาดแผ่นมาตรฐานและแนวทาง (Guide)
# -------------------------------------------------------------
ws_guide = wb.create_sheet(title="ขนาดแผ่นมาตรฐานและแนวทาง")
ws_guide.views.sheetView[0].showGridLines = True

ws_guide.merge_cells("A1:F1")
ws_guide["A1"] = "ข้อมูลอ้างอิงขนาดแผ่นอลูมิเนียมคอมโพสิต (Aluminum Composite Sheet Standards)"
ws_guide["A1"].font = font_title
ws_guide.row_dimensions[1].height = 28

guide_headers = ["ขนาดมาตรฐาน (Standard Size)", "กว้าง (W) มม.", "ยาว (L) มม.", "พื้นที่ (ตร.ม./แผ่น)", "ความหนารวมทั่วไป", "การใช้งานที่นิยม"]
for c_idx, gh in enumerate(guide_headers, 1):
    cell = ws_guide.cell(row=3, column=c_idx)
    cell.value = gh
    cell.font = font_header
    cell.fill = fill_navy
    cell.alignment = align_wrap
    cell.border = header_border
ws_guide.row_dimensions[3].height = 25

sizes_data = [
    ("4 x 8 ฟุต (มาตรฐานสากล - นิยมที่สุด)", 1220, 2440, "=B4*C4/1000000", "3 มม. / 4 มม.", "โครงสร้างตู้, พาร์ทิชัน, ป้าย"),
    ("1.25 x 2.50 เมตร (ไซส์ยุโรป)", 1250, 2500, "=B5*C5/1000000", "4 มม.", "งานอาคาร, ผนังตู้ขนาดใหญ่"),
    ("4 x 10 ฟุต (แผ่นยาว)", 1220, 3050, "=B6*C6/1000000", "4 มม.", "ฝาหลังตู้สูง, ชิ้นส่วนยาวต่อเนื่อง"),
    ("5 x 10 ฟุต (แผ่นหน้ากว้าง)", 1500, 3000, "=B7*C7/1000000", "4 มม.", "ชิ้นงานขนาดใหญ่ลดรอยต่อ"),
]

for r_idx, row_vals in enumerate(sizes_data, 4):
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

ws_guide.merge_cells("A10:F10")
ws_guide["A10"] = "📐 เทคนิคการคำนวณขนาดคลี่สำหรับงานพับแผ่นคอมโพสิต (V-Groove Bending Allowance)"
ws_guide["A10"].font = font_section

bending_tips = [
    "1. การพับแผ่นอลูมิเนียมคอมโพสิต นิยมใช้ใบเซาะร่อง V-Groove 90° หรือ 135° ด้านหลัง โดยเหลือชั้นแกนพลาสติกและอลูมิเนียมผิวหน้าไว้ประมาณ 0.5 - 0.8 มม.",
    "2. ระยะปีกพับ (Bending Flange): ควรมีความกว้างอย่างน้อย 20 - 30 มม. เพื่อให้จับยึดรีเวทหรือสกรูได้แข็งแรง",
    "3. การหาขนาด Blank Size (กว้าง x ยาว ก่อนพับ):",
    "   - หากพับขึ้นขอบ 2 ข้าง ซ้าย-ขวา ข้างละ F มม. และแผ่นตรงกลางกว้าง W มม. -> กว้างคลี่ = W + (2 x F) - K-factor (ปกติเผื่อลดลงประมาณ 1-2 มม. ต่อมุมพับ)",
    "   - เพื่อความปลอดภัยในการสั่งแผ่น สามารถใช้ขนาด กว้างรวมปีก (W + 2F) ได้เลยโดยถือเป็นระยะเผื่อตัดแต่งขอบ",
    "4. ชิ้นงานที่มีชื่อ Arcylic (อะคริลิก): เช่น Arcylic Cover Front, Arcylic Cover Right ให้ตรวจสอบว่าใช้แผ่นอะคริลิกใส หรือแผ่นคอมโพสิตทึบในการตัด"
]

for idx, tip in enumerate(bending_tips, 11):
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
