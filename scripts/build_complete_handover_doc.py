r"""
Script to generate the complete, unified Handover Document (หนังสือส่งมอบงาน)
for Narit Smart Vending Machine according to TOR J69-290.
Outputs both .docx and .pdf files directly into D:\37-Project Narit Vending Machine\Document

Professional Thai Typography & Engineering Standards:
- Standard A4 page size (210 x 297 mm)
- Official Thai Margins: Left 1.25 in (3.175 cm เผื่อเข้าเล่ม), Right 1.0 in, Top 1.0 in, Bottom 1.0 in
- Content Width = 6.02 inches (All tables, callouts, and drawings fit within 6.0 inches)
- Full-width distributed alignment (THAI_JUSTIFY / w:jc="thaiDistribute")
- Thai Paragraph First-Line Indent: 0.5 in (1.27 cm / 1 Thai tab)
- Official Cover Letter First-Line Indent: 1.0 in (2.5 cm standard Thai royal/government letter indent)
- Line Spacing: 1.18 multiple (optimal vertical breathing room, no vowel collision)
- Hanging Indents for bullet and numbered lists
- Table rows keep together (w:cantSplit) and repeat headers across pages (w:tblHeader)
- Images kept with their captions (keep_with_next)
- Clean section breaks before major technical chapters
- Zero orphan lines, zero blank pages, and single-page acceptance certificate with signatures!
"""

import os
import sys
import json
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from pythainlp.tokenize import word_tokenize

sys.stdout.reconfigure(encoding='utf-8')

# ---------------------------------------------------------------------------
# STYLING HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def insert_thai_breaks(text: str) -> str:
    """
    Inserts Zero-Width Spaces (\u200b) at Thai word boundaries using pythainlp.
    This enables Microsoft Word to perform accurate Thai word breaking,
    eliminating awkward character stretching and unsightly white gaps in justified text.
    """
    if not text or not any('\u0e00' <= c <= '\u0e7f' for c in text):
        return text
    tokens = word_tokenize(text, engine='newmm')
    res = []
    NO_BREAK_BEFORE = set(":;,.)!?%/\\]}>’”\"“”–— \t\n\u200bฯๆ")
    NO_BREAK_AFTER = set("([{\\<‘“\"”–— \t\n\u200b")
    for i, tok in enumerate(tokens):
        res.append(tok)
        if i < len(tokens) - 1:
            next_tok = tokens[i+1]
            if not tok.endswith(' ') and not next_tok.startswith(' '):
                if next_tok[0] not in NO_BREAK_BEFORE and tok[-1] not in NO_BREAK_AFTER:
                    has_thai = any('\u0e00' <= c <= '\u0e7f' for c in tok) or any('\u0e00' <= c <= '\u0e7f' for c in next_tok)
                    if has_thai:
                        res.append('\u200b')
    return ''.join(res)

def set_run_font(run, name='TH Sarabun New', size_pt=16, bold=False, italic=False, color_rgb=(30, 41, 59)):
    run.font.name = name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(*color_rgb)
    rPr = run._element.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), name)
    rFonts.set(qn('w:hAnsi'), name)
    rFonts.set(qn('w:eastAsia'), name)
    rFonts.set(qn('w:cs'), name)
    rPr.append(rFonts)
    if bold:
        bCs = OxmlElement('w:bCs')
        rPr.append(bCs)
    szCs = OxmlElement('w:szCs')
    szCs.set(qn('w:val'), str(int(size_pt * 2)))
    rPr.append(szCs)
    lang = parse_xml(f'<w:lang {nsdecls("w")} w:val="th-TH" w:eastAsia="th-TH" w:bidi="th-TH"/>')
    rPr.append(lang)

def set_cell_shading(cell, color_hex):
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{color_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    tblPr = table._element.xpath('w:tblPr')
    if tblPr:
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:left w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:insideV w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr[0].append(borders)

def apply_header_footer(section):
    # Header
    header = section.header
    header.is_linked_to_previous = False
    hp = header.paragraphs[0]
    hp.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hp.paragraph_format.first_line_indent = Pt(0)
    hrun = hp.add_run("หนังสือส่งมอบงานจ้างตามข้อกำหนดสัญญา TOR (ใบสั่งจ้างเลขที่ J69/290 | เลขคุมสัญญา 690714014761) | NARIT Smart Vending Machine")
    set_run_font(hrun, size_pt=10, color_rgb=(148, 163, 184), italic=True)
    
    # Footer
    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.first_line_indent = Pt(0)
    frun = fp.add_run("สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน) — ศูนย์ปฏิบัติการหอดูดาวและวิศวกรรม")
    set_run_font(frun, size_pt=10, color_rgb=(148, 163, 184))

def add_h1(doc, text, space_before=14, space_after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.first_line_indent = Pt(0)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, size_pt=18, bold=True, color_rgb=(30, 58, 138)) # Navy Blue
    return p

def add_h2(doc, text, space_before=11, space_after=3):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.first_line_indent = Pt(0)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, size_pt=16, bold=True, color_rgb=(15, 23, 42)) # Slate Navy
    return p

def add_h3(doc, text, space_before=8, space_after=2):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.first_line_indent = Pt(0)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, size_pt=15, bold=True, color_rgb=(51, 65, 85)) # Slate
    return p

def add_body(doc, text, bold_prefix=None, indent=0.0, first_line_indent=0.5, align_justify=True, space_before=2, space_after=3, line_spacing=1.16):
    ret_p = None
    
    # If bold_prefix ends with newline, output it as an independent subheading line
    # to prevent Word from stretching it across the whole width of the page
    if bold_prefix and bold_prefix.endswith('\n'):
        p_pre = doc.add_paragraph()
        p_pre.paragraph_format.space_before = Pt(space_before + 3)
        p_pre.paragraph_format.space_after = Pt(2)
        p_pre.paragraph_format.first_line_indent = Pt(0)
        p_pre.paragraph_format.keep_with_next = True
        p_pre.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_pre = p_pre.add_run(insert_thai_breaks(bold_prefix.strip()))
        set_run_font(r_pre, size_pt=16, bold=True, color_rgb=(15, 23, 42))
        bold_prefix = None

    # Split text into lines/paragraphs so intermediate newlines never cause stretched text
    raw_lines = [l.strip() for l in text.split('\n') if l.strip()]
    for idx, line in enumerate(raw_lines):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(space_before if idx == 0 else 1)
        p.paragraph_format.space_after = Pt(space_after if idx == len(raw_lines) - 1 else 2)
        p.paragraph_format.line_spacing = line_spacing
        
        # Check if this line is a numbered sub-item like "1. ", "2. "
        is_sub_item = (len(line) > 2 and line[0].isdigit() and line[1] in ['.', ')']) or line.startswith('• ')
        
        if is_sub_item:
            p.paragraph_format.left_indent = Inches(0.4)
            p.paragraph_format.first_line_indent = Pt(0)
            if align_justify:
                p.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        else:
            if indent > 0:
                p.paragraph_format.left_indent = Inches(indent)
                p.paragraph_format.first_line_indent = Pt(0)
            elif first_line_indent > 0:
                p.paragraph_format.first_line_indent = Inches(first_line_indent)
            else:
                p.paragraph_format.first_line_indent = Pt(0)
            
            if align_justify:
                p.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            
        if idx == 0 and bold_prefix:
            r_pre = p.add_run(insert_thai_breaks(bold_prefix))
            set_run_font(r_pre, size_pt=16, bold=True, color_rgb=(15, 23, 42))
        
        r_txt = p.add_run(insert_thai_breaks(line))
        set_run_font(r_txt, size_pt=16, bold=False, color_rgb=(30, 41, 59))
        if ret_p is None:
            ret_p = p
    return ret_p

def add_bullet(doc, text, bold_prefix=None, level=0, space_before=1, space_after=2, line_spacing=1.16):
    p = doc.add_paragraph(style='List Bullet' if level==0 else 'List Bullet 2')
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    p.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
    
    # Hanging Indents for neat bullet alignment
    if level == 0:
        p.paragraph_format.left_indent = Inches(0.4)
        p.paragraph_format.first_line_indent = -Inches(0.25)
    else:
        p.paragraph_format.left_indent = Inches(0.7)
        p.paragraph_format.first_line_indent = -Inches(0.25)
        
    if bold_prefix:
        r_pre = p.add_run(insert_thai_breaks(bold_prefix))
        set_run_font(r_pre, size_pt=16, bold=True, color_rgb=(15, 23, 42))
        
    r_txt = p.add_run(insert_thai_breaks(text))
    set_run_font(r_txt, size_pt=16, bold=False, color_rgb=(30, 41, 59))
    return p

def add_image_caption(doc, img_path, caption_text, width=Inches(5.5), space_before=6, space_after=6):
    if not os.path.exists(img_path):
        print(f"ERROR: Image not found: {img_path}")
        return None
    p_img = doc.add_paragraph()
    p_img.paragraph_format.space_before = Pt(space_before)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.first_line_indent = Pt(0)
    p_img.paragraph_format.keep_with_next = True
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_img = p_img.add_run()
    run_img.add_picture(img_path, width=width)
    
    p_cap = doc.add_paragraph()
    p_cap.paragraph_format.space_before = Pt(2)
    p_cap.paragraph_format.space_after = Pt(space_after)
    p_cap.paragraph_format.first_line_indent = Pt(0)
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_cap = p_cap.add_run(insert_thai_breaks(caption_text))
    set_run_font(run_cap, size_pt=13, bold=True, italic=True, color_rgb=(71, 85, 105))
    return p_img

def add_styled_table(doc, headers, rows_data, col_widths=None, font_size_data=13, cell_top=60, cell_bot=60):
    table = doc.add_table(rows=len(rows_data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    # Repeat header row on every page
    header_tr = table.rows[0]._element.get_or_add_trPr()
    header_tr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
    
    # Prevent rows from breaking across pages
    for row in table.rows:
        trPr = row._element.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
    
    # Header row
    hdr_cells = table.rows[0].cells
    for i, h_text in enumerate(headers):
        hdr_cells[i].text = insert_thai_breaks(h_text)
        set_cell_shading(hdr_cells[i], "1E3A8A") # Navy Blue
        set_cell_margins(hdr_cells[i], top=90, bottom=90, left=110, right=110)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.first_line_indent = Pt(0)
        set_run_font(p.runs[0], size_pt=13.5, bold=True, color_rgb=(255, 255, 255))
        
    # Data rows
    for r_idx, row_values in enumerate(rows_data):
        row_cells = table.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_values):
            row_cells[c_idx].text = insert_thai_breaks(str(val))
            set_cell_shading(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=cell_top, bottom=cell_bot, left=100, right=100)
            p = row_cells[c_idx].paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.1
            p.paragraph_format.first_line_indent = Pt(0)
            if len(str(val)) <= 6 or c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_run_font(p.runs[0], size_pt=font_size_data, color_rgb=(30, 41, 59))
            
    # Apply column widths
    if col_widths:
        for row in table.rows:
            for c_idx, w in enumerate(col_widths):
                row.cells[c_idx].width = w
                
    set_table_borders(table, color="CBD5E1", sz="4", val="single")
    return table

def add_callout(doc, text, bold_title=None):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.0) # Matches exactly with content width
    set_cell_shading(cell, "F1F5F9")
    set_cell_margins(cell, top=90, bottom=90, left=150, right=150)
    
    tcPr = cell._element.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="2563EB"/>'
        f'<w:top w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    if bold_title:
        p_t = cell.paragraphs[0]
        p_t.paragraph_format.space_before = Pt(2)
        p_t.paragraph_format.space_after = Pt(2)
        p_t.paragraph_format.line_spacing = 1.15
        p_t.paragraph_format.first_line_indent = Pt(0)
        p_t.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_t = p_t.add_run(insert_thai_breaks(bold_title))
        set_run_font(r_t, size_pt=15, bold=True, color_rgb=(30, 58, 138))
        p_b = cell.add_paragraph()
    else:
        p_b = cell.paragraphs[0]
        
    p_b.paragraph_format.space_before = Pt(2)
    p_b.paragraph_format.space_after = Pt(2)
    p_b.paragraph_format.line_spacing = 1.16
    p_b.paragraph_format.first_line_indent = Pt(0)
    p_b.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
    r_b = p_b.add_run(insert_thai_breaks(text))
    set_run_font(r_b, size_pt=15, color_rgb=(51, 65, 85))

# ---------------------------------------------------------------------------
# MAIN BUILDER
# ---------------------------------------------------------------------------

def generate_handover_document(output_docx_path):
    print("Generating comprehensive Handover Document with EXACT image verification...")
    doc = docx.Document()
    
    media_dir = r"C:\Users\Naruebest\.gemini\antigravity\brain\0418e452-5702-4e54-9804-766d0362af50\scratch\exact_media"
    draw_dir = r"C:\Users\Naruebest\.gemini\antigravity\brain\0418e452-5702-4e54-9804-766d0362af50\scratch\drawing_pages"
    bom_json_path = r"C:\Users\Naruebest\.gemini\antigravity\brain\0418e452-5702-4e54-9804-766d0362af50\scratch\bom_items.json"
    
    with open(bom_json_path, 'r', encoding='utf-8') as f:
        bom_data = json.load(f)

    # =========================================================================
    # SECTION 1: หนังสือนำส่งมอบงาน (OFFICIAL COVER LETTER - EXACT 1 PAGE)
    # =========================================================================
    sec1 = doc.sections[0]
    sec1.page_width = Inches(8.27)
    sec1.page_height = Inches(11.69)
    sec1.top_margin = Inches(0.8)
    sec1.bottom_margin = Inches(0.8)
    sec1.left_margin = Inches(1.25)
    sec1.right_margin = Inches(1.0)
    sec1.header.is_linked_to_previous = False
    sec1.footer.is_linked_to_previous = False

    p_top_title = doc.add_paragraph()
    p_top_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_top_title.paragraph_format.space_before = Pt(0)
    p_top_title.paragraph_format.space_after = Pt(4)
    p_top_title.paragraph_format.first_line_indent = Pt(0)
    r_tt = p_top_title.add_run("ใบส่งมอบงาน")
    set_run_font(r_tt, size_pt=24, bold=True, color_rgb=(15, 23, 42))

    tbl_letter_meta = doc.add_table(rows=2, cols=2)
    tbl_letter_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_letter_meta.autofit = False
    tbl_letter_meta.rows[0].cells[0].width = Inches(2.8)
    tbl_letter_meta.rows[0].cells[1].width = Inches(3.2)
    tbl_letter_meta.rows[1].cells[0].width = Inches(2.8)
    tbl_letter_meta.rows[1].cells[1].width = Inches(3.2)

    c00 = tbl_letter_meta.cell(0, 0).paragraphs[0]
    c10 = tbl_letter_meta.cell(1, 0).paragraphs[0]
    c01 = tbl_letter_meta.cell(0, 1).paragraphs[0]
    c11 = tbl_letter_meta.cell(1, 1).paragraphs[0]

    c00.alignment = WD_ALIGN_PARAGRAPH.LEFT
    c10.alignment = WD_ALIGN_PARAGRAPH.LEFT
    c01.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    c11.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    c00.paragraph_format.space_before = Pt(0)
    c00.paragraph_format.space_after = Pt(0)
    c10.paragraph_format.space_before = Pt(0)
    c10.paragraph_format.space_after = Pt(0)
    c01.paragraph_format.space_before = Pt(0)
    c01.paragraph_format.space_after = Pt(0)
    c11.paragraph_format.space_before = Pt(0)
    c11.paragraph_format.space_after = Pt(0)

    c00.paragraph_format.first_line_indent = Pt(0)
    c10.paragraph_format.first_line_indent = Pt(0)
    c01.paragraph_format.first_line_indent = Pt(0)
    c11.paragraph_format.first_line_indent = Pt(0)

    r = c00.add_run("ที่   J69/290 (คุมสัญญา 690714014761)")
    set_run_font(r, size_pt=15.5, bold=True, color_rgb=(15, 23, 42))
    r = c10.add_run("เลขที่โครงการ 69079014721")
    set_run_font(r, size_pt=13, color_rgb=(71, 85, 105))

    r = c01.add_run("เขียนที่  สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน)")
    set_run_font(r, size_pt=15.5, color_rgb=(15, 23, 42))
    r = c11.add_run("วันที่  17  กันยายน  พ.ศ.  2569")
    set_run_font(r, size_pt=15.5, color_rgb=(15, 23, 42))

    p_subj = doc.add_paragraph()
    p_subj.paragraph_format.space_before = Pt(2)
    p_subj.paragraph_format.space_after = Pt(2)
    p_subj.paragraph_format.first_line_indent = Pt(0)
    r1 = p_subj.add_run("เรื่อง   ")
    set_run_font(r1, size_pt=15.5, bold=True, color_rgb=(15, 23, 42))
    r2 = p_subj.add_run("ส่งมอบงานจ้างและขออนุมัติเบิกจ่ายเงินค่าจ้าง")
    set_run_font(r2, size_pt=15.5, bold=True, color_rgb=(30, 58, 138))

    p_to = doc.add_paragraph()
    p_to.paragraph_format.space_before = Pt(2)
    p_to.paragraph_format.space_after = Pt(2)
    p_to.paragraph_format.first_line_indent = Pt(0)
    r1 = p_to.add_run("เรียน   ")
    set_run_font(r1, size_pt=15.5, bold=True, color_rgb=(15, 23, 42))
    r2 = p_to.add_run("ประธานคณะกรรมการตรวจรับพัสดุ สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน)")
    set_run_font(r2, size_pt=15.5, bold=False, color_rgb=(15, 23, 42))

    p_ref = doc.add_paragraph()
    p_ref.paragraph_format.space_before = Pt(2)
    p_ref.paragraph_format.space_after = Pt(4)
    p_ref.paragraph_format.first_line_indent = Pt(0)
    r1 = p_ref.add_run("อ้างถึง  ")
    set_run_font(r1, size_pt=15.5, bold=True, color_rgb=(15, 23, 42))
    r2 = p_ref.add_run("ใบสั่งจ้างเลขที่ J69/290 (เลขที่โครงการ 69079014721, เลขคุมสัญญา 690714014761) ลงวันที่ 1 กรกฎาคม 2569")
    set_run_font(r2, size_pt=15.5, bold=False, color_rgb=(51, 65, 85))

    p_body1 = doc.add_paragraph()
    p_body1.paragraph_format.left_indent = Pt(0)
    p_body1.paragraph_format.first_line_indent = Inches(1.0) # 2.5 cm standard Thai royal/government letter indent
    p_body1.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
    p_body1.paragraph_format.space_before = Pt(2)
    p_body1.paragraph_format.space_after = Pt(3)
    p_body1.paragraph_format.line_spacing = 1.12
    r_b1 = p_body1.add_run(
        insert_thai_breaks(
            "ตามที่ สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน) ได้ตกลงให้ข้าพเจ้า นายปพน แซ่จ๊ะ "
            "ที่อยู่ 197 หมู่ 6 ตำบลปากกลาง อำเภอปัว จังหวัดน่าน 55120 ดำเนินการจ้างออกแบบชั้นเก็บและจ่ายอุปกรณ์อิเล็กทรอนิกส์อัตโนมัติ "
            "(Auto Electronic Parts Box) / เครื่องจำหน่ายสินค้าอัตโนมัติ (NARIT Smart Vending Machine) สำหรับบรรจุภัณฑ์รูปทรงสี่เหลี่ยม จำนวน 1 งาน "
            "ตามใบสั่งจ้างเลขที่ J69/290 (เลขที่โครงการ 69079014721, เลขคุมสัญญา 690714014761) ลงวันที่ 1 กรกฎาคม 2569 ในวงเงินงบประมาณค่าจ้างทั้งสิ้น 90,000.00 บาท (เก้าหมื่นบาทถ้วน) นั้น"
        )
    )
    set_run_font(r_b1, size_pt=15.5, color_rgb=(30, 41, 59))

    p_body2 = doc.add_paragraph()
    p_body2.paragraph_format.left_indent = Pt(0)
    p_body2.paragraph_format.first_line_indent = Inches(1.0)
    p_body2.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
    p_body2.paragraph_format.space_before = Pt(2)
    p_body2.paragraph_format.space_after = Pt(3)
    p_body2.paragraph_format.line_spacing = 1.12
    r_b2 = p_body2.add_run(
        insert_thai_breaks(
            "บัดนี้ ข้าพเจ้าได้ดำเนินการปฏิบัติงานจ้างออกแบบดังกล่าวเสร็จสิ้นเรียบร้อยสมบูรณ์ ถูกต้องครบถ้วนตามขอบเขตและเงื่อนไขแห่งข้อกำหนดของสถาบันฯ (TOR) "
            "ทุกประการ โดยได้รวบรวมรายละเอียดผลงานการออกแบบทั้งหมด ทั้งแบบร่าง 3 รูปแบบ (Versions), ภาพจำลอง 3 มิติ (3D Rendering), "
            "แบบจำลอง 3D CAD Model ฉบับสมบูรณ์, แบบวาดทางวิศวกรรมฉบับสมบูรณ์ (Production Drawing), รายการวัสดุและชิ้นส่วน (Bill of Materials : BOM), "
            "เอกสารอธิบายหลักการทำงานของระบบย่อยแต่ละระบบ (System Description Document), แบบวงจรไฟฟ้าและแผนผังการเดินสาย (Electrical Schematic & Wiring Diagram) "
            "ตลอดจนเอกสารข้อกำหนดการเชื่อมต่อระบบ (Interface Specification Document) บรรจุไว้ในเอกสารหนังสือส่งมอบงานฉบับสมบูรณ์นี้อย่างครบถ้วนในเล่มเดียว โดยไม่มีส่วนแยกแนบภายนอก"
        )
    )
    set_run_font(r_b2, size_pt=15.5, color_rgb=(30, 41, 59))

    p_body3 = doc.add_paragraph()
    p_body3.paragraph_format.left_indent = Pt(0)
    p_body3.paragraph_format.first_line_indent = Inches(1.0)
    p_body3.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
    p_body3.paragraph_format.space_before = Pt(2)
    p_body3.paragraph_format.space_after = Pt(6)
    p_body3.paragraph_format.line_spacing = 1.12
    r_b3 = p_body3.add_run(
        insert_thai_breaks(
            "จึงเรียนมาเพื่อโปรดดำเนินการตรวจรับงานจ้าง และอนุมัติการเบิกจ่ายเงินค่าจ้าง จำนวน 90,000.00 บาท (เก้าหมื่นบาทถ้วน) ให้แก่ข้าพเจ้าต่อไป"
        )
    )
    set_run_font(r_b3, size_pt=15.5, color_rgb=(30, 41, 59))

    p_close = doc.add_paragraph()
    p_close.paragraph_format.left_indent = Inches(3.0)
    p_close.paragraph_format.first_line_indent = Pt(0)
    p_close.paragraph_format.space_before = Pt(6)
    p_close.paragraph_format.space_after = Pt(10)
    r_cl = p_close.add_run("ขอแสดงความนับถือ")
    set_run_font(r_cl, size_pt=15.5, color_rgb=(15, 23, 42))

    p_sig = doc.add_paragraph()
    p_sig.paragraph_format.left_indent = Inches(3.0)
    p_sig.paragraph_format.first_line_indent = Pt(0)
    p_sig.paragraph_format.space_before = Pt(0)
    p_sig.paragraph_format.space_after = Pt(0)
    r_s1 = p_sig.add_run("ลงชื่อ............................................................ผู้รับจ้าง\n")
    set_run_font(r_s1, size_pt=15, color_rgb=(15, 23, 42))
    r_s2 = p_sig.add_run("       ( นายปพน  แซ่จ๊ะ )\n")
    set_run_font(r_s2, size_pt=15, bold=True, color_rgb=(15, 23, 42))
    r_s3 = p_sig.add_run("          ผู้รับจ้าง / ผู้ปฏิบัติงาน")
    set_run_font(r_s3, size_pt=14.5, color_rgb=(71, 85, 105))

    # =========================================================================
    # SECTION 2: หน้าปกและข้อมูลควบคุมเอกสารรายงาน (REPORT TITLE BLOCK - EXACT 1 PAGE)
    # =========================================================================
    sec2 = doc.add_section()
    sec2.page_width = Inches(8.27)
    sec2.page_height = Inches(11.69)
    sec2.top_margin = Inches(0.8)
    sec2.bottom_margin = Inches(0.8)
    sec2.left_margin = Inches(1.25)
    sec2.right_margin = Inches(1.0)
    sec2.header.is_linked_to_previous = False
    sec2.footer.is_linked_to_previous = False

    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(0)
    p_inst.paragraph_format.space_after = Pt(2)
    p_inst.paragraph_format.first_line_indent = Pt(0)
    r_ins = p_inst.add_run("สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน)")
    set_run_font(r_ins, size_pt=19, bold=True, color_rgb=(30, 58, 138))

    p_dept = doc.add_paragraph()
    p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_dept.paragraph_format.space_before = Pt(0)
    p_dept.paragraph_format.space_after = Pt(6)
    p_dept.paragraph_format.first_line_indent = Pt(0)
    r_dep = p_dept.add_run("ศูนย์ปฏิบัติการหอดูดาวและวิศวกรรม | ห้องปฏิบัติการเทคโนโลยีเมคาทรอนิกส์")
    set_run_font(r_dep, size_pt=14, italic=True, color_rgb=(71, 85, 105))

    p_rtitle = doc.add_paragraph()
    p_rtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_rtitle.paragraph_format.space_before = Pt(2)
    p_rtitle.paragraph_format.space_after = Pt(2)
    p_rtitle.paragraph_format.first_line_indent = Pt(0)
    r_rt = p_rtitle.add_run("รายงานผลงานส่งมอบงานจ้างออกแบบฉบับสมบูรณ์ (รวมเล่มเดียว)\n(Comprehensive Final Deliverables Report)")
    set_run_font(r_rt, size_pt=19, bold=True, color_rgb=(15, 23, 42))

    p_rproj = doc.add_paragraph()
    p_rproj.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_rproj.paragraph_format.space_before = Pt(2)
    p_rproj.paragraph_format.space_after = Pt(6)
    p_rproj.paragraph_format.first_line_indent = Pt(0)
    r_rp = p_rproj.add_run("งานจัดจ้างออกแบบเครื่องจำหน่ายสินค้าอัตโนมัติ (NARIT Smart Vending Machine)\nสำหรับบรรจุภัณฑ์รูปทรงสี่เหลี่ยม จำนวน 1 งาน ตามข้อกำหนด TOR (ใบสั่งจ้างเลขที่ J69/290 | เลขคุมสัญญา 690714014761)")
    set_run_font(r_rp, size_pt=15, bold=True, color_rgb=(30, 58, 138))

    # COVER IMAGE: image4.png (3D CAD Model Overview)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image4.png"),
        "ภาพจำลอง 3 มิติ (3D CAD Model) ฉบับสมบูรณ์ โครงสร้างตู้จำหน่ายสินค้าอัตโนมัติ NARIT Smart Vending Machine",
        width=Inches(3.2),
        space_before=2,
        space_after=4
    )

    p_tbl_lbl = doc.add_paragraph()
    p_tbl_lbl.paragraph_format.space_before = Pt(4)
    p_tbl_lbl.paragraph_format.space_after = Pt(2)
    p_tbl_lbl.paragraph_format.first_line_indent = Pt(0)
    r_tl = p_tbl_lbl.add_run("ตารางข้อมูลการควบคุมเอกสาร (Document Control)")
    set_run_font(r_tl, size_pt=13.5, bold=True, color_rgb=(30, 58, 138))

    doc_ctrl_headers = ["รายการข้อมูล", "รายละเอียด"]
    doc_ctrl_rows = [
        ["ชื่อเอกสาร", "รายงานผลงานส่งมอบงานจ้างออกแบบฉบับสมบูรณ์ตามข้อกำหนด TOR (รวมเล่มเดียว)"],
        ["เลขที่เอกสารอ้างอิง", "NARIT-VEND-J69-290-DELIVERABLE-REV-FINAL"],
        ["เลขที่ใบสั่งจ้าง / สัญญา", "ใบสั่งจ้างเลขที่ J69/290 (เลขที่โครงการ 69079014721, เลขคุมสัญญา 690714014761) ลงวันที่ 1 กรกฎาคม 2569"],
        ["ผู้รับจ้าง / ผู้ออกแบบ", "นายปพน แซ่จ๊ะ (ที่อยู่ 197 หมู่ 6 ต.ปากกลาง อ.ปัว จ.น่าน 55120 | เลขประจำตัวผู้เสียภาษี 1559200013326)"],
        ["หน่วยงานเจ้าของโครงการ", "ศูนย์ปฏิบัติการหอดูดาวและวิศวกรรม สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน)"],
        ["วงเงินงบประมาณค่าจ้าง", "90,000.00 บาท (เก้าหมื่นบาทถ้วน)"],
        ["สถานะเอกสาร", "ฉบับสมบูรณ์สำหรับตรวจรับพัสดุ (Final Approved Deliverable - Single Volume)"]
    ]
    add_styled_table(doc, doc_ctrl_headers, doc_ctrl_rows, [Inches(1.9), Inches(4.1)], font_size_data=11.5, cell_top=45, cell_bot=45)

    # =========================================================================
    # SECTION 3: เนื้อหารายงานจัดเรียงตามเลขข้อของ TOR (BODY CONTENT)
    # =========================================================================
    sec3 = doc.add_section()
    sec3.page_width = Inches(8.27)
    sec3.page_height = Inches(11.69)
    sec3.top_margin = Inches(1.0)
    sec3.bottom_margin = Inches(1.0)
    sec3.left_margin = Inches(1.25)
    sec3.right_margin = Inches(1.0)
    apply_header_footer(sec3)

    # -------------------------------------------------------------------------
    # ข้อ 4. ขอบเขตของงานที่จะดำเนินการจัดจ้าง (Scope of Work)
    # -------------------------------------------------------------------------
    add_h1(doc, "4. ขอบเขตของงานที่จะดำเนินการจัดจ้าง (Scope of Work)", space_before=12, space_after=4)
    
    # 4.1 เงื่อนไขและคุณลักษณะทั่วไป
    add_h2(doc, "4.1 เงื่อนไขและคุณลักษณะทั่วไปของเครื่อง NARIT Smart Vending Machine")
    
    add_h3(doc, "4.1.1 คุณลักษณะทั่วไปและการรองรับกล่องบรรจุภัณฑ์มาตรฐาน 3 ขนาด")
    add_body(doc,
        "เครื่องจำหน่ายสินค้าอัตโนมัติได้รับการออกแบบทางวิศวกรรมให้สามารถจัดเก็บ ขนส่ง และจ่ายสินค้าในรูปแบบกล่องบรรจุภัณฑ์ทรงสี่เหลี่ยม "
        "ขนาดมาตรฐานจำนวน 3 ขนาด ได้แก่ ขนาด 2A, 2B และ D ได้อย่างสมบูรณ์ โดยมีรายละเอียดมิติขนาด (กว้าง x ยาว x สูง) ดังนี้:"
    )
    add_body(doc,
        "กล่องขนาดมาตรฐาน กว้าง 140 มม. x ยาว 200 มม. x สูง 60 มม. (หรือขนาดมาตรฐาน 14 x 20 x 12 ซม.) "
        "เหมาะสำหรับสินค้าของที่ระลึกขนาดเล็ก เช่น พวงกุญแจ, แผ่นอะคริลิก, เข็มกลัด หรือชิ้นส่วนอุปกรณ์อิเล็กทรอนิกส์",
        bold_prefix="กล่องเบอร์ 2A: ", first_line_indent=0.5, space_before=1, space_after=2
    )
    add_body(doc,
        "กล่องขนาดมาตรฐาน กว้าง 170 มม. x ยาว 250 มม. x สูง 90 มม. (หรือขนาดมาตรฐาน 17 x 25 x 18 ซม.) "
        "เหมาะสำหรับสินค้าขนาดกลาง เช่น เสื้อยืดที่ระลึก, หนังสือดาราศาสตร์, โมเดลดาวเคราะห์ หรือแก้วน้ำ",
        bold_prefix="กล่องเบอร์ 2B: ", first_line_indent=0.5, space_before=1, space_after=2
    )
    add_body(doc,
        "กล่องขนาดมาตรฐาน กว้าง 220 มม. x ยาว 350 มม. x สูง 140 มม. (หรือขนาดมาตรฐาน 22 x 35 x 14 ซม.) "
        "เหมาะสำหรับสินค้าขนาดใหญ่ เช่น โมเดลกล้องโทรทรรศน์, ร่มพับดาราศาสตร์ หรือเซ็ตของขวัญพิเศษ",
        bold_prefix="กล่องเบอร์ D: ", first_line_indent=0.5, space_before=1, space_after=3
    )

    # IMAGE: image6.png (กล่อง 2A, 2B, D และการจัดเรียงบนชั้นวาง)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image6.png"),
        "ภาพขนาดมิติของกล่องบรรจุภัณฑ์มาตรฐานทั้ง 3 ขนาด (2A, 2B, D) และการจัดวางบนชั้นวางสินค้า",
        width=Inches(5.0)
    )

    add_h3(doc, "4.1.2 การออกแบบโครงสร้างชั้นวางและกลไกให้ใช้งานร่วมกับกล่องบรรจุภัณฑ์")
    add_body(doc,
        "การออกแบบชั้นวางสินค้าใช้เทคโนโลยี ชั้นวางแบบลาดเอียงอาศัยแรงโน้มถ่วง (Gravity-Fed Sloped Shelves) ทำมุมลาดเอียง 25 องศา (25°) "
        "กับแนวระนาบ โดยเป็นมุมที่ผ่านการทดสอบและปรับจูนทางวิศวกรรมแล้วว่า ช่วยให้กล่องสินค้าไหลเลื่อนลงมายังขอบด้านหน้าของรางได้อย่างนุ่มนวล "
        "สม่ำเสมอ และไม่กระแทกแรงจนเกิดความเสียหายต่อสินค้าภายใน ที่บริเวณขอบหน้าของแต่ละรางติดตั้งแผ่นกั้นอะลูมิเนียมขึ้นรูปทรง L (L-Plate) "
        "ความสูง 20 มม. เพื่อกักกล่องไม่ให้ไหลตก พร้อมเว้นระยะร่องเปิดตรงกลางและด้านข้าง เพื่อให้ชุดแผ่นช้อนของแกน Z (Carriage End-Effector) "
        "สามารถสอดแทรกเข้าใต้กล่องสินค้าและยกกล่องข้ามแนวแผ่นกั้นได้อย่างแม่นยำ"
    )

    # IMAGE: image5.png (ชั้นวางลาดเอียง 25 องศา)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image5.png"),
        "ภาพโครงสร้างชั้นวางสินค้าแบบลาดเอียง 25 องศา (Gravity-Fed Sloped Shelves) พร้อมแผ่นกั้นขอบหน้าและช่องสอดแผ่นช้อน",
        width=Inches(2.7),
        space_before=2,
        space_after=2
    )

    add_body(doc,
        "โครงสร้างตู้มีขนาดความกว้างภายในสำหรับติดตั้งชั้นวาง 1,480 มม. ลึก 700 มม. และสูง 2,200 มม. โดยแบ่งระดับชั้นวางสินค้าออกเป็น 7-8 ชั้น "
        "ซึ่งสามารถรองรับการจัดวางกล่องบรรจุภัณฑ์ได้ทั้งสิ้น 127 กล่อง โดยมีรายละเอียดการจัดสรรพื้นที่ชั้นวาง ดังนี้:",
        bold_prefix="การคำนวณความจุสินค้า: ",
        space_before=1, space_after=2, line_spacing=1.14
    )
    
    cap_headers = ["ประเภทกล่อง", "ขนาดมิติ (กว้าง x ยาว x สูง)", "จำนวนชั้นวาง", "แถวต่อชั้น x กล่องต่อแถว", "ความจุรวม"]
    cap_rows = [
        ["กล่องเบอร์ 2A (เล็ก)", "140 x 200 x 60 mm", "2 ชั้น", "ชั้นละ 6 แถว แถวละ 5 กล่อง", "60 กล่อง"],
        ["กล่องเบอร์ 2B (กลาง)", "170 x 250 x 90 mm", "2 ชั้น", "ชั้นละ 5 แถว แถวละ 4 กล่อง", "40 กล่อง"],
        ["กล่องเบอร์ D (ใหญ่)", "220 x 350 x 140 mm", "3 ชั้น", "ชั้นละ 3 แถว แถวละ 3 กล่อง", "27 กล่อง"],
        ["รวมทั้งสิ้น", "รองรับกล่องมาตรฐาน 3 ขนาด", "7-8 ระดับชั้น", "จัดสรรแบบโมดูลาร์ยืดหยุ่น", "127 กล่อง"]
    ]
    add_styled_table(doc, cap_headers, cap_rows, [Inches(1.2), Inches(1.5), Inches(0.85), Inches(1.45), Inches(1.0)])

    add_h3(doc, "4.1.3 ระบบชำระเงิน (Payment System)")
    add_body(doc,
        "เครื่องจำหน่ายสินค้าอัตโนมัติได้รับการออกแบบระบบชำระเงินให้รองรับการชำระเงินผ่านระบบอิเล็กทรอนิกส์ (QR Code Payment) "
        "บนโทรศัพท์มือถือของผู้ซื้อ เป็นช่องทางหลักเพียงช่องทางเดียว โดยไม่มีระบบรับเงินสด (100% Cashless System) ซึ่งให้ประโยชน์สำคัญคือ:"
    )
    add_bullet(doc, "ลดปัญหาเชิงกลจากการติดขัดของหัวรับธนบัตรและเครื่องทอนเหรียญ ซึ่งเป็นสาเหตุหลักของปัญหาขัดข้องในตู้จำหน่ายสินค้าทั่วไป", bold_prefix="1) ความน่าเชื่อถือสูงสุด: ")
    add_bullet(doc, "ตัดความเสี่ยงด้านการสูญหาย การโจรกรรมเงินสด หรือปัญหาเงินทอนไม่เพียงพอ", bold_prefix="2) ความปลอดภัยของทรัพย์สิน: ")
    add_bullet(doc, "ระบบชำระเงินเชื่อมต่อกับ Web Application และระบบ Payment Gateway ทางการเงินโดยตรง ทำให้ตรวจสอบยอดเงินและตัดสต็อกได้แบบเรียลไทม์", bold_prefix="3) ความโปร่งใสทางบัญชี: ")

    add_h3(doc, "4.1.4 ระบบสั่งสินค้าผ่าน Web Application (Mobile Web Application Ordering System)")
    add_body(doc,
        "เพื่อความทันสมัย ความทนทาน และการประหยัดพลังงาน ตัวเครื่องได้รับการออกแบบภายใต้สถาปัตยกรรม Displayless Machine "
        "โดยไม่มีหน้าจอแสดงผลขนาดใหญ่ติดตั้งอยู่ภายนอกตัวเครื่อง เพื่อลดจุดชำรุดเสียหายจากการสัมผัสภายนอก (Vandalism Protection) "
        "ผู้ซื้อสินค้าสามารถเข้าถึงระบบได้โดยใช้กล้องโทรศัพท์มือถือสแกนคิวอาร์โค้ดประจำตู้ (Station QR Code) เพื่อเปิดใช้งาน Mobile Web Application "
        "ผ่านเว็บเบราว์เซอร์บนสมาร์ตโฟนได้ทันที โดยไม่ต้องดาวน์โหลดแอปพลิเคชันเพิ่มเติม"
    )
    add_body(doc,
        "กระบวนการสั่งซื้อผ่าน Web Application ประกอบด้วย 3 ขั้นตอนหลัก:\n"
        "1. การเลือกสินค้า: แสดงรายการสินค้าที่พร้อมจำหน่าย รูปภาพ รายละเอียด และราคา แบบเรียลไทม์\n"
        "2. การชำระเงินออนไลน์: ระบบสร้าง Thai QR Payment (พร้อมเพย์) ให้ผู้ซื้อสแกนชำระเงินผ่าน Mobile Banking\n"
        "3. การรับรหัสรับสินค้า (Token): เมื่อระบบการเงินยืนยันยอดเงินสำเร็จ Web Application จะสร้างรหัสคิวอาร์โค้ดคำสั่งซื้อ (Order QR Token) "
        "แบบใช้ครั้งเดียว (Single-use Token) แสดงบนหน้าจอมือถือ เพื่อให้ผู้ซื้อนำไปสแกนที่หัวอ่าน Barcode/QR Scanner หน้าตู้เพื่อสั่งจ่ายสินค้า"
    )

    # IMAGE: image14.png (Mobile Web Mockup)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image14.png"),
        "ภาพจำลองส่วนต่อประสานผู้ใช้บนโทรศัพท์มือถือ (Mobile Web Application Mockup) หน้าเลือกสินค้าและหน้ารายละเอียดการสั่งซื้อ",
        width=Inches(4.2)
    )

    add_h3(doc, "4.1.5 ขนาดโดยรวมของตัวเครื่องและพื้นที่ใช้งาน (Overall Dimensions and Accessibility Areas)")
    add_body(doc,
        "ตามข้อกำหนด TOR ระบุให้ขนาดโดยรวมของตัวเครื่องอยู่ภายในขอบเขตพื้นที่ไม่เกิน กว้าง x ยาว x สูง = 2.5 x 6.0 x 2.5 เมตร "
        "ผลงานการออกแบบเครื่อง NARIT Smart Vending Machine มีขนาดมิติทางกายภาพจริงของตัวตู้ ดังนี้:"
    )
    add_bullet(doc, "ความกว้างรวมของตัวเครื่อง (Width): 1,465.00 มม. (1.465 เมตร)", bold_prefix="• ")
    add_bullet(doc, "ความลึกรวมของตัวเครื่อง (Depth): 1,006.92 มม. (1.007 เมตร)", bold_prefix="• ")
    add_bullet(doc, "ความสูงรวมของตัวเครื่อง (Height): 2,000.00 มม. (2.000 เมตร)", bold_prefix="• ")
    add_body(doc,
        "ซึ่งมิติรวมของตัวเครื่องมีขนาดกะทัดรัด ประหยัดพื้นที่จัดวาง โดยอยู่ภายในขอบเขตที่ TOR กำหนดไว้อย่างสมบูรณ์แบบ "
        "นอกจากนี้ โครงสร้างตัวตู้ได้รับการจัดสรรพื้นที่ภายในออกเป็น 3 เขตการทำงานอย่างเป็นสัดส่วน (Zoning Architecture):"
    )
    add_bullet(doc, "พื้นที่ติดตั้งแร็คชั้นวางสินค้าแบบเอียง 25 องศา ทั้ง 7-8 ชั้น บรรจุกล่องสินค้าได้ 127 กล่อง", bold_prefix="1) เขตชั้นวางสินค้า (Storage Zone): ")
    add_bullet(doc, "ช่องว่างระหว่างชั้นวางกับผนังหน้าตู้ สำหรับการเคลื่อนที่อย่างอิสระของชุดหุ่นยนต์ Cartesian Gantry 3 แกน", bold_prefix="2) เขตทางวิ่งกลไก (Motion Corridor): ")
    add_bullet(doc, "ตู้ควบคุมไฟฟ้าตามมาตรฐาน IP55 บริเวณด้านล่าง พร้อมช่องรับสินค้า (Product Delivery Port) และเซนเซอร์ตรวจจับของตก", bold_prefix="3) เขตควบคุมและช่องจ่ายสินค้า (Control & Delivery Zone): ")

    # IMAGE: image7.png (มิติตัวเครื่อง 1465 x 1006.92 x 2000 mm และ 3 โซน)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image7.png"),
        "ภาพแบบแปลนมิติตัวเครื่อง (กว้าง 1,465 มม. ลึก 1,006.92 มม. สูง 2,000 มม.) และการจัดสรรเขตพื้นที่ทำงานภายใน 3 โซน",
        width=Inches(4.8)
    )

    add_body(doc,
        "การออกแบบพื้นที่สำหรับการบำรุงรักษา (Maintenance Area) และการเติมสินค้า (Restock Area):\n"
        "ตัวตู้ได้รับการออกแบบฝาเปิดด้านหน้าแบบบานพับเปิดกว้าง 180 องศา และฝาข้างแบบปลดเร็ว (Quick-release Maintenance Panels) "
        "ทำให้เจ้าหน้าที่สามารถเข้าถึงชิ้นส่วนกลไก มอเตอร์ สายพาน และชุดตู้คอนโทรลได้อย่างสะดวก ปลอดภัย "
        "สำหรับการเติมสินค้า (Restocking) เจ้าหน้าที่สามารถดึงถาดชั้นวางออกมาจากด้านหน้าและเติมกล่องสินค้าเข้าสู่รางลาดเอียงได้อย่างรวดเร็ว "
        "โดยไม่ต้องรื้อถอนชิ้นส่วนกลไกขับเคลื่อนใด ๆ ทั้งสิ้น"
    )

    add_h3(doc, "4.1.6 ขอบเขตงานออกแบบระบบ (System Design Scope)")
    add_body(doc, "งานออกแบบเครื่องจำหน่ายสินค้าอัตโนมัติได้รับการออกแบบครอบคลุมครบถ้วนทั้ง 3 ระบบวิศวกรรมหลักตามที่ TOR กำหนด ได้แก่:")
    add_bullet(doc, "ครอบคลุมการออกแบบโครงสร้างตู้หลักด้วยอลูมิเนียมโปรไฟล์อุตสาหกรรม 40x40 มม., ระบบหุ่นยนต์พิกัดฉาก 3 แกนอิสระ (Cartesian Gantry X, Y, Z), ชุดตักสินค้า (Carriage End-Effector), โครงสร้างชั้นวางสินค้าแบบลาดเอียง, ประตูรับสินค้า และกลไกป้องกันสินค้าจ่ายซ้อน (Anti-Double Feed Mechanism)", bold_prefix="ก) ระบบเครื่องกล (Mechanical System): ")
    add_bullet(doc, "ครอบคลุมการออกแบบระบบจ่ายไฟหลัก 220VAC พร้อมระบบตัดวงจรป้องกัน, ระบบแปลงและจ่ายไฟกระแสตรงแยกบัสเด็ดขาด (60VDC สำหรับมอเตอร์กำลังสูง, 24VDC สำหรับระบบควบคุม/เซนเซอร์, 5VDC สำหรับสมองกลประมวลผล), บอร์ดควบคุมหลักคอมพิวเตอร์อุตสาหกรรม IRIV PiControl CM4, บอร์ดขยาย I/O, ไดรเวอร์ขับมอเตอร์สเต็ปเปอร์แบบวงปิด (Closed-Loop Stepper Drivers), เซนเซอร์แสงตรวจจับของตก (Photoelectric Drop Sensor), ลิมิตสวิตช์ความปลอดภัย 6 จุด และปุ่มหยุดฉุกเฉิน (Hardware E-Stop)", bold_prefix="ข) ระบบไฟฟ้าและอิเล็กทรอนิกส์ (Electrical & Electronics System): ")
    add_bullet(doc, "ครอบคลุมการเชื่อมต่อระหว่างตัวเครื่องกับ Web Application ผ่านระบบเครือข่าย IoT บนโพรโทคอล MQTT Broker และ REST API สถาปัตยกรรมแบบ Decoupled Architecture, ระบบรับข้อมูลคำสั่งซื้อและสแกนคิวอาร์โค้ด, ระบบตรวจสอบยืนยันความปลอดภัยแบบ Two-Phase Motion Token และการส่งข้อมูลสถานะการทำงาน (Telemetry) กลับสู่เซิร์ฟเวอร์แบบเรียลไทม์", bold_prefix="ค) ระบบสื่อสารและเชื่อมต่อ (Communication & Interface System): ")

    # 4.2 การออกแบบ 3 รูปแบบ (Design Concepts)
    add_h2(doc, "4.2 การออกแบบเครื่องจำหน่ายสินค้าอัตโนมัติ 3 รูปแบบ (Design Concepts)")
    add_body(doc,
        "เพื่อให้สอดคล้องกับข้อกำหนด TOR ข้อ 4.2 ผู้รับจ้างได้ดำเนินการศึกษาและออกแบบแนวคิดเครื่องจำหน่ายสินค้าอัตโนมัติออกเป็น "
        "3 รูปแบบ (Versions) ที่มีโครงสร้างทางวิศวกรรม กลไกการเคลื่อนที่ และรูปแบบการจัดวางพื้นที่ที่แตกต่างกัน "
        "โดยทั้ง 3 รูปแบบสามารถรองรับกล่องบรรจุภัณฑ์มาตรฐาน 2A, 2B และ D ได้ทั้งหมด และสะท้อนถึงภาพลักษณ์ความทันสมัย "
        "และนวัตกรรมทางวิศวกรรมชั้นสูงของ NARIT ดังนี้:"
    )

    # Concept 1
    add_body(doc, "แนวคิดการออกแบบ แบบที่ 1: ระบบมาตรฐาน (จุดจ่ายคงที่ / จ่ายทีละ 1 ชิ้นต่อรอบ Cycle) [แบบที่เลือกพัฒนาจริง]", bold_prefix="• ")
    add_body(doc,
        "การออกแบบระบบจัดเก็บและจ่ายสินค้าอัตโนมัติ โดยใช้สินค้าจัดเก็บบนชั้นวางลาดเอียง และใช้ชุดกลไก Cartesian Gantry 3 แกน (X, Y, Z) "
        "ร่วมกับชุดช้อนกล่อง (Carriage Fork) เป็นกลไกหลักในการเข้าถึงและนำสินค้าออกจากชั้นจัดเก็บ จากนั้นจึงลำเลียงสินค้ามายังจุดส่งมอบสินค้า "
        "(Product Delivery Station) บริเวณด้านล่างของตู้เพียงจุดเดียว การควบคุมการทำงานดำเนินการผ่านชุดประมวลผลกลาง เชื่อมต่อกับระบบสแกนคิวอาร์โค้ด "
        "เมื่อได้รับคำสั่งซื้อ ระบบจะคำนวณพิกัดเป้าหมายและเคลื่อนที่ไปรับสินค้า จ่ายครั้งละ 1 กล่องต่อหนึ่งรอบการทำงาน (Single Dispense Cycle) "
        "จุดเด่นคือโครงสร้างกลไกเรียบง่าย มีเสถียรภาพสูงสุด ดูแลรักษาง่าย และแม่นยำสูงต่อการติดตั้งเซนเซอร์ตรวจจับการตกของสินค้า"
    )
    # IMAGE: image1.png (Concept 1)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image1.png"),
        "ภาพจำลอง 3 มิติ แนวคิดการออกแบบ แบบที่ 1 : ระบบมาตรฐาน (จุดจ่ายคงที่ / จ่ายทีละ 1 ชิ้น) [แบบที่ได้รับคัดเลือก]",
        width=Inches(4.5)
    )

    # Concept 2
    add_body(doc, "แนวคิดการออกแบบ แบบที่ 2: ระบบเพิ่มชั้นพักจ่ายแบบเคลื่อนที่ (Mobile Delivery Shelf)", bold_prefix="• ")
    add_body(doc,
        "เป็นการพัฒนาระบบต่อยอดจากแบบที่ 1 โดยเพิ่มถาดพักสินค้าเคลื่อนที่ (Mobile Delivery Shelf) ติดตั้งควบคู่ไปกับชุดยก Carriage "
        "ทำให้จุดจ่ายสินค้าสามารถเคลื่อนที่ไปพร้อมกับชุดขับเคลื่อน และนำสินค้าไปส่งยังช่องเปิดรับสินค้าที่ระดับความสูงที่เหมาะสมกับสรีระของผู้ใช้งาน "
        "(Ergonomic Height Delivery) ได้หลากหลายระดับ ช่วยลดระยะทางและเวลาในการนำกล่องลงมาส่งที่ก้นตู้ แต่มีความซับซ้อนของกลไกและน้ำหนักบรรทุกของแกน Y เพิ่มขึ้น"
    )
    # IMAGE: image2.png (Concept 2)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image2.png"),
        "ภาพจำลอง 3 มิติ แนวคิดการออกแบบ แบบที่ 2 : ระบบเพิ่มชั้นพักจ่ายแบบเคลื่อนที่ (Mobile Delivery Shelf)",
        width=Inches(4.5)
    )

    # Concept 3
    add_body(doc, "แนวคิดการออกแบบ แบบที่ 3: ระบบโครงสร้างโปร่งใสและจ่ายหลายระดับ (Multi-level Transparent Enclosure System)", bold_prefix="• ")
    add_body(doc,
        "ออกแบบเป็นตู้โชว์โครงสร้างโปร่งใส Acrylic Enclosure รอบทิศทาง เพื่อให้ผู้เยี่ยมชมสามารถมองเห็นกลไกหุ่นยนต์และอุปกรณ์ดาราศาสตร์ภายในได้อย่างชัดเจน "
        "ติดตั้งชั้นวางแบบปรับระดับได้ และมีช่องส่งสินค้าหลายระดับ (Multi-level Dispense Doors) เพื่อเพิ่มความน่าสนใจในการจัดแสดงนิทรรศการ "
        "แต่มีต้นทุนการผลิตสูง และต้องมีระบบควบคุมความปลอดภัยของช่องจ่ายสินค้าหลายบานพร้อมกัน"
    )
    # IMAGE: image3.png (Concept 3)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image3.png"),
        "ภาพจำลอง 3 มิติ แนวคิดการออกแบบ แบบที่ 3 : ระบบโครงสร้างโปร่งใสและจ่ายหลายระดับ (Multi-level System)",
        width=Inches(4.5)
    )

    add_body(doc, "ตารางการวิเคราะห์เปรียบเทียบแนวคิดการออกแบบทั้ง 3 รูปแบบ (Concept Evaluation Matrix):", bold_prefix="การประเมินผลแนวคิด: ")
    eval_headers = ["เกณฑ์การประเมินทางวิศวกรรม", "แบบที่ 1 (มาตรฐาน จุดจ่ายคงที่)", "แบบที่ 2 (ชั้นพักจ่ายเคลื่อนที่)", "แบบที่ 3 (โครงสร้างโปร่งใส Multi-level)"]
    eval_rows = [
        ["ความซับซ้อนของกลไก (Kinematic Complexity)", "ต่ำมาก (3 แกนอิสระ ควบคุมง่าย)", "ปานกลาง (เพิ่มชุดถาดและมอเตอร์เสริม)", "สูง (มีประตูปิด-เปิดหลายระดับ)"],
        ["เสถียรภาพและความน่าเชื่อถือ (Reliability)", "สูงมาก (โอกาสติดขัดน้อยที่สุด)", "ปานกลาง (มีจุดเคลื่อนที่เพิ่มขึ้น)", "ปานกลาง (มีเซนเซอร์ประตูหลายจุด)"],
        ["ความแม่นยำในการตรวจจับของตก", "สูงมาก (มีกรอบรับชิ้นงานจุดเดียว)", "ปานกลาง (ต้องตรวจจับตามระดับชั้น)", "ปานกลาง (ต้องตรวจจับแยกหลายช่อง)"],
        ["ความสะดวกในการซ่อมบำรุง (Maintainability)", "ง่ายมาก (อะไหล่มาตรฐาน)", "ปานกลาง (ต้องปรับตั้งระนาบหลายจุด)", "ยาก (ต้องระวังรอยขีดข่วนอะคริลิก)"],
        ["ความคุ้มค่าและต้นทุนการผลิต (Cost-Effectiveness)", "คุ้มค่าสูงสุด (งบประมาณเหมาะสม)", "ต้นทุนปานกลาง-สูง", "ต้นทุนสูงมาก"],
        ["ผลการคัดเลือกเพื่อผลิตจริง", "ผ่านการคัดเลือก (Final Selection)", "แบบทางเลือกสำรอง", "แบบทางเลือกสำรอง"]
    ]
    add_styled_table(doc, eval_headers, eval_rows, [Inches(1.8), Inches(1.4), Inches(1.4), Inches(1.4)])

    add_callout(doc,
        "คณะทำงานวิศวกรรมและผู้รับจ้างได้มีมติคัดเลือก 'แนวคิดการออกแบบ แบบที่ 1 : ระบบมาตรฐาน (จุดจ่ายคงที่ / จ่ายทีละ 1 ชิ้น)' "
        "เป็นแบบสุดท้าย (Final Version) สำหรับดำเนินการออกแบบรายละเอียดทางวิศวกรรม จัดทำ 3D CAD Model และแบบวาดสายการผลิตฉบับสมบูรณ์ "
        "เนื่องจากเป็นโครงสร้างที่มีความน่าเชื่อถือทางวิศวกรรมสูงสุด กลไกไม่ซับซ้อน มีความปลอดภัยต่อผู้ใช้งาน และบำรุงรักษาง่ายที่สุดในระยะยาว",
        bold_title="ข้อสรุปการคัดเลือกแนวคิดการออกแบบ (Final Design Selection)"
    )

    # 4.3 ผลงานส่งมอบ (Deliverables)
    add_h2(doc, "4.3 ผลงานส่งมอบ (Deliverables - Final Version)")
    add_body(doc,
        "ผู้รับจ้างขอส่งมอบผลงานออกแบบฉบับสมบูรณ์ (Final Version) ตามรายการผลงานส่งมอบข้อ 4.3.1 ถึง 4.3.7 "
        "โดยรวบรวมเนื้อหา รายละเอียดทางวิศวกรรม ตารางสเปก ภาพวาด และแบบแปลนทั้งหมดไว้ในเอกสารฉบับนี้อย่างครบถ้วนสมบูรณ์ ดังนี้:"
    )

    # 4.3.1 แบบร่าง (Concept Design)
    add_h3(doc, "4.3.1 แบบร่าง (Concept Design) ทั้ง 3 รูปแบบ พร้อมภาพ 3D Rendering ฉบับสมบูรณ์")
    add_body(doc,
        "ผู้รับจ้างได้จัดทำแบบร่างและภาพเรนเดอร์ 3 มิติ (3D Rendering) ครบทั้ง 3 รูปแบบ พร้อมจัดทำภาพเรนเดอร์ฉบับสมบูรณ์ของแบบที่ 1 "
        "ในมุมมองต่าง ๆ แสดงรายละเอียดโครงสร้างภายนอก วัสดุตกแต่ง แผงครอบป้องกันฝุ่น ช่องรับสินค้า และตำแหน่งสแกนคิวอาร์โค้ด "
        "เพื่อใช้เป็นต้นแบบในการผลิตตัวถังภายนอกและสื่อความหมายด้านนวัตกรรมเมคาทรอนิกส์ของ NARIT อย่างชัดเจน"
    )

    # 4.3.2 แบบ 3D CAD Model ฉบับสมบูรณ์
    add_h3(doc, "4.3.2 แบบ 3D CAD Model ฉบับสมบูรณ์ (Complete 3D CAD Model)")
    add_body(doc,
        "แบบจำลอง 3 มิติฉบับสมบูรณ์ได้รับการออกแบบด้วยซอฟต์แวร์วิศวกรรม SolidWorks โดยจัดเตรียมไฟล์ในรูปแบบไฟล์ชิ้นส่วน (.sldprt), "
        "ไฟล์ชุดประกอบ (.sldasm) และไฟล์สากลมาตรฐาน STEP (.step / .stp) เพื่อให้สามารถเปิดใช้งาน ตรวจสอบ และนำไปใช้งานต่อกับซอฟต์แวร์ CAD "
        "ได้ทุกแพลตฟอร์มอย่างสมบูรณ์แบบ"
    )

    # IMAGE: image4.png (3D CAD Model Overview)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image4.png"),
        "ภาพแบบจำลอง 3 มิติฉบับสมบูรณ์ (Complete 3D CAD Model) โครงสร้างตู้จำหน่ายสินค้าและชั้นวางภายใน",
        width=Inches(4.5)
    )

    add_body(doc,
        "NARIT Smart Vending Machine ขับเคลื่อนด้วยระบบหุ่นยนต์พิกัดฉาก (Cartesian Robot) 3 แกนอิสระ (X, Y, Z) "
        "ที่ออกแบบขนาดมอเตอร์และอัตราทดให้เหมาะสมกับโหลดและพฤติกรรมการเคลื่อนที่จริง:",
        bold_prefix="ระบบขับเคลื่อนเชิงกล 3 แกน: "
    )
    add_bullet(doc, "ทำหน้าที่ขับเคลื่อนเสาแนวตั้งไปตามแนวซ้าย-ขวาของตู้ ใช้มอเตอร์ Hybrid Closed-Loop Stepper Motor ขนาด NEMA 34 รุ่น 86HBS85 แรงบิดสูงถึง 8.5 N·m กระแส 5.6 A ควบคุมด้วยไดรเวอร์ดิจิทัล HBS860H ส่งกำลังผ่านสายพานไทม์มิ่งความแม่นยำสูง (Timing Belt Drive) ระยะพิตช์สมมูล 8 มม. ต่อรอบ ระยะชักใช้งานจริง 1,200 มม. (ระยะรวมโครงสร้าง 1,465 มม.) มีเอนโค้เดอร์ป้อนกลับตำแหน่ง ป้องกันการตกก้าว 100%", bold_prefix="1) แกน X (แนวนอน — Horizontal Axis): ")
    add_bullet(doc, "ทำหน้าที่ยกระดับชุด Carriage ขึ้น-ลงในแนวดิ่งเพื่อเข้าถึงชั้นวางสินค้าทั้ง 8 ระดับ ใช้มอเตอร์ Closed-Loop Stepper NEMA 34 รุ่น 86HBS85 (8.5 N·m) ร่วมกับไดรเวอร์ HBS860H ส่งกำลังผ่านชุดบอลสกรูความแม่นยำสูง (Ballscrew Drive) ขนาดเพลา 25 มม. พิตช์ 8 มม./รอบ ระยะชักใช้งานจริง 1,440 มม. รองรับน้ำหนักบรรทุกรวมชุดยกและสินค้าได้อย่างนิ่งสนิท", bold_prefix="2) แกน Y (แนวดิ่ง — Vertical Lift Axis): ")
    add_bullet(doc, "ติดตั้งอยู่บนชุด Carriage ทำหน้าที่ยื่นแขนสอดเข้าใต้กล่องสินค้าและดึงกล่องกลับ ใช้ชุดรางสไลด์มินิสำเร็จรูป V-Slot Mini Actuator 1-Axis ขับด้วยสเต็ปเปอร์มอเตอร์ NEMA 17 รุ่น 17HS4401S (แรงบิด 42 N·cm) ร่วมกับไดรเวอร์ DM542 ขับเคลื่อนผ่านลีดสกรูพิตช์ 1.0 มม./รอบ ระยะชักรวม 180 มม. (แบ่งเป็น ระยะเปิดประตู 50 มม. + ระยะช่องว่าง 80 มม. + ระยะเกี่ยวกล่อง 50 มม.)", bold_prefix="3) แกน Z (แนวลึก/ยื่นช้อน — Reach/Extension Axis): ")

    # IMAGE: image8.jpg (Gantry 3 แกน)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image8.jpg"),
        "ภาพโครงสร้างกลไกขับเคลื่อน 3 แกนพิกัดฉาก (Cartesian Gantry X, Y, Z) และการเชื่อมต่อมอเตอร์ส่งกำลัง",
        width=Inches(4.8)
    )

    add_body(doc, "ตารางสรุปพารามิเตอร์ระบบขับเคลื่อน 3 แกน (3-Axis Motion Parameters):", bold_prefix="ตารางพารามิเตอร์การเคลื่อนที่: ")
    motion_headers = ["แกนขับ", "รุ่นมอเตอร์", "แรงบิด", "ระบบส่งกำลัง", "พิตช์", "ระยะชัก", "ความเร็ว", "ความเร่ง"]
    motion_rows = [
        ["แกน X (แนวนอน)", "86HBS85 (NEMA34)", "8.5 N·m", "Timing Belt Drive", "8 mm/rev", "1,200 mm", "300 mm/s", "1,500 mm/s²"],
        ["แกน Y (แนวดิ่ง)", "86HBS85 (NEMA34)", "8.5 N·m", "Ballscrew C7 25mm", "8 mm/rev", "1,440 mm", "250 mm/s", "1,200 mm/s²"],
        ["แกน Z (ยื่นช้อน)", "17HS4401S (NEMA17)", "0.42 N·m", "Lead Screw Mini", "1 mm/rev", "180 mm", "100 mm/s", "800 mm/s²"]
    ]
    add_styled_table(doc, motion_headers, motion_rows, [Inches(1.0), Inches(1.1), Inches(0.6), Inches(1.0), Inches(0.6), Inches(0.6), Inches(0.6), Inches(0.5)])

    add_body(doc,
        "กลไกป้องกันการจ่ายสินค้าซ้อน (Anti-Double Feed Mechanical Logic):\n"
        "เพื่อแก้ปัญหาการไหลซ้อนของกล่องสินค้าชิ้นถัดไปบนรางลาดเอียง ระบบได้รับการออกแบบอัลกอริทึมประสานงานระหว่างแกน Z และ แกน Y โดยเมื่อแกน Z "
        "สอดแผ่นช้อนเข้าใต้กล่องเป้าหมายและเริ่มดึงกล่องถอยหลังออกมาประมาณ 20-30 มม. ซอฟต์แวร์ควบคุมจะสั่งให้แกน Y ขยับยกตัวขึ้นสวนแนวโน้มถ่วง 15 มม. ทันที "
        "ขอบด้านล่างของโครง Carriage จะทำหน้าที่เสมือนสลักกลไกกั้น (Mechanical Interlock Baffle) ขวางไม่ให้กล่องสินค้าชิ้นถัดไปที่อยู่ข้างหลังสไลด์ตามลงมา "
        "เมื่อกล่องสินค้าเป้าหมายถูกดึงพ้นแนวชั้นวางแล้ว กล่องถัดไปจะค่อย ๆ ไหลมาชนกับแผ่น L-Plate ด้านหน้าอย่างนุ่มนวลและพร้อมสำหรับการจ่ายในรอบต่อไป"
    )

    doc.add_page_break()

    # 4.3.3 แบบวาดทางวิศวกรรมฉบับสมบูรณ์ (Production Drawing)
    add_h3(doc, "4.3.3 แบบวาดทางวิศวกรรมฉบับสมบูรณ์ (Production Drawing)")
    add_body(doc,
        "ผู้รับจ้างได้จัดทำแบบวาดทางวิศวกรรมสำหรับการผลิต (Production Drawing) ครบถ้วนตามมาตรฐานสากล ISO/JIS (Third Angle Projection) "
        "ประกอบด้วยรายละเอียดขนาด พิกัดความเผื่อ (Geometric Tolerances) ชนิดวัสดุ และการเก็บผิวงาน (Surface Treatment) ครบทั้ง 12 แผ่น ดังนี้:"
    )

    dwg_headers = ["ลำดับ", "เลขที่แบบ (DWG No.)", "ชื่อแบบวาดทางวิศวกรรม (Drawing Title)", "วัสดุ (Material)", "การเก็บผิวงาน (Finish)", "สเกล"]
    dwg_rows = [
        ["1", "NAR2093-0100A", "Machine Assembly Isometric & Dimensions", "Aluminium / SS400", "Powder Coating / Anodize", "1:40"],
        ["2", "NAR2093-0200A", "Shelf Assembly Overall (ชุดชั้นวางสินค้าภาพรวม)", "SUS304 / Steel", "Brush / Coating", "1:20"],
        ["3", "NAR2093-0200A", "Shelf Plate Sub-Assembly (ชุดประกอบถาดรองรับสินค้า)", "SUS304 Stainless", "No-burr / Clean", "1:15"],
        ["4", "NAR2093", "8-Level Shelf Assembly (ชุดแร็คชั้นวาง 8 ระดับ)", "Aluminium Profile", "Natural Anodize", "1:20"],
        ["5", "NAR2093-0211A", "Stainless Plate Slot Detail (แผ่นสแตนเลสรองสินค้า)", "SUS304 2B (1.2mm)", "Laser Cut / Deburr", "1:12"],
        ["6", "NAR2093-0211A", "Stainless Plate Flatten Pattern (แผ่นสแตนเลสคลี่)", "SUS304 2B (1.2mm)", "Flat Sheet Pattern", "1:10"],
        ["7", "NAR2093-0212A", "Spline Rail Guide (สไปลน์ประกบรางนำร่องกล่อง)", "Steel SS400 (1.2mm)", "Zinc Plated", "1:10"],
        ["8", "NAR2093-0212A", "Spline Flatten Pattern (สไปลน์คลี่ระนาบ)", "Steel SS400 (1.2mm)", "Flat Sheet Pattern", "1:7"],
        ["9", "NAR2093-0213A", "Right L-Plate (แผ่นฉากกั้นขอบขวา)", "Aluminium / SUS304", "Bending Finish", "1:5"],
        ["10", "NAR2093-0213A", "Right L-Plate Flatten (แผ่นฉากกั้นขวาคลี่ระนาบ)", "Aluminium / SUS304", "Flat Sheet Pattern", "1:5"],
        ["11", "NAR2093-0214A", "Left L-Plate (แผ่นฉากกั้นขอบซ้าย)", "Aluminium / SUS304", "Bending Finish", "1:5"],
        ["12", "NAR2093-0214A", "Left L-Plate Flatten (แผ่นฉากกั้นซ้ายคลี่ระนาบ)", "Aluminium / SUS304", "Flat Sheet Pattern", "1:5"]
    ]
    add_styled_table(doc, dwg_headers, dwg_rows, [Inches(0.65), Inches(1.30), Inches(1.75), Inches(0.95), Inches(0.90), Inches(0.45)], font_size_data=12.5, cell_top=45, cell_bot=45)

    doc.add_page_break()

    add_body(doc, "รูปภาพแบบวาดทางวิศวกรรมฉบับสมบูรณ์ (Production Drawing Sheets):", bold_prefix="ภาพแบบวาดการผลิต: ", first_line_indent=0.0)

    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_01.png"),
        "แบบวาดที่ 1 (NAR2093-0100A): มิติและโครงสร้างภาพรวมของเครื่องจำหน่ายสินค้าอัตโนมัติ (Machine Assembly)",
        width=Inches(5.6)
    )
    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_02.png"),
        "แบบวาดที่ 2 (NAR2093-0200A): มิติและโครงสร้างชุดชั้นวางสินค้าหลัก (Shelf Assembly)",
        width=Inches(5.6)
    )
    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_03.png"),
        "แบบวาดที่ 3 (NAR2093-0200A): รายละเอียดชุดประกอบถาดรองรับสินค้าและแผ่นสแตนเลส (Shelf Plate Sub-Assembly)",
        width=Inches(5.6)
    )
    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_04.png"),
        "แบบวาดที่ 4 (NAR2093): โครงสร้างชุดแร็คชั้นวาง 8 ระดับ (8-Level Shelf Assembly)",
        width=Inches(5.6)
    )
    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_05.png"),
        "แบบวาดที่ 5 (NAR2093-0211A): แผ่นสแตนเลสรองสินค้าเจาะสล็อตระบายและลดแรงเสียดทาน (Stainless Plate)",
        width=Inches(5.6)
    )
    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_07.png"),
        "แบบวาดที่ 7 (NAR2093-0212A): สไปลน์รางนำทางกล่องบรรจุภัณฑ์ (Spline Rail Guide)",
        width=Inches(5.6)
    )
    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_09.png"),
        "แบบวาดที่ 9 (NAR2093-0213A): แผ่นฉากกั้นปรับระดับขอบขวา (Right L-Plate)",
        width=Inches(5.6)
    )
    add_image_caption(
        doc,
        os.path.join(draw_dir, "drawing_page_11.png"),
        "แบบวาดที่ 11 (NAR2093-0214A): แผ่นฉากกั้นปรับระดับขอบซ้าย (Left L-Plate)",
        width=Inches(5.6)
    )

    doc.add_page_break()

    # 4.3.4 รายการวัสดุและชิ้นส่วน (Bill of Materials : BOM)
    add_h3(doc, "4.3.4 รายการวัสดุและชิ้นส่วน (Bill of Materials : BOM)")
    add_body(doc,
        "ผู้รับจ้างได้จัดทำบัญชีแจกแจงรายการวัสดุ ชิ้นส่วนทางกล อุปกรณ์ไฟฟ้า และอิเล็กทรอนิกส์ทั้งหมด (Bill of Materials) "
        "ที่ออกแบบและระบุไว้สำหรับสร้างเครื่องจักรต้นแบบ โดยจำแนกออกเป็น 4 หมวดหมู่วิศวกรรมอย่างเป็นสัดส่วน ดังนี้:"
    )

    # BOM Table 1: Core Mechatronics
    add_body(doc, "หมวดที่ 1 : อุปกรณ์ระบบควบคุมและเมคาทรอนิกส์หลัก (Core Mechatronics System)", bold_prefix="BOM ตารางที่ 1: ")
    bom1_headers = ["ลำดับ", "รายการอุปกรณ์", "คุณลักษณะเฉพาะ / โมเดล", "จำนวน", "หน่วย"]
    bom1_rows = []
    for item in bom_data.get('CoreMechatronics', []):
        spec_short = item['spec'].split('\n')[0][:55] if item['spec'] else '-'
        bom1_rows.append([item['no'], item['name'][:42], spec_short, item['qty'], item['unit']])
    add_styled_table(doc, bom1_headers, bom1_rows, [Inches(0.65), Inches(2.10), Inches(2.15), Inches(0.55), Inches(0.55)], font_size_data=12, cell_top=45, cell_bot=45)

    # BOM Table 2: Electrical & Control Enclosure
    add_body(doc, "หมวดที่ 2 : อุปกรณ์ไฟฟ้ากำลังและการจ่ายไฟตู้ควบคุม (Electrical & Power Distribution)", bold_prefix="BOM ตารางที่ 2: ")
    bom2_headers = ["ลำดับ", "รายการอุปกรณ์", "คุณลักษณะเฉพาะ", "จำนวน", "หน่วย"]
    bom2_rows = []
    for item in bom_data.get('อิเล็กเฟส1', [])[:12]:
        spec_short = item['spec'].split('\n')[0][:55] if item['spec'] else '-'
        bom2_rows.append([item['no'], item['name'][:42], spec_short, item['qty'], item['unit']])
    add_styled_table(doc, bom2_headers, bom2_rows, [Inches(0.65), Inches(2.10), Inches(2.15), Inches(0.55), Inches(0.55)], font_size_data=12, cell_top=45, cell_bot=45)

    # BOM Table 3: Mechanical & Transmission
    add_body(doc, "หมวดที่ 3 : อุปกรณ์ระบบเครื่องกลและชิ้นส่วนส่งกำลัง (Mechanical & Power Transmission)", bold_prefix="BOM ตารางที่ 3: ")
    bom3_headers = ["ลำดับ", "รายการอุปกรณ์", "คุณลักษณะเฉพาะ / มาตรฐาน", "จำนวน", "หน่วย"]
    bom3_rows = []
    for item in bom_data.get('Mechanic phase1', [])[:14]:
        spec_short = item['spec'].split('\n')[0][:55] if item['spec'] else '-'
        bom3_rows.append([item['no'], item['name'][:42], spec_short, item['qty'], item['unit']])
    add_styled_table(doc, bom3_headers, bom3_rows, [Inches(0.65), Inches(2.10), Inches(2.15), Inches(0.55), Inches(0.55)], font_size_data=12, cell_top=45, cell_bot=45)

    # BOM Table 4: Fabrication
    add_body(doc, "หมวดที่ 4 : ชิ้นส่วนโลหะสั่งผลิตและตัดพับ (Fabrication & Sheet Metal Parts)", bold_prefix="BOM ตารางที่ 4: ")
    bom4_headers = ["ลำดับ", "รายการชิ้นส่วน", "คุณลักษณะเฉพาะและมิติ", "จำนวน", "หน่วย"]
    bom4_rows = []
    for item in bom_data.get('สั่งผลิต phase1', []):
        spec_short = item['spec'].replace('\n', ' ')[:55] if item['spec'] else '-'
        bom4_rows.append([item['no'], item['name'][:42], spec_short, item['qty'], item['unit']])
    add_styled_table(doc, bom4_headers, bom4_rows, [Inches(0.65), Inches(2.10), Inches(2.15), Inches(0.55), Inches(0.55)], font_size_data=12, cell_top=45, cell_bot=45)

    doc.add_page_break()

    # 4.3.5 เอกสารอธิบายหลักการทำงานของระบบย่อย (System Description Document)
    add_h3(doc, "4.3.5 เอกสารอธิบายหลักการทำงานของระบบย่อยแต่ละระบบ (System Description Document : SDD)")
    add_body(doc,
        "ตู้จำหน่ายสินค้าอัตโนมัติ NARIT Smart Vending Machine ได้รับการออกแบบเชิงสถาปัตยกรรมระบบขั้นสูง "
        "โดยแบ่งระบบออกเป็น 8 ระบบย่อย (8 Subsystems) ที่ทำงานสอดประสานกันอย่างมีเสถียรภาพและปลอดภัยสูงสุด ดังนี้:"
    )

    # IMAGE: image10.jpeg (8 Subsystems Architecture Block Diagram)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image10.jpeg"),
        "บล็อกไดอะแกรมสถาปัตยกรรมระบบโดยรวม (Automated Machine System Architecture Block Diagram) ครอบคลุม 8 ระบบย่อย",
        width=Inches(5.4)
    )

    add_body(doc, "รายละเอียดหลักการทำงานของ 8 ระบบย่อย:", bold_prefix="รายละเอียดเชิงวิศวกรรมของแต่ละระบบย่อย:\n")
    add_bullet(doc, "โครงสร้างหลักสร้างขึ้นจากอลูมิเนียมโปรไฟล์อุตสาหกรรมขนาด 40x40 มม. เสริมมุมด้วยแผ่นเหล็กฉากหนา 10 มม. เพื่อรองรับน้ำหนักโครงสร้าง ชั้นวาง และสินค้าได้มากกว่า 350 กิโลกรัม ทนต่อแรงสั่นสะเทือนจากการเร่งความเร็วของแกน X และ Y ภายในตู้ติดตั้งตู้สวิตช์บอร์ดเหล็กมาตรฐาน IP55 สำหรับติดตั้งระบบไฟฟ้า และมีกระดูกงูร้อยสาย (Drag Chain) ป้องกันสายไฟขาดล้า", bold_prefix="1. ระบบโครงสร้างตู้ (Machine Structure & Cabinet Enclosure): ", space_before=1, space_after=1, line_spacing=1.13)
    add_bullet(doc, "ใช้ระบบชั้นวางเอียง 25 องศาตามแรงโน้มถ่วง (Gravity-Fed Shelves) เมื่อกล่องสินค้าตัวหน้าสุดถูกยกจ่าย กล่องถัดไปจะเลื่อนลงมารอที่ปากรางอัตโนมัติ โดยมีแผ่นสแตนเลสเจาะร่องลดแรงเสียดทานและสไปลน์ประคองข้างเพื่อป้องกันกล่องเอียงติดขัด", bold_prefix="2. ระบบชั้นวางสินค้า (Product Shelf & Gravity-Feed System): ", space_before=1, space_after=1, line_spacing=1.13)
    add_bullet(doc, "ใช้หุ่นยนต์ Cartesian Gantry 3 แกนอิสระ ขับเคลื่อนด้วย Closed-Loop Stepper มอเตอร์แรงบิดสูง 8.5 N·m ในแกน X และ Y ป้องกันการหลุดก้าว ควบคุมความเร็วด้วยโพรไฟล์ S-Curve ป้องกันแรงกระชาก และมี Anti-Double Feed Logic โดยแกน Y ยกขึ้นสวนเพื่อกันกล่องถัดไป", bold_prefix="3. ระบบขับเคลื่อน 3 แกน (3-Axis Cartesian Motion Subsystem): ", space_before=1, space_after=1, line_spacing=1.13)
    add_bullet(doc, "รับไฟ 220VAC ผ่านเบรกเกอร์ MCB, ตัวกรองสัญญาณรบกวน EMI Filter, อุปกรณ์ป้องกันไฟกระชาก SPD และตัวตัดไฟตก-ไฟเกินดิจิทัล แปลงไฟเป็นบัส 60VDC จ่ายมอเตอร์แรงบิดสูง, 24VDC จ่ายระบบคอนโทรล/เซนเซอร์ และ 5VDC จ่ายสมองกล CM4 แบบแยกกราวด์อิสระ (Galvanic Isolation)", bold_prefix="4. ระบบไฟฟ้ากำลังและการจ่ายพลังงาน (Power Distribution & Protection): ", space_before=1, space_after=1, line_spacing=1.13)
    add_bullet(doc, "รวมสัญญาณจากลิมิตสวิตช์ความปลอดภัย 6 จุด (NC Contact), โฮมสวิตช์ 3 จุด และเซนเซอร์ลำแสง Photoelectric Sensor (E3Z-D81) ตรวจจับการตกของกล่องสินค้าลงสู่ช่องรับ เพื่อยืนยันว่าการจ่ายสินค้าสำเร็จจริงก่อนปิดคำสั่งซื้อ", bold_prefix="5. ระบบควบคุม I/O และเซนเซอร์ (I/O & Sensors Network): ", space_before=1, space_after=1, line_spacing=1.13)
    add_bullet(doc, "สถาปัตยกรรมซอฟต์แวร์แบบแยกโพรเซสอิสระ (Decoupled Architecture) บนระบบปฏิบัติการ Linux โดยมี Controller Process เป็นผู้ถือกรรมสิทธิ์ควบคุมฮาร์ดแวร์และการเคลื่อนที่เพียงผู้เดียว บริหารผ่าน Finite State Machine (IDLE, MOVING, DISPENSING, ALARM, E_STOP) และ Web Process รัน REST API ผ่าน FastAPI และสื่อสารข้ามโพรเซสผ่าน Unix Domain Socket", bold_prefix="6. ระบบซอฟต์แวร์และการประมวลผล (Software Architecture & State Engine): ", space_before=1, space_after=1, line_spacing=1.13)
    add_bullet(doc, "รองรับทั้งหน้าจอสัมผัสในตู้ (Local HMI) สำหรับช่างเทคนิคในการทดสอบระบบ (Jog, Home, Slot Calibration) และรองรับ Mobile Web Application สำหรับลูกค้าสั่งซื้อสินค้า พร้อมไฟสัญญาณ LED แสดงสถานะการทำงาน 4 สี (น้ำเงิน=พร้อม, เหลือง=กำลังขยับ, เขียว=สำเร็จ, แดง=ขัดข้อง)", bold_prefix="7. ระบบติดต่อผู้ใช้งาน (HMI Touchscreen & Web Interface): ", space_before=1, space_after=1, line_spacing=1.13)
    add_bullet(doc, "ความปลอดภัยแบบสามชั้น (Three-Tier Safety System): วงจรตัดตอนไฟฟ้าฮาร์ดแวร์ฉุกเฉิน (Hardware E-Stop Contactor Cutoff ตัดบัส 60V ทันทีที่กดปุ่ม), ลิมิตสวิตช์แบบต่ออนุกรมตัดวงจรฉุกเฉินหากหลุดระยะ (Fail-Safe Limit Switches) และ ซอฟต์แวร์วอทช์ด็อก (Software Safety Watchdog) ตรวจสอบความผิดปกติระดับมิลลิวินาที", bold_prefix="8. ระบบความปลอดภัยและอินเตอร์ล็อก (Safety & Interlock System): ", space_before=1, space_after=1, line_spacing=1.13)

    doc.add_page_break()

    # IMAGE: image9.png (Operation Sequence Flowchart)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image9.png"),
        "แผนผังลำดับกระบวนการทำงานหลักของระบบ (End-to-End Operation Workflow Flowchart)",
        width=Inches(4.8)
    )

    # 4.3.6 แบบวงจรไฟฟ้าและแผนผังการเดินสาย (Electrical Schematic & Wiring Diagram)
    add_h3(doc, "4.3.6 แบบวงจรไฟฟ้าและแผนผังการเดินสาย (Electrical Schematic & Wiring Diagram)")
    add_body(doc,
        "ผู้รับจ้างได้ออกแบบแผนผังวงจรไฟฟ้าและการเดินสายไฟภายในเครื่องทั้งหมด (System Power & Signal Wiring Diagram) "
        "โดยเน้นความปลอดภัยระดับอุตสาหกรรมและการป้องกันสัญญาณรบกวนทางแม่เหล็กไฟฟ้า (EMI/EMC) อย่างเคร่งครัด ดังนี้:"
    )

    # IMAGE: image11.png (System Power & Signal Wiring Diagram)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image11.png"),
        "แผนผังการกระจายพลังงานไฟฟ้าและระบบสัญญาณควบคุม (System Power & Signal Wiring Diagram)",
        width=Inches(5.2)
    )

    add_body(doc, "หลักการจัดสรรระบบไฟฟ้าและการเดินสายสัญญาณ:", bold_prefix="รายละเอียดระบบไฟฟ้าและสัญญาณ:\n")
    add_bullet(doc, "รับกระแสไฟฟ้าสลับ 220V 50Hz ผ่าน Miniature Circuit Breaker (MCB), Surge Protection Device (SPD) ป้องกันฟ้าผ่า/ไฟกระชาก และ EMI Filter กรองสัญญาณรบกวนความถี่สูง ก่อนแยกจ่ายเข้า Power Supply 3 ชุด", bold_prefix="1) การกรองและจ่ายไฟฟ้ากระแสสลับ (AC Mains Distribution): ")
    add_bullet(doc, "Switching PSU 60V 6.7A (400W) จ่ายให้เฉพาะไดรเวอร์ HBS860H ของแกน X และ Y เพื่อให้ได้กำลังขับและแรงบิดสูงสุด, DIN-Rail PSU 24V 5A (120W) จ่ายไฟนิ่งให้ไดรเวอร์ DM542 ของแกน Z และบอร์ดขยาย I/O, และ USB-C 15W PSU จ่ายไฟแยกเด็ดขาด (Galvanic Isolation) ให้บอร์ด Raspberry Pi CM4 เพื่อตัดปัญหารีเซ็ตตัวเองจากสัญญาณรบกวน", bold_prefix="2) ระบบแปลงและจ่ายไฟฟ้ากระแสตรง (Triple-Bus DC Architecture): ")
    add_bullet(doc, "สวิตช์ลิมิต Min/Max รวม 6 จุด (แกน X, Y, Z) ใช้หน้าสัมผัสแบบ Normally Closed (NC) ต่ออนุกรมเข้ากับบอร์ดคอนโทรลเลอร์ หากสายไฟขาด หลุด หรือแกนชนสวิตช์ วงจรจะเปิดออกและระบบจะสั่งหยุดขับมอเตอร์ทันทีในระดับมิลลิวินาที", bold_prefix="3) วงจรลิมิตสวิตช์และระบบหยุดฉุกเฉิน (Fail-Safe NC Wiring): ")
    add_bullet(doc, "ปุ่มกด E-Stop หน้าตู้ต่อเข้ากับแมกเนติกคอนแทกเตอร์ (Contactor) โดยตรง เมื่อถูกกดจะตัดไฟบัสขับมอเตอร์ 60VDC ทันที แต่ยังคงจ่ายไฟเลี้ยง 24V/5V ให้ระบบคอมพิวเตอร์เพื่อคงสถานะและแจ้งเตือนข้อผิดพลาด", bold_prefix="4) วงจรตัดกำลังขับฉุกเฉิน (Hardware E-Stop Interlock): ")

    # IMAGE: image12.jpg (IRIV CM4 & Mini Control Box)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image12.jpg"),
        "ภาพบอร์ดประมวลผลหลักคอมพิวเตอร์อุตสาหกรรม IRIV PiControl CM4, บอร์ดขยาย I/O และอุปกรณ์ตู้ควบคุม Mini Control Box",
        width=Inches(4.6)
    )

    # 4.3.7 เอกสารข้อกำหนดการเชื่อมต่อระบบ (Interface Specification Document)
    add_h3(doc, "4.3.7 เอกสารข้อกำหนดการเชื่อมต่อระบบ (Interface Specification Document)")
    add_body(doc,
        "เอกสารข้อกำหนดการเชื่อมต่อระบบได้รับการจัดทำขึ้นเพื่อกำหนดมาตรฐานโปรโตคอลการสื่อสาร "
        "ระหว่างตัวเครื่องจำหน่ายสินค้าอัตโนมัติ (Cabinet Agent), ระบบแม่ข่ายส่วนกลาง (Backend Server) "
        "และแอปพลิเคชันบนโทรศัพท์มือถือ (Mobile Web Application) ผ่านระบบ IoT เพื่อให้การทำงานเป็นไปอย่างถูกต้องและปลอดภัยสูงสุด:"
    )

    # IMAGE: image13.png (MQTT IoT Communication Structure)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image13.png"),
        "โครงสร้างการสื่อสารและสถาปัตยกรรมการเชื่อมต่อระหว่าง Web Application และตัวเครื่องผ่าน Private MQTT Broker",
        width=Inches(4.8)
    )

    add_body(doc,
        "ระบบใช้ MQTT Broker พร้อมการเข้ารหัส TLS และกำหนด Topic แยกตามรหัสประจำเครื่อง ({id}) โดยใช้ระดับคุณภาพบริการ QoS 1 "
        "ประกอบด้วย Topic หลักตามตารางต่อไปนี้:",
        bold_prefix="1) การสื่อสารด้วย MQTT (Message Queuing Telemetry Transport):\n"
    )

    mqtt_headers = ["MQTT Topic", "ทิศทาง", "ระดับ QoS", "หน้าที่และข้อมูลหลักที่รับ-ส่ง (Payload Data)"]
    mqtt_rows = [
        ["cabinet/{id}/scan", "เครื่อง → Server", "QoS 1", "ส่งข้อมูลรหัส Token ที่ลูกค้าสแกนหน้าตู้ พร้อม Device ID และ Timestamp"],
        ["cabinet/{id}/command", "Server → เครื่อง", "QoS 1", "ส่งคำสั่งจ่ายสินค้า (Dispense), พิกัดสล็อตเป้าหมาย, Request ID และ Timeout"],
        ["cabinet/{id}/status", "เครื่อง → Server", "QoS 1", "รายงานสถานะการทำงาน ผลเซนเซอร์ตรวจจับของตก และ Error Code หากมีปัญหา"],
        ["cabinet/{id}/presence", "เครื่อง → Server", "QoS 1 (Retained)", "รายงานสถานะออนไลน์/ออฟไลน์ (LWT: Last Will and Testament) ของตู้"],
        ["cabinet/{id}/telemetry", "เครื่อง → Server", "QoS 0", "ส่งข้อมูลพิกัดปัจจุบัน (DRO X,Y,Z), อุณหภูมิ และสถานะเซนเซอร์แบบเรียลไทม์"]
    ]
    add_styled_table(doc, mqtt_headers, mqtt_rows, [Inches(1.6), Inches(1.1), Inches(0.9), Inches(2.4)])

    # IMAGE: image15.png (MQTT Topic Contract)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image15.png"),
        "แผนภาพข้อกำหนด MQTT Topic Contract และทิศทางการรับ-ส่งข้อมูลระหว่างตัวเครื่องกับเซิร์ฟเวอร์",
        width=Inches(4.2)
    )

    add_body(doc,
        "ตัวเครื่องให้บริการ REST API ผ่าน FastAPI ภายในเครื่อง เพื่อให้ Web Process, Local HMI และระบบภายนอกสามารถเรียกสั่งงาน "
        "โดยมีเอนด์พอยต์สำคัญตามตารางต่อไปนี้:",
        bold_prefix="2) การเชื่อมต่อด้วย REST API:\n"
    )

    api_headers = ["Method", "Endpoint Path", "คำอธิบายหน้าที่การทำงาน", "ระดับความปลอดภัย"]
    api_rows = [
        ["GET", "/api/status", "อ่านสถานะรวมของเครื่องจักร (Machine State, Interlocks, Position)", "Public Read"],
        ["POST", "/api/motion/validate", "ตรวจสอบพารามิเตอร์และพิกัดการเคลื่อนที่ว่าอยู่ในขอบเขตปลอดภัยหรือไม่", "Pre-flight Check"],
        ["POST", "/api/motion/arm", "เตรียมความพร้อมระบบขับเคลื่อน พร้อมสร้าง Arm Token แบบจำกัดเวลา", "Token Gated"],
        ["POST", "/api/motion/execute", "สั่งให้กลไกเคลื่อนที่จริงตามพารามิเตอร์ที่ได้รับอนุมัติผ่าน Arm Token", "Arm Token Required"],
        ["POST", "/api/slot/run_sequence", "สั่งทำงานตามลำดับจ่ายสินค้าเต็มรูปแบบ (Move X/Y -> Extend Z -> Retract Z -> Home)", "Safety Interlocked"],
        ["POST", "/api/stop", "คำสั่งหยุดฉุกเฉินซอฟต์แวร์ สั่งตัดสัญญาณพัลส์และหยุดมอเตอร์ทันที", "High Priority Emergency"]
    ]
    add_styled_table(doc, api_headers, api_rows, [Inches(0.7), Inches(1.8), Inches(2.4), Inches(1.1)])

    # IMAGE: image16.png (REST API Endpoints)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image16.png"),
        "แผนภาพสถาปัตยกรรม REST API Endpoints และการเชื่อมต่อข้ามโพรเซสผ่าน Unix Domain Socket",
        width=Inches(4.8)
    )

    add_body(doc,
        "เพื่อป้องกันอุบัติเหตุและคำสั่งสั่งงานที่ผิดพลาด การสั่งเคลื่อนที่กลไกจะไม่กระทำโดยตรงในคำสั่งเดียว "
        "แต่ต้องผ่านกระบวนการตรวจสอบสิทธิ์และสถานะ 6 ขั้นตอนอย่างเข้มงวด ดังนี้:\n"
        "1. ตรวจสอบสถานะระบบ (System Status Check): เรียก GET /api/status เพื่อยืนยันว่าระบบอยู่ในสถานะ READY ไม่มีสัญญาณเตือน ALARM หรือ E-Stop ค้างอยู่\n"
        "2. ตรวจสอบความถูกต้องของคำสั่ง (Validate Motion Command): เรียก POST /api/motion/validate ตรวจสอบพิกัดเป้าหมายและสปีดว่าอยู่ภายในระยะชักที่ปลอดภัย\n"
        "3. ขอสิทธิ์ขับเคลื่อน (Arm System): เรียก POST /api/motion/arm เพื่อเปิดระบบขับเคลื่อน และรับ Arm Token แบบสุ่มมีอายุ 5 วินาที\n"
        "4. สั่งเริ่มเคลื่อนที่จริง (Execute Motion): เรียก POST /api/motion/execute พร้อมแนบ Arm Token ที่ถูกต้องเพื่อสั่งเคลื่อนที่มอเตอร์\n"
        "5. ติดตามผลการทำงาน (Monitor Telemetry): ติดตามสถานะผ่าน GET /api/status จนกว่ากลไกจะหยุดนิ่งและเซนเซอร์ยืนยันตำแหน่ง\n"
        "6. จุดหยุดฉุกเฉิน (Emergency Stop): สามารถเรียก POST /api/stop ได้ทุกเสี้ยววินาทีเพื่อสั่งเบรกการเคลื่อนที่ทันที",
        bold_prefix="3) ลำดับขั้นตอนความปลอดภัยก่อนการเคลื่อนที่:\n"
    )

    # IMAGE: image17.png (Two-Phase Motion Safety)
    add_image_caption(
        doc,
        os.path.join(media_dir, "image17.png"),
        "แผนผังขั้นตอนความปลอดภัย Two-Phase Motion Safety (Status Check -> Validate -> Arm -> Execute -> Monitor -> E-Stop)",
        width=Inches(4.8)
    )

    # =========================================================================
    # SECTION 4: แบบฟอร์มการตรวจรับพัสดุและลายมือชื่อ (EXACT 1 PAGE COMPLETE)
    # =========================================================================
    sec4 = doc.add_section()
    sec4.page_width = Inches(8.27)
    sec4.page_height = Inches(11.69)
    sec4.top_margin = Inches(0.6)
    sec4.bottom_margin = Inches(0.4)
    sec4.left_margin = Inches(1.25)
    sec4.right_margin = Inches(1.0)
    apply_header_footer(sec4)

    p_cert_title = doc.add_paragraph()
    p_cert_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert_title.paragraph_format.space_before = Pt(0)
    p_cert_title.paragraph_format.space_after = Pt(2)
    p_cert_title.paragraph_format.first_line_indent = Pt(0)
    r_ct = p_cert_title.add_run("ใบตรวจรับพัสดุสำหรับคณะกรรมการตรวจรับพัสดุ")
    set_run_font(r_ct, size_pt=16.5, bold=True, color_rgb=(30, 58, 138))

    p_cb1 = doc.add_paragraph()
    p_cb1.paragraph_format.first_line_indent = Inches(0.5)
    p_cb1.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
    p_cb1.paragraph_format.space_before = Pt(0)
    p_cb1.paragraph_format.space_after = Pt(2)
    p_cb1.paragraph_format.line_spacing = 1.05
    r_cb1 = p_cb1.add_run(
        insert_thai_breaks(
            "ตามที่ สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน) ได้ตกลงจ้าง นายปพน แซ่จ๊ะ ดำเนินการจ้างออกแบบชั้นเก็บและจ่ายอุปกรณ์อิเล็กทรอนิกส์อัตโนมัติ "
            "(Auto Electronic Parts Box) / เครื่องจำหน่ายสินค้าอัตโนมัติ (NARIT Smart Vending Machine) สำหรับบรรจุภัณฑ์รูปทรงสี่เหลี่ยม จำนวน 1 งาน "
            "ตามใบสั่งจ้างเลขที่ J69/290 (เลขที่โครงการ 69079014721, เลขคุมสัญญา 690714014761) ลงวันที่ 1 กรกฎาคม 2569 ในวงเงินค่าจ้าง 90,000.00 บาท (เก้าหมื่นบาทถ้วน) นั้น "
            "คณะกรรมการตรวจรับพัสดุได้ร่วมกันทำการตรวจสอบผลงานการส่งมอบงานจ้างออกแบบดังกล่าวแล้ว ปรากฏผลการตรวจรับดังนี้:"
        )
    )
    set_run_font(r_cb1, size_pt=13.5, color_rgb=(30, 41, 59))

    chk_headers = ["ลำดับ", "รายการผลงานส่งมอบตามข้อกำหนด TOR", "ข้อกำหนดสัญญา", "ผลการตรวจสอบ", "หมายเหตุ"]
    chk_rows = [
        ["1", "แบบร่าง (Concept Design) 3 รูปแบบ พร้อมภาพ 3D Rendering", "TOR ข้อ 4.3.1", "[ / ] ครบถ้วนถูกต้อง", "มีภาพ 3 มิติครบ 3 รูปแบบ"],
        ["2", "แบบ 3D CAD Model ฉบับสมบูรณ์ (SolidWorks & STEP)", "TOR ข้อ 4.3.2", "[ / ] ครบถ้วนถูกต้อง", "รองรับ 3 แกน X,Y,Z สมบูรณ์"],
        ["3", "แบบวาดทางวิศวกรรมฉบับสมบูรณ์ (Production Drawing 12 แผ่น)", "TOR ข้อ 4.3.3", "[ / ] ครบถ้วนถูกต้อง", "มีขนาด Tolerance ครบถ้วน"],
        ["4", "รายการวัสดุและชิ้นส่วน (Bill of Materials : BOM 4 หมวด)", "TOR ข้อ 4.3.4", "[ / ] ครบถ้วนถูกต้อง", "แจกแจงอุปกรณ์ครบทุกหมวด"],
        ["5", "เอกสารอธิบายการทำงานของระบบย่อย (System Description Document)", "TOR ข้อ 4.3.5", "[ / ] ครบถ้วนถูกต้อง", "อธิบายครบถ้วนทั้ง 8 ระบบย่อย"],
        ["6", "แบบวงจรไฟฟ้าและแผนผังการเดินสาย (Wiring Schematic)", "TOR ข้อ 4.3.6", "[ / ] ครบถ้วนถูกต้อง", "ครอบคลุมระบบความปลอดภัย E-Stop"],
        ["7", "เอกสารข้อกำหนดการเชื่อมต่อระบบ (Interface Specification)", "TOR ข้อ 4.3.7", "[ / ] ครบถ้วนถูกต้อง", "ครอบคลุม MQTT และ REST API"]
    ]
    add_styled_table(doc, chk_headers, chk_rows, [Inches(0.65), Inches(2.25), Inches(1.05), Inches(1.05), Inches(1.00)], font_size_data=10.5, cell_top=22, cell_bot=22)

    p_cb2 = doc.add_paragraph()
    p_cb2.paragraph_format.first_line_indent = Inches(0.5)
    p_cb2.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY
    p_cb2.paragraph_format.space_before = Pt(2)
    p_cb2.paragraph_format.space_after = Pt(3)
    p_cb2.paragraph_format.line_spacing = 1.05
    r_cb2 = p_cb2.add_run(
        insert_thai_breaks(
            "คณะกรรมการตรวจรับพัสดุขอรับรองว่า ผู้รับจ้างได้ส่งมอบงานถูกต้องครบถ้วนตามสัญญาจ้างและข้อกำหนดแห่ง TOR ทุกประการ "
            "ตั้งแต่วันที่ 17 กันยายน 2569 (ครบกำหนดส่งมอบตามสัญญาภายใน 90 วัน คือวันที่ 29 กันยายน 2569) ซึ่งเป็นการส่งมอบงานก่อนกำหนดเวลา "
            "จึงเห็นควรอนุมัติให้เบิกจ่ายเงินค่าจ้าง จำนวน 90,000.00 บาท (เก้าหมื่นบาทถ้วน) ให้แก่ผู้รับจ้างต่อไป"
        )
    )
    set_run_font(r_cb2, size_pt=13.5, color_rgb=(30, 41, 59))

    # Signature Block Table (Fits on same page!)
    tbl_sigs = doc.add_table(rows=2, cols=2)
    tbl_sigs.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_sigs.autofit = False
    tbl_sigs.rows[0].cells[0].width = Inches(3.0)
    tbl_sigs.rows[0].cells[1].width = Inches(3.0)
    tbl_sigs.rows[1].cells[0].width = Inches(3.0)
    tbl_sigs.rows[1].cells[1].width = Inches(3.0)

    for r in tbl_sigs.rows:
        for c in r.cells:
            c.paragraphs[0].paragraph_format.space_before = Pt(0)
            c.paragraphs[0].paragraph_format.space_after = Pt(2)
            c.paragraphs[0].paragraph_format.line_spacing = 1.05
            c.paragraphs[0].paragraph_format.first_line_indent = Pt(0)

    # Contractor Signature
    r = tbl_sigs.rows[0].cells[0].paragraphs[0].add_run("ลงชื่อ...................................................ผู้รับจ้าง\n( นายปพน  แซ่จ๊ะ )\nวันที่ 17 กันยายน 2569")
    set_run_font(r, size_pt=11.5, color_rgb=(15, 23, 42))

    # Committee Chairman Signature
    r = tbl_sigs.rows[0].cells[1].paragraphs[0].add_run("ลงชื่อ...................................................ประธานกรรมการ\n( .................................................... )\nวันที่ ......./......./.......")
    set_run_font(r, size_pt=11.5, color_rgb=(15, 23, 42))

    # Committee Member 1
    r = tbl_sigs.rows[1].cells[0].paragraphs[0].add_run("ลงชื่อ...................................................กรรมการตรวจรับ\n( .................................................... )\nวันที่ ......./......./.......")
    set_run_font(r, size_pt=11.5, color_rgb=(15, 23, 42))

    # Committee Member 2
    r = tbl_sigs.rows[1].cells[1].paragraphs[0].add_run("ลงชื่อ...................................................กรรมการตรวจรับ\n( .................................................... )\nวันที่ ......./......./.......")
    set_run_font(r, size_pt=11.5, color_rgb=(15, 23, 42))

    # Save Word document
    print(f"Saving Word document to: {output_docx_path}")
    doc.save(output_docx_path)
    print("Word document generated successfully!")

    # Export PDF via Word COM
    try:
        import win32com.client
        pdf_path = os.path.splitext(output_docx_path)[0] + ".pdf"
        print(f"Converting to PDF via Word COM: {pdf_path}")
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        try:
            wdoc = word.Documents.Open(os.path.abspath(output_docx_path))
            pages = wdoc.ComputeStatistics(2) # 2 = wdStatisticPages
            print(f"Total computed pages in Word: {pages}")
            wdoc.SaveAs(os.path.abspath(pdf_path), FileFormat=17) # 17 = wdFormatPDF
            wdoc.Close(False)
            print("PDF exported successfully!")
        finally:
            word.Quit()
    except Exception as e:
        print(f"Word COM PDF export notice: {e}")

if __name__ == "__main__":
    out_docx = r"D:\37-Project Narit Vending Machine\Document\01-หนังสือส่งมอบงาน Narit Smart Vending Machine (ฉบับสมบูรณ์รวมเล่ม).docx"
    generate_handover_document(out_docx)
