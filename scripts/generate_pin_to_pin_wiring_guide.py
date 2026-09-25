# -*- coding: utf-8 -*-
"""
NARIT Vending Machine — Pin-to-Pin Detailed Electrical Schematic & Wiring Guide
Generates a comprehensive 5-page engineering booklet with explicit PIN-TO-PIN connections:
- Page 1: System Overview & Interconnection Flowchart (Derived directly from block diagram)
- Page 2: Section 1 — AC Mains Distribution & DC Power Supplies (Pin-to-Pin Wiring)
- Page 3: Section 2 — Main Controller (IRiV PiControl CM4) & Modbus I/O (Pin-to-Pin Wiring)
- Page 4: Section 3 — Field Sensor System (Optical & Inductive Limits Pin-to-Pin Wiring)
- Page 5: Section 4 — Stepper Motor Drivers, STM32 Pulse Generator & Motors (Pin-to-Pin Wiring)

Compliant with ISO 7200 / IEC 60617 / IEC 60204-1 standards.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import os
import shutil

plt.rcParams['font.sans-serif'] = ['Leelawadee UI', 'Tahoma', 'Segoe UI', 'DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# Colors
BG_WHITE     = '#FFFFFF'
BORDER_NAVY  = '#0F2744'
BORDER_SLATE = '#334155'
BORDER_LIGHT = '#CBD5E1'

# Headers
HDR_NAVY   = '#0F2744'
HDR_RED    = '#881337'
HDR_AMBER  = '#78350F'
HDR_TEAL   = '#064E3B'
HDR_SLATE  = '#1E293B'

# Text
TXT_MAIN   = '#0F172A'
TXT_MUTED  = '#475569'

# Wires
C_AC_L     = '#B91C1C'  # Phase Red
C_AC_N     = '#1D4ED8'  # Neutral Blue
C_PE       = '#15803D'  # Earth Green
C_60V      = '#991B1B'  # 60VDC Deep Red
C_24V      = '#C2410C'  # 24VDC Orange
C_0V       = '#1E293B'  # 0V Return Slate
C_5V       = '#7E22CE'  # 5VDC Purple
C_STEP     = '#0284C7'  # Pulse Sky Blue
C_DIR      = '#B45309'  # Direction Amber
C_SIG      = '#0F766E'  # Sensor Teal
C_ALM      = '#DC2626'  # Alarm Red
C_ETH      = '#1E3A8A'  # Ethernet Navy

def create_page(title, subtitle, section_tag=""):
    # Canvas size: 32 x 20 inches
    fig = plt.figure(figsize=(32, 20), dpi=150)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 320)
    ax.set_ylim(0, 200)
    ax.axis('off')

    # Border frame
    ax.add_patch(patches.Rectangle((0, 0), 320, 200, facecolor=BG_WHITE, edgecolor=BORDER_NAVY, linewidth=3.5))
    ax.add_patch(patches.Rectangle((4, 4), 312, 192, facecolor='none', edgecolor=BORDER_NAVY, linewidth=1.5))
    ax.add_patch(patches.Rectangle((5.5, 5.5), 309, 189, facecolor='none', edgecolor=BORDER_LIGHT, linewidth=0.8))

    # Top Header Banner
    ax.add_patch(patches.Rectangle((7, 181), 306, 12, facecolor=BORDER_NAVY, edgecolor='none'))
    ax.text(12, 188.5, "สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน) — NATIONAL ASTRONOMICAL RESEARCH INSTITUTE OF THAILAND", 
            color='#94A3B8', fontsize=9.0, fontweight='bold', va='center')
    ax.text(12, 184.2, f"PROJECT: NARIT SMART VENDING MACHINE  |  {title.upper()}", 
            color='white', fontsize=13.0, fontweight='bold', va='center')

    ax.text(310, 188.5, "DOC: NARIT-VEND-E04 (REV 2.6)  |  PIN-TO-PIN SCHEMATIC", 
            color='#38BDF8', fontsize=9.2, fontweight='bold', ha='right', va='center')
    if section_tag:
        ax.text(310, 184.2, f"SECTION: {section_tag.upper()}  |  IEC 60204-1 / ISO 7200 STANDARDS", 
                color='#E2E8F0', fontsize=8.2, ha='right', va='center')

    return fig, ax

def draw_card(ax, x, y, w, h, title, subtitle="", header_color=HDR_SLATE, bg=BG_WHITE, border=BORDER_SLATE):
    ax.add_patch(patches.Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=1.4))
    hdr_h = 4.2
    ax.add_patch(patches.Rectangle((x, y + h - hdr_h), w, hdr_h, facecolor=header_color, edgecolor=border, linewidth=1.0))
    ax.text(x + w/2, y + h - 1.8, title, color='white', fontsize=10.0, fontweight='bold', ha='center', va='center')
    if subtitle:
        ax.text(x + w/2, y + h - 3.2, subtitle, color='#E2E8F0', fontsize=7.5, ha='center', va='center')

def draw_pin_box(ax, x, y, w, h, pin_id, pin_name, color=TXT_MAIN, bg='#F8FAFC'):
    ax.add_patch(patches.Rectangle((x, y), w, h, facecolor=bg, edgecolor=BORDER_SLATE, linewidth=0.9))
    ax.text(x + 1.2, y + h/2, pin_id, color=color, fontsize=8.0, fontweight='bold', va='center')
    ax.text(x + w - 1.2, y + h/2, pin_name, color=TXT_MUTED, fontsize=7.2, ha='right', va='center')

def draw_wire(ax, pts, color, style='-', lw=1.6):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, linestyle=style, linewidth=lw, solid_capstyle='round')

def draw_dot(ax, x, y, color):
    ax.plot(x, y, marker='o', markersize=4.5, color=color, zorder=6)

def draw_table_header(ax, x, y, widths, titles, bg='#E2E8F0'):
    cur_x = x
    for w, t in zip(widths, titles):
        ax.add_patch(patches.Rectangle((cur_x, y), w, 4.2, facecolor=bg, edgecolor=BORDER_SLATE, linewidth=0.8))
        ax.text(cur_x + w/2, y + 2.1, t, color=BORDER_NAVY, fontsize=8.0, fontweight='bold', ha='center', va='center')
        cur_x += w

def draw_table_row(ax, x, y, widths, values, colors=None, bg=BG_WHITE):
    cur_x = x
    for i, (w, val) in enumerate(zip(widths, values)):
        ax.add_patch(patches.Rectangle((cur_x, y), w, 3.8, facecolor=bg, edgecolor=BORDER_LIGHT, linewidth=0.6))
        c = colors[i] if colors and i < len(colors) and colors[i] else TXT_MAIN
        ha = 'center' if i == 0 or len(val) <= 5 else 'left'
        tx = cur_x + w/2 if ha == 'center' else cur_x + 1.5
        ax.text(tx, y + 1.9, val, color=c, fontsize=7.6, fontweight='bold' if i == 0 or i == 1 else 'normal', ha=ha, va='center')
        cur_x += w

# =============================================================================
# PAGE 1: SYSTEM OVERVIEW & PIN-TO-PIN ARCHITECTURE
# =============================================================================
def generate_page_1():
    fig, ax = create_page("System Overview & Pin-to-Pin Architecture", 
                          "Comprehensive Electrical Connection Layout & Subsystem Interconnection Flow", "Overview")

    # Banner explanation
    ax.add_patch(patches.Rectangle((10, 164), 300, 13, facecolor='#F8FAFC', edgecolor=BORDER_SLATE, linewidth=1.0))
    ax.text(14, 172.5, "PIN-TO-PIN WIRING METHODOLOGY & SPECIFICATION:", fontsize=8.8, fontweight='bold', color=BORDER_NAVY)
    ax.text(14, 168.0, "This document explicitly defines the point-to-point electrical connections between terminal blocks, power buses,", fontsize=7.5, color=TXT_MAIN)
    ax.text(14, 165.0, "controllers, motor drives, and sensors. Every terminal pin, wire gauge, and color code is rigorously specified.", fontsize=7.5, color=TXT_MAIN)
    ax.text(260, 170.5, "Standard: IEC 60204-1\nVoltage: 220VAC / 60V / 24V / 5V\nRated Current: 16A Max", fontsize=7.2, color=BORDER_NAVY, fontweight='bold')

    # Left Column: AC Power Chain (x: 10 to 65)
    draw_card(ax, 10, 80, 56, 80, "1. AC MAINS & POWER CHAIN", "220VAC 50Hz Distribution", header_color=HDR_RED)
    
    draw_pin_box(ax, 14, 138, 48, 7.5, "AC INLET (C14)", "L, N, PE Terminals", color=C_AC_L, bg='#FEF2F2')
    draw_pin_box(ax, 14, 124, 48, 7.5, "MCB 2P (C16)", "Poles 1-2 (L) / 3-4 (N)", color=TXT_MAIN)
    draw_pin_box(ax, 14, 110, 48, 7.5, "EMI FILTER", "CW4L2-20A-S (L', N')", color=TXT_MAIN)
    draw_pin_box(ax, 14, 96, 48, 7.5, "SURGE ARRESTER", "Type 2 SPD (L, N, PE)", color=TXT_MAIN)
    draw_pin_box(ax, 14, 84, 48, 7.5, "AC TERMINAL JUMPER", "TB-L, TB-N, TB-PE Bus", color=BORDER_NAVY, bg='#F1F5F9')

    draw_wire(ax, [(38, 138), (38, 131.5)], C_AC_L, lw=2.0)
    draw_wire(ax, [(38, 124), (38, 117.5)], C_AC_L, lw=2.0)
    draw_wire(ax, [(38, 110), (38, 103.5)], C_AC_L, lw=2.0)
    draw_wire(ax, [(38, 96), (38, 91.5)], C_AC_L, lw=2.0)

    # Middle-Left Column: 3 DC Power Supplies (x: 74 to 134)
    draw_card(ax, 74, 80, 60, 80, "2. DC POWER SUPPLIES", "Multi-Rail DC Power Generation", header_color=HDR_SLATE)
    
    draw_pin_box(ax, 78, 135, 52, 18, "PSU 1: 60VDC 6.7A (400W)", "In: L,N,FG | Out: +V, -V", color=C_60V, bg='#FEF2F2')
    draw_pin_box(ax, 78, 110, 52, 18, "PSU 2: 24VDC 5A (120W)", "In: L,N,FG | Out: +24V, 0V", color=C_24V, bg='#FFF7ED')
    draw_pin_box(ax, 78, 85, 52, 18, "PSU 3: USB-C 15W (5V 3A)", "In: L,N | Out: VBUS, GND", color=C_5V, bg='#FAF5FF')

    # Distribute AC to 3 PSUs
    draw_wire(ax, [(62, 88), (68, 88), (68, 144), (78, 144)], C_AC_L, lw=2.0)
    draw_wire(ax, [(68, 88), (68, 119), (78, 119)], C_AC_L, lw=2.0)
    draw_wire(ax, [(68, 88), (78, 88)], C_AC_L, lw=2.0)

    # Center Column: Stepper Drivers & Actuators (x: 142 to 216)
    draw_card(ax, 142, 80, 74, 80, "3. STEPPER DRIVERS & MOTORS", "Axes X, Y, Z Drives & Actuators", header_color=HDR_TEAL)
    
    draw_pin_box(ax, 146, 135, 66, 18, "DRIVER X (HBS860H)", "+60V In | PUL/DIR | Motor X NEMA34", color=C_60V, bg='#FEF2F2')
    draw_pin_box(ax, 146, 110, 66, 18, "DRIVER Y (HBS860H)", "+60V In | PUL/DIR | Motor Y NEMA34", color=C_60V, bg='#FEF2F2')
    draw_pin_box(ax, 146, 85, 66, 18, "DRIVER Z (DM542)", "+24V In | PUL/DIR | Motor Z NEMA17", color=C_24V, bg='#FFF7ED')

    # Connect 60V PSU to Drivers X/Y via KM1
    draw_wire(ax, [(130, 144), (138, 144), (138, 150), (146, 150)], C_60V, lw=2.2)
    draw_wire(ax, [(138, 144), (138, 125), (146, 125)], C_60V, lw=2.2)
    draw_dot(ax, 138, 125, C_60V)
    # Connect 24V PSU to Driver Z
    draw_wire(ax, [(130, 119), (138, 119), (138, 95), (146, 95)], C_24V, lw=2.0)

    # Right Column: Controllers & Sensors (x: 224 to 310)
    draw_card(ax, 224, 80, 86, 80, "4. CONTROLLERS & SENSORS", "Cytron IRiV PiControl & IRiV IO", header_color=HDR_NAVY)
    
    draw_pin_box(ax, 228, 135, 78, 18, "IRIV PiControl CM4", "Dual LAN, 4xUSB, ST-LINK, GPIOs", color=BORDER_NAVY, bg='#EFF6FF')
    draw_pin_box(ax, 228, 110, 78, 18, "IRIV IO CONTROLLER", "Modbus TCP (10.0.0.10) | 11 DI, 4 DO", color=HDR_AMBER, bg='#FFFBEB')
    draw_pin_box(ax, 228, 85, 78, 18, "FIELD SENSOR ARRAY", "2 Optical (Omron) + 6 Proximity (Limits)", color=C_SIG, bg='#F0FDFA')

    # Connect Controllers & Sensors
    draw_wire(ax, [(267, 135), (267, 128)], C_ETH, lw=2.0) # Modbus
    draw_wire(ax, [(267, 110), (267, 103)], C_SIG, lw=2.0) # Sensors

    # Bottom Half: Master Pin-to-Pin Interconnection Table
    draw_card(ax, 10, 14, 300, 62, "MASTER PIN-TO-PIN CONNECTION SCHEDULE", 
              "Explicit Terminal-to-Terminal Mapping across all Cabinets and Rails", header_color=BORDER_NAVY)

    p1_widths = [18, 42, 42, 38, 30, 48, 82]
    draw_table_header(ax, 14, 58.0, p1_widths, 
                      ["WIRE", "ORIGIN COMPONENT", "ORIGIN PIN", "TARGET COMPONENT", "TARGET PIN", "WIRE SPEC / COLOR", "ELECTRICAL FUNCTION"])

    overview_wires = [
        (["W-01", "AC Mains Inlet C14", "Pin L (Live)", "MCB 2P 16A", "Pole 1 (L_in)", "2.5 mm² Brown", "AC 220V Input to Breaker"], [C_AC_L, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["W-02", "MCB 2P 16A", "Pole 2 (L_out)", "EMI Noise Filter", "Terminal LINE (L)", "2.5 mm² Brown", "Protected AC Live to Filter"], [C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["W-03", "EMI Noise Filter", "Terminal LOAD (L')", "AC Terminal Bus", "Terminal TB-L", "2.5 mm² Brown", "Filtered AC Distribution Bus"], [C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN]),
        (["W-04", "AC Terminal Bus", "Terminal TB-L", "PSU 1 (60V 6.7A)", "Terminal L (AC)", "2.5 mm² Brown", "Feeds 60V Motor Power Supply"], [C_AC_L, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["W-05", "PSU 1 (60V 6.7A)", "Terminal +V (DC)", "KM1 Safety Contactor", "Main Contact 1 (L1)", "2.5 mm² Red", "60VDC Motor Bus to Contactor"], [C_60V, TXT_MAIN, C_60V, TXT_MAIN, C_60V, TXT_MAIN, C_60V]),
        (["W-06", "KM1 Safety Contactor", "Main Contact 2 (T1)", "Drivers X & Y", "Terminal AC / V+", "2.5 mm² Red", "Switched 60VDC to X/Y Drives"], [C_60V, TXT_MAIN, C_60V, TXT_MAIN, C_60V, TXT_MAIN, C_60V]),
        (["W-07", "PSU 2 (24V 5A)", "Terminal +24V", "IRiV IO / Sensors", "Terminal 24V / Anode", "1.5 mm² Orange", "+24VDC Control & V-PULSE Bus"], [C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["W-08", "PSU 3 (5V 3A)", "USB-C VBUS Pin", "IRiV PiControl CM4", "USB-C Power Port", "18 AWG Shielded", "+5.1VDC Isolated CM4 Supply"], [C_5V, TXT_MAIN, C_5V, TXT_MAIN, C_5V, TXT_MAIN, C_5V]),
        (["W-09", "IRiV PiControl CM4", "RJ45 Port (eth1)", "IRiV IO Controller", "RJ45 Modbus Port", "Cat6 UTP (Blue)", "Modbus TCP Industrial LAN (10.0.0.2 -> 10.0.0.10)"], [C_ETH, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH]),
        (["W-10", "STM32 NUCLEO-G491RE", "Morpho CN10 pin 23", "Driver X (HBS860H)", "Terminal PUL- (via Q1)", "0.5 mm² Blue (Pair)", "Hardware Timer Pulse (TIM1_CH1 / PA8)"], [C_STEP, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP]),
        (["W-11", "Sensor Array (Limits)", "Black Signal Wire", "IRiV IO Controller", "Terminals DI0 - DI5", "0.5 mm² Shielded", "24V Normally Closed Limit Triggers"], [C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG]),
        (["W-12", "KM1 Aux Contact", "Terminal 21-22 (NC)", "IRiV IO Controller", "Terminal DI10", "0.5 mm² Shielded", "Fail-Safe E-Stop & Contactor Feedback"], [C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
    ]
    y_r = 54.2
    for rdata, rcols in overview_wires:
        draw_table_row(ax, 14, y_r, p1_widths, rdata, rcols, bg='#FEF2F2' if '60V' in rdata[6] or 'E-Stop' in rdata[6] else BG_WHITE)
        y_r -= 3.8

    return fig

# =============================================================================
# PAGE 2: SECTION 1 — AC MAINS & POWER SUPPLIES PIN-TO-PIN
# =============================================================================
def generate_page_2():
    fig, ax = create_page("Section 1: AC Mains & Power Supplies Pin-to-Pin Wiring", 
                          "Direct Pin-to-Pin Connections for 220VAC Mains, Breakers, Filter, SPD, and 3 DC Power Supplies", "Section 1")

    # Left Side: Schematic Graphic with Pin Terminals (x: 10 to 140)
    draw_card(ax, 10, 15, 130, 160, "AC & DC POWER DISTRIBUTION PIN SCHEMATIC", 
              "Exact Point-to-Point Wire Routing between Components", header_color=HDR_RED)

    # 1. Inlet Block
    draw_pin_box(ax, 14, 152, 38, 18, "AC INLET", "IEC C14 Socket\nL, N, PE", color=C_AC_L, bg='#FEF2F2')
    # 2. MCB Block
    draw_pin_box(ax, 68, 152, 40, 18, "MCB 2P (C16)", "In: 1,3 | Out: 2,4", color=TXT_MAIN)
    # Connect Inlet to MCB
    draw_wire(ax, [(52, 163), (68, 163)], C_AC_L, lw=2.0)
    draw_wire(ax, [(52, 157), (68, 157)], C_AC_N, lw=2.0)

    # 3. EMI Filter Block
    draw_pin_box(ax, 14, 118, 48, 22, "EMI FILTER", "CW4L2-20A-S\nLINE: L, N\nLOAD: L', N', FG", color=TXT_MAIN)
    # Connect MCB to EMI Filter
    draw_wire(ax, [(108, 163), (120, 163), (120, 136), (62, 136)], C_AC_L, lw=2.0)
    draw_wire(ax, [(108, 157), (116, 157), (116, 128), (62, 128)], C_AC_N, lw=2.0)

    # 4. SPD Block
    draw_pin_box(ax, 82, 118, 46, 22, "SURGE ARRESTER", "Type 2 SPD\nTerm L, N, PE", color=TXT_MAIN)
    draw_wire(ax, [(62, 136), (72, 136), (72, 132), (82, 132)], C_AC_L, lw=2.0)
    draw_wire(ax, [(62, 128), (72, 128), (72, 124), (82, 124)], C_AC_N, lw=2.0)

    # 5. AC Terminal Bus
    draw_pin_box(ax, 14, 76, 114, 28, "AC TERMINAL JUMPER BUS (DIN RAIL)", 
                 "TB-L : 220VAC Live Rail (1-in 4-out)\nTB-N : 0VAC Neutral Rail (1-in 4-out)\nTB-PE : Protective Earth Ground Bar", 
                 color=BORDER_NAVY, bg='#F1F5F9')
    draw_wire(ax, [(38, 118), (38, 104)], C_AC_L, lw=2.0)

    # 6. KM1 Safety Contactor Block (Bottom)
    draw_pin_box(ax, 14, 22, 114, 46, "KM1 SAFETY CONTACTOR & POWER CUTOFF INTERLOCK", 
                 "Contact 1 (L1) -> Contact 2 (T1) : +60VDC Motor Bus\nContact 3 (L2) -> Contact 4 (T2) : 0VDC Return Bus\nCoil A1 (+24VDC from PiControl DO0) | Coil A2 (0V via E-Stop NC)\nAux Contact 21-22 (NC) : Wired to IRiV IO DI10 for Software Interlock", 
                 color=HDR_RED, bg='#FEF2F2')

    # Right Side: Explicit Pin-to-Pin Table (x: 148 to 310)
    draw_card(ax, 148, 15, 162, 160, "PIN-TO-PIN CONNECTION SCHEDULE (SECTION 1)", 
              "Origin Terminal -> Target Terminal, Wire Gauge, Color, and Voltage", header_color=BORDER_NAVY)

    s1_widths = [16, 28, 22, 28, 22, 24, 22]
    draw_table_header(ax, 152, 157.0, s1_widths, 
                      ["NO", "FROM COMPONENT", "PIN / TERM", "TO COMPONENT", "PIN / TERM", "WIRE COLOR / GAUGE", "SIGNAL / VOLT"])

    s1_wires = [
        (["1", "AC Inlet C14", "Line (L)", "MCB 2P 16A", "Pole 1 (L_in)", "Brown 2.5 mm²", "220VAC Phase"], [TXT_MAIN, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L]),
        (["2", "AC Inlet C14", "Neut (N)", "MCB 2P 16A", "Pole 3 (N_in)", "Blue 2.5 mm²", "0VAC Neutral"], [TXT_MAIN, TXT_MAIN, C_AC_N, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_N]),
        (["3", "AC Inlet C14", "Earth (PE)", "AC Terminal Bus", "TB-PE Bar", "Grn/Yel 2.5 mm²", "Chassis Earth"], [TXT_MAIN, TXT_MAIN, C_PE, TXT_MAIN, C_PE, TXT_MAIN, C_PE]),
        (["4", "MCB 2P 16A", "Pole 2 (L_out)", "EMI Filter", "Terminal L", "Brown 2.5 mm²", "220VAC Line"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L]),
        (["5", "MCB 2P 16A", "Pole 4 (N_out)", "EMI Filter", "Terminal N", "Blue 2.5 mm²", "0VAC Neutral"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_N]),
        (["6", "EMI Filter", "Terminal L'", "AC Terminal Bus", "TB-L Bus", "Brown 2.5 mm²", "Filtered 220V"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L, TXT_MAIN, C_AC_L]),
        (["7", "EMI Filter", "Terminal N'", "AC Terminal Bus", "TB-N Bus", "Blue 2.5 mm²", "Filtered 0V"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_N, TXT_MAIN, C_AC_N]),
        (["8", "EMI Filter", "Terminal FG", "AC Terminal Bus", "TB-PE Bar", "Grn/Yel 2.5 mm²", "Earth Ground"], [TXT_MAIN, TXT_MAIN, C_PE, TXT_MAIN, C_PE, TXT_MAIN, C_PE]),
        (["9", "AC Terminal Bus", "TB-L Bus", "Surge Arrester", "Terminal L", "Brown 2.5 mm²", "220VAC Surge"], [TXT_MAIN, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L]),
        (["10", "AC Terminal Bus", "TB-N Bus", "Surge Arrester", "Terminal N", "Blue 2.5 mm²", "0VAC Surge"], [TXT_MAIN, TXT_MAIN, C_AC_N, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_N]),
        (["11", "Surge Arrester", "Terminal PE", "AC Terminal Bus", "TB-PE Bar", "Grn/Yel 2.5 mm²", "Earth Discharge"], [TXT_MAIN, TXT_MAIN, C_PE, TXT_MAIN, C_PE, TXT_MAIN, C_PE]),
        (["12", "AC Terminal Bus", "TB-L Bus", "PSU 1 (60V)", "Terminal L", "Brown 2.5 mm²", "220VAC Feed"], [TXT_MAIN, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L]),
        (["13", "AC Terminal Bus", "TB-N Bus", "PSU 1 (60V)", "Terminal N", "Blue 2.5 mm²", "0VAC Return"], [TXT_MAIN, TXT_MAIN, C_AC_N, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_N]),
        (["14", "AC Terminal Bus", "TB-L Bus", "PSU 2 (24V)", "Terminal L", "Brown 1.5 mm²", "220VAC Feed"], [TXT_MAIN, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L]),
        (["15", "AC Terminal Bus", "TB-N Bus", "PSU 2 (24V)", "Terminal N", "Blue 1.5 mm²", "0VAC Return"], [TXT_MAIN, TXT_MAIN, C_AC_N, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_N]),
        (["16", "AC Terminal Bus", "TB-L Bus", "PSU 3 (5V)", "Plug Live", "Brown 1.5 mm²", "220VAC Feed"], [TXT_MAIN, TXT_MAIN, C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_L]),
        (["17", "AC Terminal Bus", "TB-N Bus", "PSU 3 (5V)", "Plug Neut", "Blue 1.5 mm²", "0VAC Return"], [TXT_MAIN, TXT_MAIN, C_AC_N, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_AC_N]),
        (["18", "PSU 1 (60V)", "Terminal +V", "KM1 Contactor", "Contact 1 (L1)", "Red 2.5 mm²", "+60VDC Motor"], [TXT_MAIN, TXT_MAIN, C_60V, TXT_MAIN, C_60V, TXT_MAIN, C_60V]),
        (["19", "PSU 1 (60V)", "Terminal -V", "KM1 Contactor", "Contact 3 (L2)", "Black 2.5 mm²", "0VDC Return"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["20", "KM1 Contactor", "Contact 2 (T1)", "Drivers X & Y", "Terminal AC/V+", "Red 2.5 mm²", "+60VDC Switched"], [TXT_MAIN, TXT_MAIN, C_60V, TXT_MAIN, C_60V, TXT_MAIN, C_60V]),
        (["21", "KM1 Contactor", "Contact 4 (T2)", "Drivers X & Y", "Terminal AC/V-", "Black 2.5 mm²", "0VDC Switched"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["22", "PiControl CM4", "Terminal DO0", "KM1 Contactor", "Coil A1 (+24V)", "Orange 1.0 mm²", "Coil Drive / Reset"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["23", "KM1 Contactor", "Coil A2 (0V)", "E-Stop Button", "NC Contact 1", "Red 1.0 mm²", "Series E-Stop Loop"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["24", "KM1 Contactor", "Aux Contact 21-22", "IRiV IO Modbus", "Terminal DI10", "Shielded 0.5 mm²", "Contactor Feedback"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
    ]
    y_r = 153.2
    for rdata, rcols in s1_wires:
        draw_table_row(ax, 152, y_r, s1_widths, rdata, rcols, bg='#FEF2F2' if '60V' in rdata[6] or 'E-Stop' in rdata[6] else BG_WHITE)
        y_r -= 3.8

    return fig

# =============================================================================
# PAGE 3: SECTION 2 — CONTROLLERS & COMMUNICATION PIN-TO-PIN
# =============================================================================
def generate_page_3():
    fig, ax = create_page("Section 2: Controllers & Communication Pin-to-Pin Wiring", 
                          "Cytron IRiV PiControl CM4, IRiV IO Modbus TCP Controller, Dual Subnets, and USB Peripherals", "Section 2")

    # Left Side: Graphic Layout of Controller Connectors (x: 10 to 140)
    draw_card(ax, 10, 15, 130, 160, "CONTROLLER TERMINALS & PORT MAPPING", 
              "PiControl CM4 & IRiV IO Physical Ports and Terminals", header_color=HDR_NAVY)

    # PiControl Box
    draw_pin_box(ax, 14, 132, 122, 38, "Cytron IRiV PiControl CM4 (MAIN CPU)", 
                 "eth0 : 192.168.70.80 (Flask Web Kiosk UI Port 80, REST API, MQTT)\neth1 : 10.0.0.2 (OT Industrial Modbus Master to IRiV IO)\nUSB 1 : 2D QR Scanner | USB 2 : FHD Web Camera\nUSB 3 : Audio Speaker (3W) | USB 4 : ST-LINK V3 VCP (115200 8-N-1)\nPower : USB-C (5V 3A) + 24V Aux Terminal Block", 
                 color=BORDER_NAVY, bg='#EFF6FF')

    # PiControl Isolated GPIO Terminal
    draw_pin_box(ax, 14, 82, 122, 46, "PiControl LOCAL ISOLATED GPIO TERMINAL BLOCK", 
                 "DI0 (GPIO 13) : X_DRIVE_ALM (From Driver X ALM- Opto)\nDI1 (GPIO 17) : Y_DRIVE_ALM (From Driver Y ALM- Opto)\nDI2 (GPIO 27) : X_PEND (From Driver X PEND- Opto)\nDI3 (GPIO 22) : Y_PEND (From Driver Y PEND- Opto)\nDO0 (GPIO 23) : XY_DRIVE_POWER_KM1 (Safety Contactor Driver)\n24V IN / 0V IN : Power terminals from PSU 2 (+24V / 0V Rail)", 
                 color=BORDER_NAVY, bg='#FFFFFF')

    # IRiV IO Modbus Controller Box (Bottom)
    draw_pin_box(ax, 14, 22, 122, 56, "Cytron IRiV IO (MODBUS TCP SLAVE @ 10.0.0.10:502)", 
                 "RJ45 Port : Modbus TCP from PiControl eth1 (Unit ID 255)\nPower Terminals : +24V, 0V, S/S (S/S jumpered to 0V for PNP mode)\nDI0 - DI5 : Limits Min/Max X, Y, Z (Normally Closed Proximity)\nDI6 - DI7 : Z Home Sensor (NO) & Product Drop Alignment Parking\nDI8 - DI9 : Completed Drop (Omron Beam) & Pickup Door Flap Access\nDI10 : KM1 Safety Contactor Feedback (Fail-Safe NC Loop)\nDO0 - DO3 : Ready, Moving, Alarm Indicators & Dispense Solenoid", 
                 color=HDR_AMBER, bg='#FFFBEB')

    # Right Side: Explicit Pin-to-Pin Table (x: 148 to 310)
    draw_card(ax, 148, 15, 162, 160, "PIN-TO-PIN CONNECTION SCHEDULE (SECTION 2)", 
              "Controller Pinout, Communication Lines, and Field I/O Termination", header_color=BORDER_NAVY)

    s2_widths = [16, 28, 22, 28, 22, 24, 22]
    draw_table_header(ax, 152, 157.0, s2_widths, 
                      ["NO", "FROM COMPONENT", "PIN / TERM", "TO COMPONENT", "PIN / TERM", "WIRE COLOR / GAUGE", "SIGNAL / FUNCTION"])

    s2_wires = [
        (["1", "PiControl CM4", "RJ45 eth1", "IRiV IO Controller", "RJ45 Modbus", "Cat6 UTP Blue", "Modbus TCP (10.0.0.2/10)"], [TXT_MAIN, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH]),
        (["2", "PiControl CM4", "USB 4 Port", "NUCLEO-G491RE", "ST-LINK VCP", "Shielded USB-A", "Safe-Link v3 115200"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["3", "PiControl CM4", "USB 1 Port", "2D QR Scanner", "USB Cable", "Molded USB-A", "Barcode / Payment CDC"], [TXT_MAIN, TXT_MAIN, C_5V, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["4", "PiControl CM4", "USB 2 Port", "FHD Web Camera", "USB Cable", "Molded USB-A", "1080p UVC Video Stream"], [TXT_MAIN, TXT_MAIN, C_5V, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["5", "PiControl CM4", "USB 3 / 3.5mm", "Audio Speaker", "3.5mm Audio", "Stereo Jack", "Voice Chime Guidance"], [TXT_MAIN, TXT_MAIN, C_5V, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["6", "Driver X (HBS860H)", "Terminal ALM-", "PiControl CM4", "Terminal DI0", "0.5 mm² Red", "X Drive Alarm Opto"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["7", "Driver Y (HBS860H)", "Terminal ALM-", "PiControl CM4", "Terminal DI1", "0.5 mm² Red", "Y Drive Alarm Opto"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["8", "Driver X (HBS860H)", "Terminal PEND-", "PiControl CM4", "Terminal DI2", "0.5 mm² Amber", "X In-Position Signal"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR]),
        (["9", "Driver Y (HBS860H)", "Terminal PEND-", "PiControl CM4", "Terminal DI3", "0.5 mm² Amber", "Y In-Position Signal"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR]),
        (["10", "PiControl CM4", "Terminal DO0", "KM1 Contactor", "Coil A1 (+24V)", "1.0 mm² Orange", "Safety Contactor Reset"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["11", "PSU 2 (24V 5A)", "Terminal +24V", "PiControl CM4", "24V IN (+)", "1.0 mm² Orange", "Aux 24V Logic Power"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["12", "PSU 2 (24V 5A)", "Terminal 0V", "PiControl CM4", "0V IN (-)", "1.0 mm² Black", "Field 0V Reference"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["13", "PSU 2 (24V 5A)", "Terminal +24V", "IRiV IO Controller", "Power +24V", "1.5 mm² Orange", "+24VDC Module Power"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["14", "PSU 2 (24V 5A)", "Terminal 0V", "IRiV IO Controller", "Power 0V", "1.5 mm² Black", "0VDC Module Return"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["15", "IRiV IO Controller", "Terminal 0V", "IRiV IO Controller", "Terminal S/S", "Jumper Wire (Blk)", "S/S tied to 0V (PNP)"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["16", "IRiV IO Controller", "Terminal DO0", "Pilot Light Green", "Lamp Anode (+)", "0.75 mm² Green", "Machine Ready Light"], [TXT_MAIN, TXT_MAIN, C_PE, TXT_MAIN, C_PE, TXT_MAIN, C_PE]),
        (["17", "IRiV IO Controller", "Terminal DO1", "Pilot Light Yellow", "Lamp Anode (+)", "0.75 mm² Yellow", "Carriage Moving Light"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR]),
        (["18", "IRiV IO Controller", "Terminal DO2", "Red Light / Buzzer", "Anode (+)", "0.75 mm² Red", "Alarm / Fault Indicator"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["19", "IRiV IO Controller", "Terminal DO3", "Dispense Relay", "Relay Coil A1", "0.75 mm² Blue", "Door Drop Solenoid"], [TXT_MAIN, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH]),
        (["20", "KM1 Contactor", "Terminal 21-22", "IRiV IO Controller", "Terminal DI10", "0.5 mm² Shielded", "Fail-Safe NC E-Stop"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
    ]
    y_r = 153.2
    for rdata, rcols in s2_wires:
        draw_table_row(ax, 152, y_r, s2_widths, rdata, rcols, bg='#FEF2F2' if 'ALM' in rdata[6] or 'E-Stop' in rdata[6] else BG_WHITE)
        y_r -= 3.8

    return fig

# =============================================================================
# PAGE 4: SECTION 3 — SENSOR SYSTEM PIN-TO-PIN
# =============================================================================
def generate_page_4():
    fig, ax = create_page("Section 3: Field Sensor System Pin-to-Pin Wiring", 
                          "Direct Terminal Connections for 2 x Optical Sensors and 6 x Inductive Proximity Limit Sensors", "Section 3")

    # Left Side: Graphic Layout of Sensor Wiring (x: 10 to 140)
    draw_card(ax, 10, 15, 130, 160, "FIELD SENSOR WIRING SCHEMATIC", 
              "Pin-to-Pin Terminations of 3-Wire Proximity & Optical Sensors", header_color=HDR_AMBER)

    # Power Distribution for Sensors
    draw_pin_box(ax, 14, 150, 122, 20, "SENSOR POWER DISTRIBUTION BUS (PSU 2)", 
                 "+24VDC Bus Rail : Brown Wire (BN) on all 8 Sensors\n0VDC Common Rail : Blue Wire (BU) on all 8 Sensors + S/S Terminal\nPE Ground Bar : Shield Drain Wires Grounded at Cabinet PE", 
                 color=C_24V, bg='#FFF7ED')

    # Optical Sensors Box
    draw_pin_box(ax, 14, 102, 122, 44, "OPTICAL PHOTOELECTRIC SENSORS (OMRON E3Z-D81)", 
                 "Completed Drop Sensor (DI8) :\n  Brown -> +24VDC | Blue -> 0VDC | Black -> IRiV IO Terminal DI8\nAlarm / Pickup Door Sensor (DI9) :\n  Brown -> +24VDC | Blue -> 0VDC | Black -> IRiV IO Terminal DI9\nOperating Mode : Dark-ON mode (Detects drop / door flap open)", 
                 color=HDR_AMBER, bg='#FEF2F2')

    # Proximity Limit Sensors Box
    draw_pin_box(ax, 14, 22, 122, 76, "INDUCTIVE PROXIMITY LIMIT SENSORS (PNP NC)", 
                 "Standard Wiring for all 6 Limit Sensors (LJ12A3-4-Z/AX) :\n  Brown (BN) -> +24VDC Bus | Blue (BU) -> 0VDC Return Bus\n  Black (BK) -> Signal Output to IRiV IO Digital Inputs:\n    - Limit Min X (Home)  -> Terminal DI0 (Channel 0)\n    - Limit Max X         -> Terminal DI1 (Channel 1)\n    - Limit Min Y (Drop)  -> Terminal DI2 (Channel 2)\n    - Limit Max Y (Top)   -> Terminal DI3 (Channel 3)\n    - Limit Min Z (Home)  -> Terminal DI4 (Channel 4)\n    - Limit Max Z (Push)  -> Terminal DI5 (Channel 5)\n  Auxiliary NO Sensors :\n    - Z Home Datum Sensor -> Terminal DI6 | Drop Parking -> DI7", 
                 color=C_SIG, bg='#F0FDFA')

    # Right Side: Explicit Pin-to-Pin Table (x: 148 to 310)
    draw_card(ax, 148, 15, 162, 160, "PIN-TO-PIN CONNECTION SCHEDULE (SECTION 3)", 
              "Sensor Leads -> Power Bus & IRiV IO Digital Input Terminals", header_color=BORDER_NAVY)

    s3_widths = [16, 28, 22, 28, 22, 24, 22]
    draw_table_header(ax, 152, 157.0, s3_widths, 
                      ["NO", "SENSOR NAME", "LEAD / COLOR", "TERMINATION POINT", "PIN / TERM", "WIRE SPEC / SHIELD", "FUNCTION / ACTION"])

    s3_wires = [
        (["1", "Completed Sensor", "Brown Lead", "Sensor Power Bus", "Terminal +24V", "3-Core 0.5 mm²", "+24VDC Sensor Power"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["2", "Completed Sensor", "Blue Lead", "Sensor Power Bus", "Terminal 0V", "3-Core 0.5 mm²", "0VDC Power Return"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["3", "Completed Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI8", "3-Core Shielded", "Drop Verification Beam"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["4", "Alarm Sensor", "Brown Lead", "Sensor Power Bus", "Terminal +24V", "3-Core 0.5 mm²", "+24VDC Sensor Power"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["5", "Alarm Sensor", "Blue Lead", "Sensor Power Bus", "Terminal 0V", "3-Core 0.5 mm²", "0VDC Power Return"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["6", "Alarm Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI9", "3-Core Shielded", "Pickup Door Flap Open"], [TXT_MAIN, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["7", "Limit Min X Sensor", "Brown Lead", "Sensor Power Bus", "Terminal +24V", "3-Core 0.5 mm²", "+24VDC Sensor Power"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["8", "Limit Min X Sensor", "Blue Lead", "Sensor Power Bus", "Terminal 0V", "3-Core 0.5 mm²", "0VDC Power Return"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["9", "Limit Min X Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI0", "3-Core Shielded", "X Min Limit / Home (NC)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG]),
        (["10", "Limit Max X Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI1", "3-Core Shielded", "X Max Travel Limit (NC)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG]),
        (["11", "Limit Min Y Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI2", "3-Core Shielded", "Y Min (Drop Level NC)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG]),
        (["12", "Limit Max Y Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI3", "3-Core Shielded", "Y Max (Top Level NC)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG]),
        (["13", "Limit Min Z Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI4", "3-Core Shielded", "Z Min (Pusher Home NC)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG]),
        (["14", "Limit Max Z Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI5", "3-Core Shielded", "Z Max (Pusher Push NC)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG]),
        (["15", "Z Home Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI6", "3-Core Shielded", "Z Home Datum (NO)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MUTED]),
        (["16", "Drop Park Sensor", "Black Lead", "IRiV IO Controller", "Terminal DI7", "3-Core Shielded", "Carriage Alignment (NO)"], [TXT_MAIN, TXT_MAIN, C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MUTED]),
        (["17", "All Sensor Cables", "Drain Wire", "Chassis Earth", "TB-PE Bar", "Braided Screen", "Noise Shield Grounding"], [TXT_MAIN, TXT_MAIN, C_PE, TXT_MAIN, C_PE, TXT_MAIN, C_PE]),
        (["18", "IRiV IO Controller", "Power 0V", "IRiV IO Controller", "Terminal S/S", "Jumper 1.0 mm²", "S/S tied to 0V for PNP"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
    ]
    y_r = 153.2
    for rdata, rcols in s3_wires:
        draw_table_row(ax, 152, y_r, s3_widths, rdata, rcols, bg='#FEF2F2' if 'DI8' in rdata[4] or 'DI9' in rdata[4] else BG_WHITE)
        y_r -= 3.8

    return fig

# =============================================================================
# PAGE 5: SECTION 4 — STEPPER DRIVERS, STM32 & MOTORS PIN-TO-PIN
# =============================================================================
def generate_page_5():
    fig, ax = create_page("Section 4: Stepper Drivers, STM32 & Motors Pin-to-Pin Wiring", 
                          "STM32 Pulse Engine -> 6-Ch NMOS Sink Board -> Drivers X/Y (HBS860H) & Z (DM542) -> Motors & Encoders", "Section 4")

    # Left Side: Graphic Layout of Motion Pulse & Motor Interfaces (x: 10 to 140)
    draw_card(ax, 10, 15, 130, 160, "MOTION CONTROL & PULSE INTERFACE SCHEMATIC", 
              "STM32 Hardware Timers, NMOS Open Drain Sink & Motor Terminals", header_color=HDR_TEAL)

    # STM32 NUCLEO Block
    draw_pin_box(ax, 14, 134, 122, 36, "STM32 NUCLEO-G491RE CO-PROCESSOR", 
                 "Hardware Timer Output Compare Pulse Generation (10 - 50,000 Hz) :\n  X_STEP : PA8 (TIM1_CH1 / AF6) on Morpho CN10 pin 23 (Arduino D7)\n  X_DIR  : PB0 (GPIO Output) on Morpho CN7 pin 34 (Arduino A3)\n  Y_STEP : PA9 (TIM1_CH2 / AF6) on Morpho CN10 pin 21 (Arduino D8)\n  Y_DIR  : PB1 (GPIO Output) on Morpho CN10 pin 24\n  Z_STEP : PA5 (TIM2_CH1 / AF1) on Morpho CN10 pin 11 (Arduino D13)\n  Z_DIR  : PB2 (GPIO Output) on Morpho CN10 pin 22 | GND : CN10 pin 20", 
                 color=BORDER_NAVY, bg='#EFF6FF')

    # 6-Channel NMOS Open Drain Board
    draw_pin_box(ax, 14, 86, 122, 44, "6-CHANNEL LOGIC-LEVEL NMOS SINK BOARD", 
                 "3.3V Logic Gate Drive -> 24V Low-Side Open-Drain Sink Circuits :\n  Gate Q1-Q6 : Driven by STM32 GPIOs via 100-Ohm series + 10k pulldown\n  Drain Q1-Q6 : Sinks Driver Terminals PUL- and DIR- to 0V\n  Source Q1-Q6 : Tied to MCU GND and Field 0VDC Reference\n  V-PULSE Bus (+24VDC) : Feeds all Driver PUL+ and DIR+ (Common Anode)", 
                 color=HDR_SLATE, bg='#F0FDFA')

    # Motor Drivers & Actuators Box
    draw_pin_box(ax, 14, 22, 122, 60, "STEPPER MOTOR DRIVERS & ACTUATOR MOTORS", 
                 "Driver X (HBS860H) & Motor X (86HBS85 NEMA 34) :\n  Power : +60VDC/0V | PUL/DIR from NMOS Ch1/Ch2 | Coils A/B | Encoder EA/EB\nDriver Y (HBS860H) & Motor Y (86HBS85 NEMA 34 Elevator) :\n  Power : +60VDC/0V | PUL/DIR from NMOS Ch3/Ch4 | Coils A/B | Encoder EA/EB\nDriver Z (DM542) & Motor Z (NEMA 17 V-Slot Pusher Actuator) :\n  Power : +24VDC/0V | PUL/DIR from NMOS Ch5/Ch6 | Coils A/B (Red,Blu,Blk,Grn)", 
                 color=HDR_TEAL, bg='#FFFFFF')

    # Right Side: Explicit Pin-to-Pin Table (x: 148 to 310)
    draw_card(ax, 148, 15, 162, 160, "PIN-TO-PIN CONNECTION SCHEDULE (SECTION 4)", 
              "STM32 Morpho Pins -> NMOS Board -> Motor Drivers -> Motor Coils & Encoders", header_color=BORDER_NAVY)

    s4_widths = [16, 28, 22, 28, 22, 24, 22]
    draw_table_header(ax, 152, 157.0, s4_widths, 
                      ["NO", "ORIGIN COMPONENT", "PIN / TERM", "TARGET COMPONENT", "PIN / TERM", "WIRE COLOR / GAUGE", "SIGNAL / FUNCTION"])

    s4_wires = [
        (["1", "STM32 G491RE", "PA8 (CN10-23)", "NMOS Board", "Gate Q1 (In)", "Ribbon Wire", "X_STEP Pulse (TIM1)"], [TXT_MAIN, TXT_MAIN, C_STEP, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_STEP]),
        (["2", "STM32 G491RE", "PB0 (CN7-34)", "NMOS Board", "Gate Q2 (In)", "Ribbon Wire", "X_DIR Direction"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_DIR]),
        (["3", "STM32 G491RE", "PA9 (CN10-21)", "NMOS Board", "Gate Q3 (In)", "Ribbon Wire", "Y_STEP Pulse (TIM1)"], [TXT_MAIN, TXT_MAIN, C_STEP, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_STEP]),
        (["4", "STM32 G491RE", "PB1 (CN10-24)", "NMOS Board", "Gate Q4 (In)", "Ribbon Wire", "Y_DIR Direction"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_DIR]),
        (["5", "STM32 G491RE", "PA5 (CN10-11)", "NMOS Board", "Gate Q5 (In)", "Ribbon Wire", "Z_STEP Pulse (TIM2)"], [TXT_MAIN, TXT_MAIN, C_STEP, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_STEP]),
        (["6", "STM32 G491RE", "PB2 (CN10-22)", "NMOS Board", "Gate Q6 (In)", "Ribbon Wire", "Z_DIR Direction"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, TXT_MAIN, TXT_MAIN, C_DIR]),
        (["7", "STM32 G491RE", "GND (CN10-20)", "NMOS Board", "Source / 0V", "Black 1.0 mm²", "Digital Ground Return"], [TXT_MAIN, TXT_MAIN, C_0V, TXT_MAIN, C_0V, TXT_MAIN, C_0V]),
        (["8", "PSU 2 (+24V)", "Terminal +24V", "Motor Drivers X,Y,Z", "Term PUL+, DIR+", "Orange 1.0 mm²", "+24V Common Anode"], [TXT_MAIN, TXT_MAIN, C_24V, TXT_MAIN, C_24V, TXT_MAIN, C_24V]),
        (["9", "NMOS Board", "Drain Q1", "Driver X (HBS860H)", "Terminal PUL-", "0.5 mm² Blue", "X Step Opto Sink"], [TXT_MAIN, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP]),
        (["10", "NMOS Board", "Drain Q2", "Driver X (HBS860H)", "Terminal DIR-", "0.5 mm² Amber", "X Dir Opto Sink"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR]),
        (["11", "NMOS Board", "Drain Q3", "Driver Y (HBS860H)", "Terminal PUL-", "0.5 mm² Blue", "Y Step Opto Sink"], [TXT_MAIN, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP]),
        (["12", "NMOS Board", "Drain Q4", "Driver Y (HBS860H)", "Terminal DIR-", "0.5 mm² Amber", "Y Dir Opto Sink"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR]),
        (["13", "NMOS Board", "Drain Q5", "Driver Z (DM542)", "Terminal PUL-", "0.5 mm² Blue", "Z Step Opto Sink"], [TXT_MAIN, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP, TXT_MAIN, C_STEP]),
        (["14", "NMOS Board", "Drain Q6", "Driver Z (DM542)", "Terminal DIR-", "0.5 mm² Amber", "Z Dir Opto Sink"], [TXT_MAIN, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR, TXT_MAIN, C_DIR]),
        (["15", "Driver X", "Term A+ / A-", "Motor X (86HBS85)", "Phase A Leads", "Red / Blue 1.5mm²", "Motor Phase A Coils"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["16", "Driver X", "Term B+ / B-", "Motor X (86HBS85)", "Phase B Leads", "Blk / Grn 1.5mm²", "Motor Phase B Coils"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["17", "Driver X", "Term EA+/EA-", "Motor X Encoder", "Channel A Leads", "Shielded Pair", "Encoder Differential A"], [TXT_MAIN, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH]),
        (["18", "Driver X", "Term EB+/EB-", "Motor X Encoder", "Channel B Leads", "Shielded Pair", "Encoder Differential B"], [TXT_MAIN, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH, TXT_MAIN, C_ETH]),
        (["19", "Driver X", "Term VCC/EGND", "Motor X Encoder", "Power Leads", "Red / White 0.5mm²", "+5V / 0V Encoder Power"], [TXT_MAIN, TXT_MAIN, C_5V, TXT_MAIN, C_5V, TXT_MAIN, C_5V]),
        (["20", "Driver Y", "Term A+ / A-", "Motor Y (Elevator)", "Phase A Leads", "Red / Blue 1.5mm²", "Motor Phase A Coils"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["21", "Driver Y", "Term B+ / B-", "Motor Y (Elevator)", "Phase B Leads", "Blk / Grn 1.5mm²", "Motor Phase B Coils"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["22", "Driver Z", "Term A+ / A-", "Motor Z (Pusher)", "Phase A Leads", "Red / Blue 0.75mm²", "Motor Phase A Coils"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["23", "Driver Z", "Term B+ / B-", "Motor Z (Pusher)", "Phase B Leads", "Blk / Grn 0.75mm²", "Motor Phase B Coils"], [TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
    ]
    y_r = 153.2
    for rdata, rcols in s4_wires:
        draw_table_row(ax, 152, y_r, s4_widths, rdata, rcols, bg='#EFF6FF' if 'STEP' in rdata[6] else BG_WHITE)
        y_r -= 3.8

    return fig

# =============================================================================
# MAIN EXPORT ROUTINE
# =============================================================================
def generate_all_pin_guide():
    base_dir = r"D:\37-Project Narit Vending Machine\Document\NaritVending"
    doc_dir  = r"D:\37-Project Narit Vending Machine\Document"
    sec_dir  = os.path.join(base_dir, "docs", "pin_to_pin_sections")
    doc_sec  = os.path.join(doc_dir, "pin_to_pin_sections")

    os.makedirs(sec_dir, exist_ok=True)
    os.makedirs(doc_sec, exist_ok=True)

    pdf_base = os.path.join(base_dir, "narit_vending_pin_to_pin_wiring_guide.pdf")
    pdf_docs = os.path.join(base_dir, "docs", "narit_vending_pin_to_pin_wiring_guide.pdf")
    pdf_main = os.path.join(doc_dir, "narit_vending_pin_to_pin_wiring_guide.pdf")

    poster_base = os.path.join(base_dir, "narit_vending_pin_to_pin_overview.png")
    poster_docs = os.path.join(base_dir, "docs", "narit_vending_pin_to_pin_overview.png")
    poster_main = os.path.join(doc_dir, "narit_vending_pin_to_pin_overview.png")

    pages = [
        ("page1_system_pin_overview", generate_page_1),
        ("page2_ac_mains_and_power_pin_to_pin", generate_page_2),
        ("page3_controllers_and_comm_pin_to_pin", generate_page_3),
        ("page4_sensors_pin_to_pin", generate_page_4),
        ("page5_stepper_motors_pin_to_pin", generate_page_5),
    ]

    print("Rendering Multi-Page Pin-to-Pin Wiring Guide (5 Pages)...")
    with PdfPages(pdf_base) as pdf:
        for idx, (name, gen_fn) in enumerate(pages):
            print(f"  Rendering Page {idx+1}: {name}...")
            fig = gen_fn()
            
            pdf.savefig(fig, bbox_inches='tight', facecolor=BG_WHITE)

            png_base = os.path.join(sec_dir, f"{name}.png")
            png_doc  = os.path.join(doc_sec, f"{name}.png")
            fig.savefig(png_base, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)
            fig.savefig(png_doc, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)

            if idx == 0:
                fig.savefig(poster_base, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)
                fig.savefig(poster_docs, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)
                fig.savefig(poster_main, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)

            plt.close(fig)

    shutil.copyfile(pdf_base, pdf_docs)
    shutil.copyfile(pdf_base, pdf_main)

    print("Complete Pin-to-Pin Wiring Guide Generated Successfully!")
    print(f"  -> Guide PDF:   {pdf_main}")
    print(f"  -> Overview PNG: {poster_main}")
    print(f"  -> Sheets Dir:  {doc_sec}")

if __name__ == "__main__":
    generate_all_pin_guide()
