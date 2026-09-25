# -*- coding: utf-8 -*-
"""
NARIT Vending Machine — Enhanced Electrical Schematic & Pinout Booklet
Designed directly from the system block diagram with large, highly legible fonts,
clean visual hierarchy, spacious component blocks, and detailed pinout tables.

Output:
- Multi-Page PDF: narit_vending_schematic_and_pinout_booklet.pdf
- Single-Page Poster PNG: narit_vending_system_block_and_pinout.png
- Section Sheets PNGs in: Document/schematic_sections/
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import os
import shutil

plt.rcParams['font.sans-serif'] = ['Leelawadee UI', 'Tahoma', 'Segoe UI', 'DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# Colors - Formal Industrial Engineering
BG_WHITE     = '#FFFFFF'
BORDER_NAVY  = '#0F2744'
BORDER_SLATE = '#475569'
BORDER_LIGHT = '#CBD5E1'

# Module Headers
HDR_NAVY   = '#0F2744'  # Controller / System
HDR_RED    = '#881337'  # Mains & Power
HDR_AMBER  = '#78350F'  # I/O & Sensors
HDR_TEAL   = '#064E3B'  # Motors & Actuators
HDR_SLATE  = '#1E293B'  # Drivers / Breakers

# Text Colors
TXT_MAIN   = '#0F172A'  # Dark slate/black (high contrast)
TXT_MUTED  = '#334155'  # Medium slate
TXT_BLUE   = '#0369A1'

# Wire & Bus Colors
C_AC_L     = '#B91C1C'  # AC Phase (Red)
C_AC_N     = '#1D4ED8'  # AC Neutral (Blue)
C_PE       = '#15803D'  # Earth (Green)
C_60V      = '#991B1B'  # +60VDC (Dark Red)
C_24V      = '#C2410C'  # +24VDC (Orange)
C_0V       = '#1E293B'  # 0V Ground (Slate Black)
C_5V       = '#7E22CE'  # +5VDC (Purple)
C_STEP     = '#0284C7'  # STEP Pulse (Sky Blue)
C_DIR      = '#B45309'  # DIR (Amber)
C_SIG      = '#0F766E'  # Sensor Signal (Teal)
C_ALM      = '#DC2626'  # Alarm / E-Stop (Red)
C_ETH      = '#1E3A8A'  # Ethernet (Navy)

def create_page(title, subtitle, section_tag=""):
    # Canvas size: 32 x 20 inches (Spacious 16:10 aspect ratio for maximum legibility)
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
            color='white', fontsize=13.5, fontweight='bold', va='center')

    ax.text(310, 188.5, "DOC: NARIT-VEND-E03 (REV 2.5)  |  TOR: 00-TOR-Vending-J69-290", 
            color='#38BDF8', fontsize=9.5, fontweight='bold', ha='right', va='center')
    if section_tag:
        ax.text(310, 184.2, f"SECTION: {section_tag.upper()}  |  VOLTAGE: 220VAC / 60VDC / 24VDC / 5VDC", 
                color='#E2E8F0', fontsize=8.5, ha='right', va='center')

    return fig, ax

def draw_card(ax, x, y, w, h, title, subtitle="", header_color=HDR_SLATE, bg=BG_WHITE, border=BORDER_SLATE):
    ax.add_patch(patches.Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=1.4))
    hdr_h = 4.2
    ax.add_patch(patches.Rectangle((x, y + h - hdr_h), w, hdr_h, facecolor=header_color, edgecolor=border, linewidth=1.0))
    ax.text(x + w/2, y + h - 1.8, title, color='white', fontsize=10.5, fontweight='bold', ha='center', va='center')
    if subtitle:
        ax.text(x + w/2, y + h - 3.2, subtitle, color='#E2E8F0', fontsize=7.8, ha='center', va='center')

def draw_table_header(ax, x, y, widths, titles, bg='#E2E8F0'):
    cur_x = x
    for w, t in zip(widths, titles):
        ax.add_patch(patches.Rectangle((cur_x, y), w, 4.0, facecolor=bg, edgecolor=BORDER_SLATE, linewidth=0.7))
        ax.text(cur_x + w/2, y + 2.0, t, color=BORDER_NAVY, fontsize=8.0, fontweight='bold', ha='center', va='center')
        cur_x += w

def draw_table_row(ax, x, y, widths, values, colors=None, bg=BG_WHITE):
    cur_x = x
    for i, (w, val) in enumerate(zip(widths, values)):
        ax.add_patch(patches.Rectangle((cur_x, y), w, 3.6, facecolor=bg, edgecolor=BORDER_LIGHT, linewidth=0.6))
        c = colors[i] if colors and i < len(colors) and colors[i] else TXT_MAIN
        # Left-aligned for text, centered for numbers/IDs
        ha = 'center' if i == 0 or len(val) <= 4 else 'left'
        tx = cur_x + w/2 if ha == 'center' else cur_x + 1.2
        ax.text(tx, y + 1.8, val, color=c, fontsize=7.6, fontweight='bold' if i == 0 else 'normal', ha=ha, va='center')
        cur_x += w

def draw_arrow(ax, x1, y1, x2, y2, color, lw=2.0, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw, shrinkA=2, shrinkB=2, mutation_scale=15))
    if label:
        mx, my = (x1 + x2)/2, (y1 + y2)/2
        ax.text(mx, my + 1.5, label, color=color, fontsize=7.5, fontweight='bold', ha='center', va='center')

# =============================================================================
# PAGE 1: ENHANCED SYSTEM BLOCK DIAGRAM & FLOW (Direct expansion from user image)
# =============================================================================
def generate_page_1_block_diagram():
    fig, ax = create_page("System Architecture & Electrical Flow Block Diagram", 
                          "Comprehensive System Architecture derived from Hardware Assembly", "Overview")

    # Group 1: AC Mains Supply & Filtering (Left Column, x: 10 to 60)
    draw_card(ax, 10, 105, 52, 68, "AC MAINS & FILTERING", "220VAC 1-Phase 50Hz", header_color=HDR_RED)
    
    # Inlet Box
    ax.add_patch(patches.Rectangle((14, 153), 44, 12, facecolor='#FEF2F2', edgecolor=BORDER_SLATE, linewidth=1))
    ax.text(36, 160.5, "AC MAINS INLET", fontsize=9.5, fontweight='bold', color=C_AC_L, ha='center')
    ax.text(36, 156.0, "220V / 50Hz (IEC C14)", fontsize=8.0, color=TXT_MUTED, ha='center')

    # MCB Box
    ax.add_patch(patches.Rectangle((14, 137), 44, 11, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1))
    ax.text(36, 144.0, "MCB 2-POLE (C16)", fontsize=9.0, fontweight='bold', color=TXT_MAIN, ha='center')
    ax.text(36, 140.0, "Main Overcurrent 16A", fontsize=7.5, color=TXT_MUTED, ha='center')

    # EMI Filter Box
    ax.add_patch(patches.Rectangle((14, 122), 44, 11, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1))
    ax.text(36, 129.0, "EMI NOISE FILTER", fontsize=9.0, fontweight='bold', color=TXT_MAIN, ha='center')
    ax.text(36, 125.0, "CW4L2-20A-S Noise Suppr.", fontsize=7.5, color=TXT_MUTED, ha='center')

    # Surge Protector Box
    ax.add_patch(patches.Rectangle((14, 108), 44, 11, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1))
    ax.text(36, 115.0, "SURGE PROTECTOR (SPD)", fontsize=9.0, fontweight='bold', color=TXT_MAIN, ha='center')
    ax.text(36, 111.0, "Type 2 Arrester Uc 275V", fontsize=7.5, color=TXT_MUTED, ha='center')

    # Flow arrows inside AC chain
    draw_arrow(ax, 36, 153, 36, 148, C_AC_L, lw=1.8)
    draw_arrow(ax, 36, 137, 36, 133, C_AC_L, lw=1.8)
    draw_arrow(ax, 36, 122, 36, 119, C_AC_L, lw=1.8)

    # AC Terminal Jumper Bus
    ax.add_patch(patches.Rectangle((10, 84), 52, 16, facecolor='#F1F5F9', edgecolor=BORDER_NAVY, linewidth=1.4))
    ax.text(36, 94.0, "AC TERMINAL JUMPER", fontsize=9.5, fontweight='bold', color=BORDER_NAVY, ha='center')
    ax.text(36, 88.0, "DIN Rail Power Bus (1-in 4-out)", fontsize=7.8, color=TXT_MUTED, ha='center')
    draw_arrow(ax, 36, 108, 36, 100, C_AC_L, lw=2.0)

    # Group 2: 3 DC Power Supplies (Middle-Left Column, x: 74 to 128)
    # PSU 1: 60V 6.7A
    draw_card(ax, 74, 124, 54, 49, "PSU 60VDC 6.7A (400W)", "Motors X & Y Power Supply", header_color=HDR_RED)
    ax.text(101, 157.0, "INPUT: 220VAC (L, N, FG)", fontsize=8.2, color=TXT_MAIN, ha='center')
    ax.text(101, 150.0, "OUTPUT: +60VDC & COM", fontsize=9.5, fontweight='bold', color=C_60V, ha='center')
    ax.text(101, 143.0, "Feeds Drivers X/Y via KM1", fontsize=8.0, color=TXT_MUTED, ha='center')
    ax.add_patch(patches.Rectangle((78, 128), 46, 10, facecolor='#FEF2F2', edgecolor=C_60V, linewidth=0.8))
    ax.text(101, 133.0, "KM1 SAFETY CUTOFF INTERLOCK", fontsize=7.5, fontweight='bold', color=C_60V, ha='center')

    # PSU 2: 24VDC 5A
    draw_card(ax, 74, 70, 54, 48, "PSU 24VDC 5A (120W)", "Industrial Control Power Supply", header_color=HDR_AMBER)
    ax.text(101, 103.0, "INPUT: 220VAC (L, N, FG)", fontsize=8.2, color=TXT_MAIN, ha='center')
    ax.text(101, 96.0, "OUTPUT: +24VDC & 0V", fontsize=9.5, fontweight='bold', color=C_24V, ha='center')
    ax.text(101, 89.0, "Mean Well DIN Rail NDR-120", fontsize=8.0, color=TXT_MUTED, ha='center')
    ax.text(101, 80.0, "Supplies IRiV IO, Sensors,\nV-PULSE & Z Drive (DM542)", fontsize=7.5, color=TXT_MAIN, ha='center')

    # PSU 3: USB-C 15W
    draw_card(ax, 74, 16, 54, 48, "PSU USB-C 15W (5V 3A)", "Dedicated CM4 Logic Power", header_color=HDR_SLATE)
    ax.text(101, 49.0, "INPUT: 220VAC 50Hz", fontsize=8.2, color=TXT_MAIN, ha='center')
    ax.text(101, 42.0, "OUTPUT: +5.1VDC 3.0A", fontsize=9.5, fontweight='bold', color=C_5V, ha='center')
    ax.text(101, 35.0, "Official Raspberry Pi Adapter", fontsize=8.0, color=TXT_MUTED, ha='center')
    ax.text(101, 26.0, "Isolated Logic Rail\nProtects from ground loops", fontsize=7.5, color=TXT_MAIN, ha='center')

    # Distribute AC from Terminal Jumper to 3 PSUs
    ax.plot([62, 68, 68], [92, 92, 148], color=C_AC_L, lw=2.0)
    draw_arrow(ax, 68, 148, 74, 148, C_AC_L, lw=2.0)
    draw_arrow(ax, 62, 92, 74, 92, C_AC_L, lw=2.0)
    ax.plot([62, 68, 68], [92, 92, 40], color=C_AC_L, lw=2.0)
    draw_arrow(ax, 68, 40, 74, 40, C_AC_L, lw=2.0)

    # Group 3: Stepper Motor Drivers (Middle-Top, x: 142 to 198)
    # Driver X
    draw_card(ax, 142, 144, 56, 29, "DRIVER STEPPING MOTOR (X)", "Leadshine HBS860H Closed-Loop", header_color=HDR_SLATE)
    ax.text(170, 162.0, "+60VDC Motor Power (from KM1)", fontsize=7.8, color=C_60V, ha='center', fontweight='bold')
    ax.text(170, 156.0, "PUL/DIR Signals from STM32", fontsize=7.8, color=C_STEP, ha='center')
    ax.text(170, 149.0, "ALM -> PiControl DI0 | PEND -> DI2", fontsize=7.5, color=C_ALM, ha='center')

    # Driver Y
    draw_card(ax, 142, 110, 56, 29, "DRIVER STEPPING MOTOR (Y)", "Leadshine HBS860H Closed-Loop", header_color=HDR_SLATE)
    ax.text(170, 128.0, "+60VDC Motor Power (from KM1)", fontsize=7.8, color=C_60V, ha='center', fontweight='bold')
    ax.text(170, 122.0, "PUL/DIR Signals from STM32", fontsize=7.8, color=C_STEP, ha='center')
    ax.text(170, 115.0, "ALM -> PiControl DI1 | PEND -> DI3", fontsize=7.5, color=C_ALM, ha='center')

    # Driver Z
    draw_card(ax, 142, 76, 56, 29, "DRIVER STEPPING MOTOR (Z)", "Leadshine DM542 Microstepping", header_color=HDR_SLATE)
    ax.text(170, 94.0, "+24VDC Power (from PSU 2)", fontsize=7.8, color=C_24V, ha='center', fontweight='bold')
    ax.text(170, 88.0, "PUL/DIR Signals from STM32", fontsize=7.8, color=C_STEP, ha='center')
    ax.text(170, 81.0, "Peak 2.0A, Microstep 1600", fontsize=7.5, color=TXT_MUTED, ha='center')

    # Connect 60V PSU to Drivers X and Y
    ax.plot([128, 135, 135], [148, 148, 158], color=C_60V, lw=2.2)
    draw_arrow(ax, 135, 158, 142, 158, C_60V, lw=2.2)
    draw_arrow(ax, 135, 124, 142, 124, C_60V, lw=2.2)
    # Connect 24V PSU to Driver Z
    ax.plot([128, 135, 135], [92, 92, 90], color=C_24V, lw=2.0)
    draw_arrow(ax, 135, 90, 142, 90, C_24V, lw=2.0)

    # Group 4: Stepper Motors & Actuators (Top Right, x: 212 to 268)
    # Motor X
    draw_card(ax, 212, 144, 56, 29, "X AXIS HYBRID STEPPER", "NEMA 34 (8.5 N.m) + 1000 CPR Encoder", header_color=HDR_TEAL)
    ax.text(240, 162.0, "HTD 5M 25mm Timing Belt Drive", fontsize=8.0, color=TXT_MAIN, ha='center')
    ax.text(240, 156.0, "Carriage Horizontal Travel (450 mm/s)", fontsize=7.5, color=TXT_MUTED, ha='center')
    ax.text(240, 149.0, "Kinematics: 78.43 steps/mm", fontsize=7.5, color=BORDER_NAVY, fontweight='bold', ha='center')

    # Motor Y
    draw_card(ax, 212, 110, 56, 29, "Y AXIS HYBRID STEPPER", "NEMA 34 (8.5 N.m) + SFU1605 Ball Screw", header_color=HDR_TEAL)
    ax.text(240, 128.0, "SFU1605 Precision Ball Screw (Lead 5mm)", fontsize=8.0, color=TXT_MAIN, ha='center')
    ax.text(240, 122.0, "Vertical Elevator Lift (120 mm/s)", fontsize=7.5, color=TXT_MUTED, ha='center')
    ax.text(240, 115.0, "Kinematics: 320.00 steps/mm", fontsize=7.5, color=BORDER_NAVY, fontweight='bold', ha='center')

    # Motor Z
    draw_card(ax, 212, 76, 56, 29, "Z AXIS V-SLOT MINI ACTUATOR", "NEMA 17 Stepper (T8x8 Lead Screw)", header_color=HDR_TEAL)
    ax.text(240, 94.0, "V-Slot Linear Actuator (150mm Stroke)", fontsize=8.0, color=TXT_MAIN, ha='center')
    ax.text(240, 88.0, "Product Dispense Push Rod Mechanism", fontsize=7.5, color=TXT_MUTED, ha='center')
    ax.text(240, 81.0, "Kinematics: 200.00 steps/mm", fontsize=7.5, color=BORDER_NAVY, fontweight='bold', ha='center')

    # Connect Drivers to Motors
    draw_arrow(ax, 198, 158, 212, 158, BORDER_NAVY, lw=2.0, label="Coils + Enc")
    draw_arrow(ax, 198, 124, 212, 124, BORDER_NAVY, lw=2.0, label="Coils + Enc")
    draw_arrow(ax, 198, 90, 212, 90, BORDER_NAVY, lw=2.0, label="4-Wire Coils")

    # Group 5: Main Controller (IRiV PiControl CM4) (Center, x: 142 to 198, y: 16 to 66)
    draw_card(ax, 142, 16, 56, 50, "IRIV PiControl CM4", "Raspberry Pi CM4 (4GB RAM, 32GB eMMC)", header_color=HDR_NAVY)
    ax.text(170, 56.0, "MAIN CONTROLLER & HMI HOST", fontsize=8.5, fontweight='bold', color=BORDER_NAVY, ha='center')
    ax.text(170, 50.0, "Power: 5V 3A (USB-C) + 24V Aux", fontsize=7.8, color=C_5V, ha='center')
    ax.text(170, 44.0, "Dual LAN: eth0 (MGMT) / eth1 (OT)", fontsize=7.8, color=C_ETH, ha='center')
    ax.text(170, 38.0, "USB4: ST-LINK to STM32 (115200)", fontsize=7.8, color=C_ALM, ha='center')
    ax.text(170, 32.0, "DI0-DI3: Driver Alarms & In-Position", fontsize=7.5, color=TXT_MUTED, ha='center')
    ax.text(170, 26.0, "DO0: KM1 Contactor Safety Reset", fontsize=7.5, color=C_24V, ha='center')

    # Connect 24V and 5V PSUs to PiControl
    ax.plot([128, 135, 135], [40, 40, 30], color=C_5V, lw=2.0)
    draw_arrow(ax, 135, 30, 142, 30, C_5V, lw=2.0, label="5V")

    # Group 6: Remote Field I/O (IRiV IO Controller) (x: 212 to 260, y: 16 to 66)
    draw_card(ax, 212, 16, 48, 50, "IRIV IO CONTROLLER", "Modbus TCP Remote Field I/O (24VDC)", header_color=HDR_AMBER)
    ax.text(236, 56.0, "FIELD I/O INTERFACE", fontsize=8.5, fontweight='bold', color=HDR_AMBER, ha='center')
    ax.text(236, 50.0, "IP: 10.0.0.10:502 (Modbus TCP)", fontsize=7.8, color=C_ETH, ha='center')
    ax.text(236, 44.0, "11 x Digital Inputs (24V Opto)", fontsize=7.8, color=C_SIG, ha='center', fontweight='bold')
    ax.text(236, 38.0, "4 x Digital Outputs (SSR/Relay)", fontsize=7.8, color=TXT_MAIN, ha='center')
    ax.text(236, 30.0, "Polled by PiControl every 20ms", fontsize=7.5, color=TXT_MUTED, ha='center')

    # Connect PiControl eth1 to IRiV IO Modbus
    draw_arrow(ax, 198, 41, 212, 41, C_ETH, lw=2.2, label="Modbus TCP")

    # Group 7: USB Peripherals (Bottom Row below PiControl, y: 3 to 14)
    periphs = [
        ("ETHERNET LAN", "eth0 / REST API", 136, 24, C_ETH),
        ("SCANNER QR", "Barcode/QR CDC", 163, 24, C_5V),
        ("WEB CAM", "FHD 1080p UVC", 190, 24, C_5V),
        ("SPEAKER", "Voice Guidance", 217, 24, C_5V),
    ]
    for pname, psub, px, pw, pcol in periphs:
        ax.add_patch(patches.Rectangle((px, 3), pw, 10, facecolor='#F8FAFC', edgecolor=BORDER_SLATE, linewidth=0.8))
        ax.text(px + pw/2, 9.5, pname, fontsize=7.2, fontweight='bold', color=pcol, ha='center')
        ax.text(px + pw/2, 5.5, psub, fontsize=6.2, color=TXT_MUTED, ha='center')
        draw_arrow(ax, px + pw/2, 16, px + pw/2, 13, pcol, lw=1.2)

    # Group 8: Field Sensors (Far Right Column, x: 274 to 314)
    # Optical Sensors (Top)
    draw_card(ax, 274, 130, 40, 43, "OPTICAL SENSORS", "Omron E3Z-D81 (24VDC)", header_color=HDR_AMBER)
    ax.add_patch(patches.Rectangle((277, 151), 34, 10, facecolor='#FEF2F2', edgecolor=C_ALM, linewidth=0.8))
    ax.text(294, 157.0, "COMPLETED SENSOR x 1", fontsize=7.5, fontweight='bold', color=C_ALM, ha='center')
    ax.text(294, 153.0, "DI8: Drop Beam Verification", fontsize=6.8, color=TXT_MUTED, ha='center')

    ax.add_patch(patches.Rectangle((277, 136), 34, 10, facecolor='#FEF2F2', edgecolor=C_ALM, linewidth=0.8))
    ax.text(294, 142.0, "ALARM / PICKUP SENSOR x 1", fontsize=7.5, fontweight='bold', color=C_ALM, ha='center')
    ax.text(294, 138.0, "DI9: Pickup Door Access", fontsize=6.8, color=TXT_MUTED, ha='center')

    # Limit Sensors (Bottom)
    draw_card(ax, 274, 16, 40, 106, "PROXIMITY LIMIT SENSORS", "24VDC Inductive PNP (NC)", header_color=HDR_NAVY)
    limits = [
        ("Limit Min X Axis Sensor x 1", "DI0: X Min Limit (NC)", C_SIG),
        ("Limit Max X Axis Sensor x 1", "DI1: X Max Limit (NC)", C_SIG),
        ("Limit Min Y Axis Sensor x 1", "DI2: Y Min Limit (NC)", C_SIG),
        ("Limit Max Y Axis Sensor x 1", "DI3: Y Max Limit (NC)", C_SIG),
        ("Limit Min Z Axis Sensor x 1", "DI4: Z Min Limit (NC)", C_SIG),
        ("Limit Max Z Axis Sensor x 1", "DI5: Z Max Limit (NC)", C_SIG),
    ]
    y_lim = 100
    for lname, lsub, lcol in limits:
        ax.add_patch(patches.Rectangle((277, y_lim), 34, 10, facecolor='#EFF6FF', edgecolor=BORDER_LIGHT, linewidth=0.8))
        ax.text(294, y_lim + 6.0, lname, fontsize=7.0, fontweight='bold', color=BORDER_NAVY, ha='center')
        ax.text(294, y_lim + 2.5, lsub, fontsize=6.5, color=lcol, ha='center')
        y_lim -= 13.0

    # Route green lines from IRiV IO to sensors
    ax.plot([260, 268, 268], [41, 41, 151], color=C_SIG, lw=1.8)
    draw_arrow(ax, 268, 151, 274, 151, C_SIG, lw=1.8)
    ax.plot([268, 268], [151, 65], color=C_SIG, lw=1.8)
    draw_arrow(ax, 268, 65, 274, 65, C_SIG, lw=1.8)

    return fig

# =============================================================================
# PAGE 2: SECTION 1 — AC MAINS DISTRIBUTION & POWER SUPPLIES PINOUT
# =============================================================================
def generate_page_2_power():
    fig, ax = create_page("Section 1: AC Mains Distribution & DC Power Supplies", 
                          "Electrical Schematic, Terminal Blocks, and Power Distribution Pinout", "Section 1")

    # Left Side: AC Distribution Schematic Block (x: 10 to 155, y: 15 to 175)
    draw_card(ax, 10, 15, 145, 160, "AC MAINS & POWER INTERLOCK SCHEMATIC", 
              "Single-Phase 220VAC 50Hz, Circuit Protection, and KM1 Safety Contactor", header_color=HDR_RED)

    # 1. Inlet
    ax.add_patch(patches.Rectangle((16, 145), 36, 22, facecolor='#FEF2F2', edgecolor=BORDER_SLATE, linewidth=1.2))
    ax.text(34, 161.0, "AC INLET (IEC C14)", fontsize=9.0, fontweight='bold', color=C_AC_L, ha='center')
    ax.text(34, 156.0, "L (Line) : 220VAC Brown\nN (Neutral) : 0VAC Blue\nPE (Earth) : Green/Yellow", fontsize=7.5, color=TXT_MAIN, ha='center')
    ax.text(34, 148.0, "Fuse 10A / 250V", fontsize=7.0, color=TXT_MUTED, ha='center')

    # 2. MCB
    ax.add_patch(patches.Rectangle((62, 145), 38, 22, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1.2))
    ax.text(81, 161.0, "MCB 2P (C16)", fontsize=9.0, fontweight='bold', color=BORDER_NAVY, ha='center')
    ax.text(81, 155.0, "Term 1 (L_in) -> 2 (L_out)\nTerm 3 (N_in) -> 4 (N_out)", fontsize=7.5, color=TXT_MAIN, ha='center')
    ax.text(81, 148.0, "Trip: In 16A, Icu 6kA", fontsize=7.0, color=TXT_MUTED, ha='center')

    # 3. EMI Filter
    ax.add_patch(patches.Rectangle((110, 145), 40, 22, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1.2))
    ax.text(130, 161.0, "EMI FILTER", fontsize=9.0, fontweight='bold', color=BORDER_NAVY, ha='center')
    ax.text(130, 155.0, "CW4L2-20A-S Filter\nL, N In -> L', N' Out", fontsize=7.5, color=TXT_MAIN, ha='center')
    ax.text(130, 148.0, "FG Chassis Earth", fontsize=7.0, color=C_PE, ha='center')

    # Connect AC stages
    draw_arrow(ax, 52, 156, 62, 156, C_AC_L, lw=2.0)
    draw_arrow(ax, 100, 156, 110, 156, C_AC_L, lw=2.0)

    # 4. SPD & AC Terminal Bus
    ax.add_patch(patches.Rectangle((16, 105), 50, 30, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1.2))
    ax.text(41, 129.0, "SURGE ARRESTER (SPD)", fontsize=8.8, fontweight='bold', color=BORDER_NAVY, ha='center')
    ax.text(41, 122.0, "Type 2 DIN Arrester", fontsize=7.5, color=TXT_MUTED, ha='center')
    ax.text(41, 115.0, "L, N In -> PE (Ground)", fontsize=7.5, color=TXT_MAIN, ha='center')
    ax.text(41, 108.0, "Uc: 275V | Imax: 20kA", fontsize=7.0, color=C_PE, ha='center')

    ax.add_patch(patches.Rectangle((76, 105), 74, 30, facecolor='#F1F5F9', edgecolor=BORDER_NAVY, linewidth=1.4))
    ax.text(113, 129.0, "AC TERMINAL JUMPER BUS", fontsize=9.2, fontweight='bold', color=BORDER_NAVY, ha='center')
    ax.text(113, 122.0, "TB-L: 220VAC Live Bus (1-in 4-out)", fontsize=7.8, color=C_AC_L, ha='center', fontweight='bold')
    ax.text(113, 115.0, "TB-N: Neutral Return Bus (1-in 4-out)", fontsize=7.8, color=C_AC_N, ha='center', fontweight='bold')
    ax.text(113, 108.0, "TB-PE: Protective Earth Bus (Chassis)", fontsize=7.8, color=C_PE, ha='center', fontweight='bold')

    ax.plot([130, 130, 113], [145, 139, 139], color=C_AC_L, lw=2.0)
    draw_arrow(ax, 113, 139, 113, 135, C_AC_L, lw=2.0)

    # 5. KM1 Safety Contactor (Bottom half of left card)
    ax.add_patch(patches.Rectangle((16, 22), 134, 75, facecolor='#FFFFFF', edgecolor=HDR_RED, linewidth=1.4))
    ax.text(83, 91.0, "KM1 SAFETY CONTACTOR & HARDWARE POWER CUTOFF", fontsize=9.5, fontweight='bold', color=HDR_RED, ha='center')
    
    # Schematic box of KM1
    km1_desc = [
        ("MAIN CONTACTS (1-2)", "+60VDC Line In (PSU 1) -> +60VDC Out to Drivers X/Y", C_60V),
        ("MAIN CONTACTS (3-4)", "0VDC Return In (PSU 1) -> 0VDC Out to Drivers X/Y", C_0V),
        ("COIL TERMINALS (A1-A2)", "24VDC Coil driven by PiControl DO0 in series with E-Stop NC", C_24V),
        ("AUX CONTACT (21-22 NC)", "Hardware Armature Feedback wired to IRiV IO DI10 (Fail-Safe)", C_ALM),
        ("AUX CONTACT (13-14 NO)", "Spare Auxiliary Signaling / Indicator Light", TXT_MUTED),
    ]
    y_km = 82
    for ctitle, cdesc, ccol in km1_desc:
        ax.add_patch(patches.Rectangle((20, y_km), 126, 9.5, facecolor='#F8FAFC', edgecolor=BORDER_LIGHT, linewidth=0.7))
        ax.text(23, y_km + 5.5, ctitle, fontsize=7.8, fontweight='bold', color=ccol)
        ax.text(23, y_km + 1.8, cdesc, fontsize=7.2, color=TXT_MAIN)
        y_km -= 11.0

    ax.text(83, 26.0, "SAFETY PRINCIPLE: E-Stop hard-drops coil voltage without software dependency.", fontsize=7.2, color=HDR_RED, fontweight='bold', ha='center')

    # Right Side: Detailed Pinout & Terminal Tables (x: 165 to 310, y: 15 to 175)
    draw_card(ax, 165, 15, 145, 160, "POWER SUPPLIES TERMINAL PINOUT SCHEDULE", 
              "Terminal Numbers, Signal Names, Voltages, Wire Gauges & Color Codes", header_color=BORDER_NAVY)

    # Table 1: PSU 1 (60V 6.7A)
    ax.text(168, 167.0, "1. PSU 1: 60VDC 6.7A (400W) TERMINAL PINOUT:", fontsize=8.5, fontweight='bold', color=HDR_RED)
    widths_p1 = [22, 28, 30, 24, 37]
    draw_table_header(ax, 168, 157.0, widths_p1, ["TERM", "PIN NAME", "VOLTAGE / TYPE", "WIRE GAUGE", "DESTINATION / REMARKS"])
    p1_rows = [
        (["L", "AC Input Line", "220VAC 50Hz", "2.5 mm² Brown", "From TB-L Bus"], [C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["N", "AC Input Neutral", "0VAC Neutral", "2.5 mm² Blue", "From TB-N Bus"], [C_AC_N, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["FG", "Chassis Earth", "Ground Bar", "2.5 mm² Grn/Yel", "From TB-PE Earth Bar"], [C_PE, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["+V (x2)", "+60VDC Output", "+60VDC Bus", "2.5 mm² Red", "To KM1 Contact 1 (L1)"], [C_60V, C_60V, C_60V, TXT_MAIN, C_60V]),
        (["-V (x2)", "0VDC Output", "0V Return / COM", "2.5 mm² Black", "To KM1 Contact 3 (L2)"], [C_0V, C_0V, C_0V, TXT_MAIN, C_0V]),
        (["V-ADJ", "Voltage Trimmer", "58V - 62V Adj.", "Internal Pot", "Calibrated to 60.0VDC"], [TXT_MUTED, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
    ]
    y_r = 153.4
    for rdata, rcols in p1_rows:
        draw_table_row(ax, 168, y_r, widths_p1, rdata, rcols, bg='#FEF2F2' if '+V' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # Table 2: PSU 2 (24VDC 5A)
    ax.text(168, 126.0, "2. PSU 2: 24VDC 5A (120W MEAN WELL) TERMINAL PINOUT:", fontsize=8.5, fontweight='bold', color=HDR_AMBER)
    widths_p2 = [22, 28, 30, 24, 37]
    draw_table_header(ax, 168, 116.0, widths_p2, ["TERM", "PIN NAME", "VOLTAGE / TYPE", "WIRE GAUGE", "DESTINATION / REMARKS"])
    p2_rows = [
        (["L", "AC Input Line", "220VAC 50Hz", "1.5 mm² Brown", "From TB-L Bus"], [C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["N", "AC Input Neutral", "0VAC Neutral", "1.5 mm² Blue", "From TB-N Bus"], [C_AC_N, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["FG", "Chassis Earth", "Ground Bar", "1.5 mm² Grn/Yel", "From TB-PE Earth Bar"], [C_PE, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["+24V (x2)", "+24VDC Output", "+24VDC Control", "1.5 mm² Orange", "IRiV IO, Sensors, V-PULSE"], [C_24V, C_24V, C_24V, TXT_MAIN, C_24V]),
        (["0V (x2)", "0VDC Output", "0V Return / COM", "1.5 mm² Black", "IRiV IO, Sensors 0V, MCU GND"], [C_0V, C_0V, C_0V, TXT_MAIN, C_0V]),
        (["DC OK", "Relay Contact", "Dry Contact", "0.5 mm² Pair", "Optional PSU status alert"], [C_PE, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
    ]
    y_r = 112.4
    for rdata, rcols in p2_rows:
        draw_table_row(ax, 168, y_r, widths_p2, rdata, rcols, bg='#FFF7ED' if '+24V' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # Table 3: PSU 3 (5V 3A USB-C)
    ax.text(168, 85.0, "3. PSU 3: 5VDC 3A (15W USB-C) TERMINAL PINOUT:", fontsize=8.5, fontweight='bold', color=HDR_SLATE)
    widths_p3 = [22, 28, 30, 24, 37]
    draw_table_header(ax, 168, 75.0, widths_p3, ["TERM", "PIN NAME", "VOLTAGE / TYPE", "WIRE GAUGE", "DESTINATION / REMARKS"])
    p3_rows = [
        (["AC IN", "2-Pin Euro/US", "100-240VAC", "Molded Cord", "From AC Socket / Bus"], [C_AC_L, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["VBUS", "USB-C Pin A4/B9", "+5.1VDC Power", "18 AWG Wire", "PiControl USB-C Port"], [C_5V, C_5V, C_5V, TXT_MAIN, C_5V]),
        (["GND", "USB-C Pin A1/B12", "0V Power Return", "18 AWG Wire", "PiControl USB-C Port"], [C_0V, C_0V, C_0V, TXT_MAIN, C_0V]),
        (["ISOLATION", "Galvanic Barrier", "Reinforced 3kV", "Internal Xfmr", "Prevents Ground Loops"], [TXT_MUTED, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
    ]
    y_r = 71.4
    for rdata, rcols in p3_rows:
        draw_table_row(ax, 168, y_r, widths_p3, rdata, rcols, bg='#FAF5FF' if 'VBUS' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # Engineering Notes Box at bottom
    ax.add_patch(patches.Rectangle((168, 18), 141, 35, facecolor='#F8FAFC', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(171, 48.0, "ELECTRICAL CODE & WIRE COLOR SPECIFICATIONS (IEC 60204-1):", fontsize=7.5, fontweight='bold', color=BORDER_NAVY)
    ax.text(171, 43.5, "• AC Mains Power Lines: Phase = Brown (2.5 mm²), Neutral = Light Blue (2.5 mm²), Earth = Green/Yellow.", fontsize=6.8, color=TXT_MAIN)
    ax.text(171, 39.0, "• DC High Voltage Power (+60V): Red (2.5 mm²), Return COM = Black (2.5 mm²). Separated from logic.", fontsize=6.8, color=C_60V)
    ax.text(171, 34.5, "• DC Low Voltage Control (+24V): Orange (1.0 mm²), Return (0V) = Black (1.0 mm²).", fontsize=6.8, color=C_24V)
    ax.text(171, 30.0, "• Earth Bonding: Cabinet metal frame, din rails, and motor casings bonded to PE bar with <= 0.1 Ohm.", fontsize=6.8, color=C_PE)
    ax.text(171, 24.0, "• Wireways: Power wires (AC 220V, DC 60V) routed in left duct; low-voltage signals in right duct.", fontsize=6.8, color=TXT_MUTED)

    return fig

# =============================================================================
# PAGE 3: SECTION 2 — CONTROLLERS & COMMUNICATION PINOUT (PiControl & IRiV IO)
# =============================================================================
def generate_page_3_controllers():
    fig, ax = create_page("Section 2: Controllers & Communication Architecture", 
                          "Cytron IRiV PiControl CM4, IRiV IO Modbus TCP, Dual Subnets & Peripheral Pinouts", "Section 2")

    # Left Side: Cytron IRiV PiControl CM4 (x: 10 to 160)
    draw_card(ax, 10, 15, 150, 160, "Cytron IRiV PiControl CM4 (MAIN CONTROLLER)", 
              "Raspberry Pi CM4 (4GB RAM, 32GB eMMC, Dual Ethernet, Isolated GPIOs)", header_color=HDR_NAVY)

    # Sub-block: Ethernet & USB interfaces
    ax.text(14, 167.0, "1. DUAL GIGABIT ETHERNET & USB PORTS:", fontsize=8.5, fontweight='bold', color=BORDER_NAVY)
    widths_net = [28, 30, 24, 60]
    draw_table_header(ax, 14, 157.0, widths_net, ["INTERFACE", "IP / PROTOCOL", "CONNECTOR", "FUNCTION & DESTINATION"])
    net_rows = [
        (["eth0 (MGMT)", "192.168.70.80 / 24", "RJ45 (GbE)", "HMI Kiosk Web Port 80, REST API, MQTT Broker"], [C_ETH, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["eth1 (OT LAN)", "10.0.0.2 / 24", "RJ45 (GbE)", "Modbus TCP Master to IRiV IO (10.0.0.10:502)"], [C_ETH, C_ETH, TXT_MAIN, C_ETH]),
        (["USB 1", "USB CDC Serial", "USB 2.0 Type-A", "2D Barcode & QR Code Payment Scanner"], [C_5V, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["USB 2", "USB Video UVC", "USB 2.0 Type-A", "FHD 1080p Web Camera (Drop / Pickup Vision)"], [C_5V, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["USB 3 / 3.5mm", "Audio DAC Output", "3.5mm / USB", "Voice Guidance & Chime Speaker (3W)"], [C_5V, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["USB 4", "115200 8-N-1 VCP", "USB 2.0 Type-A", "Safe-Link v3 Binary Protocol to STM32 NUCLEO"], [C_ALM, C_ALM, TXT_MAIN, C_ALM]),
    ]
    y_r = 153.4
    for rdata, rcols in net_rows:
        draw_table_row(ax, 14, y_r, widths_net, rdata, rcols)
        y_r -= 3.6

    # Sub-block: Local Isolated GPIO Terminal Block
    ax.text(14, 126.0, "2. LOCAL ISOLATED GPIO TERMINAL PINOUT (24VDC CHANNELS):", fontsize=8.5, fontweight='bold', color=BORDER_NAVY)
    widths_gpio = [24, 22, 28, 24, 44]
    draw_table_header(ax, 14, 116.0, widths_gpio, ["TERMINAL", "BCM PIN", "SIGNAL NAME", "DIRECTION", "ELECTRICAL FUNCTION & INTERLOCK"])
    gpio_rows = [
        (["DI0", "GPIO 13", "X_DRIVE_ALM", "Input (Opto)", "Driver X Alarm (Active HIGH, Fail-safe)"], [C_ALM, TXT_MUTED, C_ALM, TXT_MAIN, C_ALM]),
        (["DI1", "GPIO 17", "Y_DRIVE_ALM", "Input (Opto)", "Driver Y Alarm (Active HIGH, Fail-safe)"], [C_ALM, TXT_MUTED, C_ALM, TXT_MAIN, C_ALM]),
        (["DI2", "GPIO 27", "X_PEND", "Input (Opto)", "Driver X In-Position Verification Signal"], [C_DIR, TXT_MUTED, C_DIR, TXT_MAIN, TXT_MAIN]),
        (["DI3", "GPIO 22", "Y_PEND", "Input (Opto)", "Driver Y In-Position Verification Signal"], [C_DIR, TXT_MUTED, C_DIR, TXT_MAIN, TXT_MAIN]),
        (["DO0", "GPIO 23", "XY_DRIVE_POWER", "Output (Relay)", "KM1 Safety Contactor Driver (3.0s Auto-Reset)"], [C_24V, TXT_MUTED, C_24V, TXT_MAIN, C_24V]),
        (["DO1", "GPIO 24", "RELAY_AUX_1", "Output (Relay)", "Auxiliary 24V SSR Driver (Spare Channel 1)"], [TXT_MUTED, TXT_MUTED, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
        (["DO2", "GPIO 25", "RELAY_AUX_2", "Output (Relay)", "Auxiliary 24V SSR Driver (Spare Channel 2)"], [TXT_MUTED, TXT_MUTED, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
        (["DO3", "GPIO 16", "RELAY_AUX_3", "Output (Relay)", "Auxiliary 24V SSR Driver (Spare Channel 3)"], [TXT_MUTED, TXT_MUTED, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
        (["24V IN", "Power V+", "+24VDC Supply", "Power In", "From PSU 2 Control Rail (Orange wire)"], [C_24V, TXT_MUTED, C_24V, TXT_MAIN, C_24V]),
        (["0V IN", "Power V-", "0VDC Return", "Power In", "From PSU 2 Control Rail (Black wire)"], [C_0V, TXT_MUTED, C_0V, TXT_MAIN, C_0V]),
    ]
    y_r = 112.4
    for rdata, rcols in gpio_rows:
        draw_table_row(ax, 14, y_r, widths_gpio, rdata, rcols, bg='#FEF2F2' if 'ALM' in rdata[2] else BG_WHITE)
        y_r -= 3.6

    # Software Service Gate Card (Bottom)
    ax.add_patch(patches.Rectangle((14, 20), 142, 50, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(17, 65.0, "SYSTEM SOFTWARE SERVICES & RUNTIME DAEMONS:", fontsize=7.8, fontweight='bold', color=BORDER_NAVY)
    ax.text(17, 60.5, "• narit-vending-web-iriv.service : Flask Touchscreen Kiosk UI on localhost:80.", fontsize=7.0, color=TXT_MAIN)
    ax.text(17, 56.0, "• narit-vending-controller-iriv.service : Core safety state machine and hardware gateway.", fontsize=7.0, color=TXT_MAIN)
    ax.text(17, 51.5, "• IPC Socket Bus : /run/narit-vending/ctrl.sock (Non-blocking Unix Domain Socket).", fontsize=7.0, color=TXT_MAIN)
    ax.text(17, 47.0, "• Cyclic Modbus Polling : Master polls IRiV IO every 20ms; Disarms if data stale > 350ms.", fontsize=7.0, color=C_ALM, fontweight='bold')
    ax.text(17, 42.5, "• Safe-Link v3 Motion Protocol : CRC-16 validated frames; 500ms heartbeat timeout watchdog.", fontsize=7.0, color=BORDER_NAVY)
    ax.text(17, 38.0, "• Hardware Fault Reset : PiControl DO0 drops KM1 for 3s to discharge motor driver fault registers.", fontsize=7.0, color=C_24V)
    ax.text(17, 33.5, "• Telemetry Cloud Sync : MQTT client connects to broker.emqx.io:1883 for remote monitoring.", fontsize=7.0, color=C_ETH)
    ax.text(17, 28.0, "• Database : Local SQLite database persists inventory slots, motor kinematics & logs.", fontsize=7.0, color=TXT_MUTED)

    # Right Side: Cytron IRiV IO Modbus Controller (x: 168 to 310)
    draw_card(ax, 168, 15, 142, 160, "Cytron IRiV IO REMOTE FIELD CONTROLLER", 
              "Modbus TCP Slave (IP: 10.0.0.10:502, Unit ID: 255) — 11 DI, 4 DO", header_color=HDR_AMBER)

    # Table of 11 Digital Inputs
    ax.text(171, 167.0, "1. DIGITAL INPUTS (DI0 - DI10) PINOUT & MAPPING:", fontsize=8.5, fontweight='bold', color=HDR_AMBER)
    widths_di = [16, 26, 32, 28, 36]
    draw_table_header(ax, 171, 157.0, widths_di, ["CH", "NAME", "CONNECTED SENSOR", "LOGIC STATE", "BEHAVIOR & SAFETY ACTION"])
    di_table = [
        (["DI0", "x_head_limit", "Limit Min X Axis Sensor", "Normally Closed (NC)", "Stops X Reverse Motion (Home)"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["DI1", "x_tail_limit", "Limit Max X Axis Sensor", "Normally Closed (NC)", "Stops X Forward Motion"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["DI2", "y_head_limit", "Limit Min Y Axis Sensor", "Normally Closed (NC)", "Stops Y Down Motion (Drop level)"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["DI3", "y_tail_limit", "Limit Max Y Axis Sensor", "Normally Closed (NC)", "Stops Y Up Motion (Top level)"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["DI4", "z_head_limit", "Limit Min Z Axis Sensor", "Normally Closed (NC)", "Stops Z Retract (Pusher Home)"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["DI5", "z_tail_limit", "Limit Max Z Axis Sensor", "Normally Closed (NC)", "Stops Z Extend (Pusher Max)"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["DI6", "z_home", "Z Home Reference Sensor", "Normally Open (NO)", "Reference datum sensor for Z"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
        (["DI7", "drop_park", "Drop Alignment Proximity", "Normally Open (NO)", "Confirms carriage aligns with chute"], [C_SIG, TXT_MAIN, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
        (["DI8", "drop_sens", "Completed Sensor (Omron)", "Beam Interrupted", "Verifies product successfully dropped"], [C_ALM, C_ALM, TXT_MAIN, TXT_MAIN, C_ALM]),
        (["DI9", "pick_sens", "Alarm Sensor (Omron E3Z)", "Door Flap Opened", "Detects user hand / door open access"], [C_ALM, C_ALM, TXT_MAIN, TXT_MAIN, C_ALM]),
        (["DI10", "estop_fb", "KM1 Contactor Aux NC", "Fail-Safe NC Loop", "Active LOW; loop break trips E-Stop"], [C_ALM, C_ALM, C_ALM, C_ALM, C_ALM]),
    ]
    y_r = 153.4
    for rdata, rcols in di_table:
        draw_table_row(ax, 171, y_r, widths_di, rdata, rcols, bg='#FEF2F2' if 'DI10' in rdata[0] or 'DI8' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # Table of 4 Digital Outputs
    ax.text(171, 110.0, "2. DIGITAL OUTPUTS (DO0 - DO3) PINOUT & INDICATORS:", fontsize=8.5, fontweight='bold', color=HDR_AMBER)
    widths_do = [16, 26, 32, 28, 36]
    draw_table_header(ax, 171, 100.0, widths_do, ["CH", "NAME", "LOAD DEVICE", "OUTPUT TYPE", "OPERATIONAL CONDITION"])
    do_table = [
        (["DO0", "ready", "Green Pilot Light", "24V / 0.5A SSR", "Solid ON when system armed & idle"], [C_PE, TXT_MAIN, C_PE, TXT_MAIN, TXT_MAIN]),
        (["DO1", "moving", "Yellow Pilot Light", "24V / 0.5A SSR", "Blinks during carriage X/Y movement"], [C_DIR, TXT_MAIN, C_DIR, TXT_MAIN, TXT_MAIN]),
        (["DO2", "alarm", "Red Light + Audible Buzzer", "24V / 0.5A SSR", "Active during drive fault, E-Stop or stall"], [C_ALM, TXT_MAIN, C_ALM, TXT_MAIN, C_ALM]),
        (["DO3", "dispense", "Solenoid Drop Gate Relay", "24V Interposing", "500ms pulse triggers pickup door latch"], [C_ETH, TXT_MAIN, C_ETH, TXT_MAIN, TXT_MAIN]),
    ]
    y_r = 96.4
    for rdata, rcols in do_table:
        draw_table_row(ax, 171, y_r, widths_do, rdata, rcols, bg='#F0FDF4' if 'ready' in rdata[1] else BG_WHITE)
        y_r -= 3.6

    # Wiring Notes
    ax.add_patch(patches.Rectangle((171, 20), 136, 56, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(174, 71.0, "IRIV IO SENSOR TERMINATION & NOISE REJECTION RULES:", fontsize=7.8, fontweight='bold', color=HDR_AMBER)
    ax.text(174, 66.0, "• S/S Jumper Rule : The S/S terminal MUST be tied to 0V for PNP sensors (Sinking input circuit).", fontsize=7.0, color=TXT_MAIN)
    ax.text(174, 61.5, "• Fail-Safe NC Limit Inputs : Limit sensors DI0-DI5 use NC logic. Wire break stops motion immediately.", fontsize=7.0, color=C_ALM, fontweight='bold')
    ax.text(174, 57.0, "• Cable Shielding : All sensor cables must use shielded pairs; shield tied to PE ground bar at cabinet.", fontsize=7.0, color=TXT_MAIN)
    ax.text(174, 52.5, "• Debounce Filters : Hardware optocouplers + 3-sample software digital filter suppresses contact bounce.", fontsize=7.0, color=TXT_MAIN)
    ax.text(174, 48.0, "• Inductive Load Protection : DO3 solenoid coil requires flyback diode (1N4007) across terminals.", fontsize=7.0, color=C_24V)
    ax.text(174, 43.5, "• Stale Guard Policy : Software watchdog resets all DOs to OFF if Modbus link is interrupted > 350ms.", fontsize=7.0, color=BORDER_NAVY)
    ax.text(174, 38.0, "• Modbus Addressing : Unit ID = 255 | Discrete Inputs: 10001-10011 | Coils: 00001-00004.", fontsize=7.0, color=TXT_MUTED)

    return fig

# =============================================================================
# PAGE 4: SECTION 3 — SENSOR SYSTEM PINOUT & WIRING (Optical & Limits)
# =============================================================================
def generate_page_4_sensors():
    fig, ax = create_page("Section 3: Field Sensor System Wiring & Pinout", 
                          "2 x Optical Verification Sensors & 6 x Inductive Proximity Limit Sensors", "Section 3")

    # Left Half: Optical Sensors (Completed & Alarm/Pickup) (x: 10 to 155)
    draw_card(ax, 10, 15, 145, 160, "OPTICAL PHOTOELECTRIC SENSORS (OMRON E3Z-D81)", 
              "Product Drop Verification & Door Access Safety Sensors (24VDC Infrared)", header_color=HDR_AMBER)

    # Completed Sensor Box
    ax.add_patch(patches.Rectangle((16, 114), 133, 56, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1.0))
    ax.text(82, 164.0, "1. COMPLETED SENSOR x 1 (OMRON E3Z-D81 / E3Z-R81)", fontsize=9.2, fontweight='bold', color=HDR_AMBER, ha='center')
    ax.text(82, 158.0, "Mounting: Dispense Chute Beam | Function: Confirms product drop onto tray", fontsize=7.5, color=TXT_MUTED, ha='center')

    widths_s1 = [24, 28, 28, 48]
    draw_table_header(ax, 20, 148.0, widths_s1, ["WIRE COLOR", "TERMINAL PIN", "VOLTAGE / SIGNAL", "CONNECTION AT IRIV IO"])
    s1_rows = [
        (["BROWN (BN)", "Pin 1 (Power +)", "+24VDC Supply", "From PSU 2 (+24VDC Rail)"], [C_24V, TXT_MAIN, C_24V, TXT_MAIN]),
        (["BLUE (BU)", "Pin 3 (Power -)", "0VDC Return", "From PSU 2 (0VDC Common Rail)"], [C_0V, TXT_MAIN, C_0V, TXT_MAIN]),
        (["BLACK (BK)", "Pin 4 (Output)", "PNP Open Collector", "To IRiV IO Terminal DI8 (Drop Sensor)"], [C_ALM, TXT_MAIN, C_ALM, C_ALM]),
        (["WHITE (WH)", "Pin 2 (Mode)", "Dark-ON / Light-ON", "Tied to Brown for Dark-ON mode"], [TXT_MUTED, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
    ]
    y_r = 144.4
    for rdata, rcols in s1_rows:
        draw_table_row(ax, 20, y_r, widths_s1, rdata, rcols, bg='#FFF7ED' if 'BROWN' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # Alarm / Pickup Door Sensor Box
    ax.add_patch(patches.Rectangle((16, 52), 133, 56, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1.0))
    ax.text(82, 102.0, "2. ALARM / PICKUP SENSOR x 1 (OMRON E3Z-D81)", fontsize=9.2, fontweight='bold', color=HDR_AMBER, ha='center')
    ax.text(82, 96.0, "Mounting: Pickup Flap Door | Function: Detects door open / hand access", fontsize=7.5, color=TXT_MUTED, ha='center')

    widths_s2 = [24, 28, 28, 48]
    draw_table_header(ax, 20, 86.0, widths_s2, ["WIRE COLOR", "TERMINAL PIN", "VOLTAGE / SIGNAL", "CONNECTION AT IRIV IO"])
    s2_rows = [
        (["BROWN (BN)", "Pin 1 (Power +)", "+24VDC Supply", "From PSU 2 (+24VDC Rail)"], [C_24V, TXT_MAIN, C_24V, TXT_MAIN]),
        (["BLUE (BU)", "Pin 3 (Power -)", "0VDC Return", "From PSU 2 (0VDC Common Rail)"], [C_0V, TXT_MAIN, C_0V, TXT_MAIN]),
        (["BLACK (BK)", "Pin 4 (Output)", "PNP Open Collector", "To IRiV IO Terminal DI9 (Pickup Sensor)"], [C_ALM, TXT_MAIN, C_ALM, C_ALM]),
        (["WHITE (WH)", "Pin 2 (Mode)", "Dark-ON / Light-ON", "Tied to Brown for Dark-ON mode"], [TXT_MUTED, TXT_MAIN, TXT_MAIN, TXT_MUTED]),
    ]
    y_r = 82.4
    for rdata, rcols in s2_rows:
        draw_table_row(ax, 20, y_r, widths_s2, rdata, rcols, bg='#FFF7ED' if 'BROWN' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # Sensor Adjustments Box
    ax.add_patch(patches.Rectangle((16, 20), 133, 28, facecolor='#F8FAFC', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(82, 43.0, "OPTICAL SENSOR CALIBRATION PROCEDURE:", fontsize=7.8, fontweight='bold', color=BORDER_NAVY, ha='center')
    ax.text(82, 38.0, "1. Sensitivity Trimmer: Turn clockwise until yellow output LED lights with target present.", fontsize=7.0, color=TXT_MAIN, ha='center')
    ax.text(82, 33.5, "2. Beam Alignment: Verify infrared beam reflects reliably across full width of dispense chute.", fontsize=7.0, color=TXT_MAIN, ha='center')
    ax.text(82, 29.0, "3. Interlock: Carriage motion is locked in HOLD while DI9 (Pickup Door) is asserted.", fontsize=7.0, color=C_ALM, fontweight='bold', ha='center')

    # Right Half: 6 x Proximity Limit Sensors (x: 165 to 310)
    draw_card(ax, 165, 15, 145, 160, "INDUCTIVE PROXIMITY LIMIT SENSORS (AXES X, Y, Z)", 
              "6 x Inductive Proximity Sensors (24VDC PNP Normally Closed)", header_color=HDR_NAVY)

    ax.text(168, 167.0, "PROXIMITY LIMIT SENSOR PINOUT & SCHEDULE (DI0 - DI5):", fontsize=8.5, fontweight='bold', color=BORDER_NAVY)

    widths_lim = [22, 28, 30, 24, 37]
    draw_table_header(ax, 168, 157.0, widths_lim, ["AXIS / LIMIT", "SENSOR MODEL", "IRIV IO PIN", "NORMAL / ACTIVE", "MECHANICAL FUNCTION"])

    prox_rows = [
        (["LIMIT MIN X", "LJ12A3-4-Z/AX (PNP)", "DI0 (Channel 0)", "Closed (NC) -> High", "X-Axis Min / Home Limit (Left)"], [C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MAIN]),
        (["LIMIT MAX X", "LJ12A3-4-Z/AX (PNP)", "DI1 (Channel 1)", "Closed (NC) -> High", "X-Axis Max Overtravel (Right)"], [C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MAIN]),
        (["LIMIT MIN Y", "LJ12A3-4-Z/AX (PNP)", "DI2 (Channel 2)", "Closed (NC) -> High", "Y-Axis Bottom Limit (Drop Chute)"], [C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MAIN]),
        (["LIMIT MAX Y", "LJ12A3-4-Z/AX (PNP)", "DI3 (Channel 3)", "Closed (NC) -> High", "Y-Axis Top Overtravel (Level 5)"], [C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MAIN]),
        (["LIMIT MIN Z", "LJ12A3-4-Z/AX (PNP)", "DI4 (Channel 4)", "Closed (NC) -> High", "Z-Axis Retract Home (Pusher Back)"], [C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MAIN]),
        (["LIMIT MAX Z", "LJ12A3-4-Z/AX (PNP)", "DI5 (Channel 5)", "Closed (NC) -> High", "Z-Axis Extend Max (Pusher Forward)"], [C_SIG, TXT_MAIN, C_SIG, TXT_MAIN, TXT_MAIN]),
        (["Z HOME REF", "LJ12A3-4-Z/BX (PNP)", "DI6 (Channel 6)", "Open (NO) -> High", "Z Secondary Home Datum Sensor"], [C_SIG, TXT_MAIN, C_SIG, TXT_MUTED, TXT_MUTED]),
        (["PARKING SENS", "LJ12A3-4-Z/BX (PNP)", "DI7 (Channel 7)", "Open (NO) -> High", "Carriage Drop Alignment Sensor"], [C_SIG, TXT_MAIN, C_SIG, TXT_MUTED, TXT_MUTED]),
    ]
    y_r = 153.4
    for rdata, rcols in prox_rows:
        draw_table_row(ax, 168, y_r, widths_lim, rdata, rcols, bg='#EFF6FF' if 'LIMIT' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # 3-Wire Color Code Diagram for Proximity Sensors
    ax.add_patch(patches.Rectangle((168, 62), 139, 58, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=1.0))
    ax.text(237, 114.0, "STANDARD 3-WIRE INDUCTIVE PROXIMITY WIRING (PNP NC):", fontsize=8.2, fontweight='bold', color=BORDER_NAVY, ha='center')

    # Color definitions table
    widths_col = [24, 28, 32, 51]
    draw_table_header(ax, 172, 104.0, widths_col, ["WIRE COLOR", "CORE FUNCTION", "SUPPLY RAIL", "TERMINATION POINT"])
    col_rows = [
        (["BROWN (BN)", "DC Positive V+", "+24VDC Power Bus", "PSU 2 (+24VDC Terminal Bus)"], [C_24V, TXT_MAIN, C_24V, TXT_MAIN]),
        (["BLUE (BU)", "DC Common V-", "0VDC Power Return", "PSU 2 (0VDC Common Bus)"], [C_0V, TXT_MAIN, C_0V, TXT_MAIN]),
        (["BLACK (BK)", "Signal Output", "PNP Switching Load", "IRiV IO DI0 to DI7 Terminals"], [C_SIG, TXT_MAIN, C_SIG, C_SIG]),
        (["SHIELD (DRAIN)", "Noise Screen", "Earth Ground (PE)", "Cabinet PE Ground Bar (One end only)"], [C_PE, TXT_MAIN, C_PE, C_PE]),
    ]
    y_r = 100.4
    for rdata, rcols in col_rows:
        draw_table_row(ax, 172, y_r, widths_col, rdata, rcols, bg='#FFF7ED' if 'BROWN' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    ax.text(237, 78.0, "S/S Terminal on IRiV IO MUST be jumpered to 0V for PNP sensor operation.", fontsize=7.5, color=C_24V, fontweight='bold', ha='center')
    ax.text(237, 72.0, "Sensing Distance: 4.0 mm for ferrous targets (Steel bracket).", fontsize=7.0, color=TXT_MUTED, ha='center')

    # Fail-Safe NC Logic Explanation Card
    ax.add_patch(patches.Rectangle((168, 20), 139, 38, facecolor='#FEF2F2', edgecolor=C_ALM, linewidth=1.0))
    ax.text(237, 52.0, "FAIL-SAFE NORMALLY CLOSED (NC) SAFETY PHILOSOPHY:", fontsize=8.0, fontweight='bold', color=C_ALM, ha='center')
    ax.text(237, 47.0, "• Under normal operation, proximity sensors maintain closed circuit (+24V asserted at DIx).", fontsize=7.0, color=TXT_MAIN, ha='center')
    ax.text(237, 42.5, "• When carriage reaches mechanical limit, metal flag separates and signal drops to 0V.", fontsize=7.0, color=TXT_MAIN, ha='center')
    ax.text(237, 38.0, "• CRITICAL: If a wire breaks or comes loose, signal instantly drops to 0V (Triggers E-Stop).", fontsize=7.0, color=C_ALM, fontweight='bold', ha='center')
    ax.text(237, 33.5, "• Prevents machine run-away that would occur with Normally Open (NO) sensors.", fontsize=7.0, color=TXT_MUTED, ha='center')
    ax.text(237, 28.0, "• DI10 (KM1 Aux Feedback) uses identical active-LOW fail-safe loop logic.", fontsize=7.0, color=BORDER_NAVY, ha='center')

    return fig

# =============================================================================
# PAGE 5: SECTION 4 — STEPPER DRIVERS & MOTORS PINOUT (Axes X, Y, Z + STM32)
# =============================================================================
def generate_page_5_motors():
    fig, ax = create_page("Section 4: Stepper Motor Drivers & Actuators Pinout", 
                          "Leadshine HBS860H, DM542, NEMA 34/17 Steppers & STM32 Pulse Interface", "Section 4")

    # Column 1: Driver X & Y (Leadshine HBS860H) (x: 10 to 110)
    draw_card(ax, 10, 15, 100, 160, "DRIVERS X & Y: LEADSHINE HBS860H", 
              "Hybrid Closed-Loop Drives for X & Y Axes (Peak 8.2A, +60VDC)", header_color=HDR_SLATE)

    widths_drv = [24, 28, 44]
    draw_table_header(ax, 14, 157.0, widths_drv, ["TERMINAL", "SIGNAL NAME", "CONNECTION & ELECTRICAL SPEC"])
    drv_rows = [
        (["AC / AC", "+60VDC / 0VDC", "+60V Power Bus from KM1 Contactor Out"], [C_60V, C_60V, C_60V]),
        (["PUL+ (V-PULSE)", "+24VDC Common", "+24VDC Common Anode Bus (PSU 2)"], [C_24V, C_24V, C_24V]),
        (["PUL- (STEP)", "Step Pulse In", "From NMOS Ch1 (X) / Ch3 (Y) Drain"], [C_STEP, C_STEP, C_STEP]),
        (["DIR+ (V-PULSE)", "+24VDC Common", "+24VDC Common Anode Bus (PSU 2)"], [C_24V, C_24V, C_24V]),
        (["DIR- (DIR)", "Direction In", "From NMOS Ch2 (X) / Ch4 (Y) Drain"], [C_DIR, C_DIR, C_DIR]),
        (["ENA+ / ENA-", "Enable Input", "Not connected (Driver defaults enabled)"], [TXT_MUTED, TXT_MUTED, TXT_MUTED]),
        (["ALM+ / ALM-", "Alarm Output", "Optocoupler to PiControl DI0 (X) / DI1 (Y)"], [C_ALM, C_ALM, C_ALM]),
        (["PEND+ / PEND-", "In-Position Out", "Optocoupler to PiControl DI2 (X) / DI3 (Y)"], [C_DIR, C_DIR, C_DIR]),
        (["A+ / A-", "Phase A Coils", "To 86HBS85 Motor Phase A (Red / Blue)"], [TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["B+ / B-", "Phase B Coils", "To 86HBS85 Motor Phase B (Black / Green)"], [TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["EA+ / EA-", "Encoder Ch A", "Differential Optical Encoder Channel A"], [C_ETH, C_ETH, C_ETH]),
        (["EB+ / EB-", "Encoder Ch B", "Differential Optical Encoder Channel B"], [C_ETH, C_ETH, C_ETH]),
        (["VCC / EGND", "Encoder +5V/0V", "+5VDC Power to Encoder (Red / White)"], [C_5V, C_5V, C_5V]),
    ]
    y_r = 153.4
    for rdata, rcols in drv_rows:
        draw_table_row(ax, 14, y_r, widths_drv, rdata, rcols, bg='#FEF2F2' if 'AC' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # DIP Switch Settings Table HBS860H
    ax.text(14, 98.0, "DIP SWITCH SETTINGS (HBS860H):", fontsize=8.0, fontweight='bold', color=BORDER_NAVY)
    ax.add_patch(patches.Rectangle((14, 76), 92, 20, facecolor='#F8FAFC', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(17, 92.0, "• Current (SW1 - SW4): ON, ON, ON, ON -> Peak 8.2A (5.6A RMS)", fontsize=7.2, color=TXT_MAIN)
    ax.text(17, 87.0, "• Microstep (SW5 - SW8): ON, OFF, ON, ON -> 1600 pulses/revolution", fontsize=7.2, color=C_STEP, fontweight='bold')
    ax.text(17, 82.0, "• Direction (SW9): OFF -> Normal rotation | SW10: OFF -> Closed loop active", fontsize=7.0, color=TXT_MUTED)

    # Motor Specifications Card
    ax.add_patch(patches.Rectangle((14, 20), 92, 52, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(17, 67.0, "MOTOR SPECIFICATIONS (AXES X & Y):", fontsize=7.8, fontweight='bold', color=HDR_TEAL)
    ax.text(17, 62.0, "• Model: 86HBS85 Hybrid Closed-Loop Stepper (NEMA 34)", fontsize=7.0, color=TXT_MAIN)
    ax.text(17, 57.5, "• Holding Torque: 8.5 N.m | Rated Current: 5.6A / phase", fontsize=7.0, color=TXT_MAIN)
    ax.text(17, 53.0, "• Encoder: 1000 CPR Optical Quadrature (4000 counts/rev)", fontsize=7.0, color=C_ETH)
    ax.text(17, 48.5, "• Axis X Transmission: HTD 5M 25mm Belt -> 78.43 steps/mm", fontsize=7.0, color=BORDER_NAVY, fontweight='bold')
    ax.text(17, 44.0, "• Axis Y Transmission: SFU1605 Ball Screw -> 320.00 steps/mm", fontsize=7.0, color=BORDER_NAVY, fontweight='bold')
    ax.text(17, 39.5, "• Max Speed X: 450 mm/s | Accel X: 800 mm/s² (Dual HGR20)", fontsize=7.0, color=TXT_MUTED)
    ax.text(17, 35.0, "• Max Speed Y: 120 mm/s | Accel Y: 600 mm/s² (Elevator Lift)", fontsize=7.0, color=TXT_MUTED)
    ax.text(17, 28.0, "• Stall Protection: Drive trips ALM if encoder lags > 1000 pulses.", fontsize=7.0, color=C_ALM)

    # Column 2: Driver Z (Leadshine DM542) (x: 115 to 215)
    draw_card(ax, 115, 15, 100, 160, "DRIVER Z: LEADSHINE DM542", 
              "Digital Microstepping Drive for Pusher Axis (Peak 4.2A, +24VDC)", header_color=HDR_SLATE)

    widths_dm = [24, 28, 44]
    draw_table_header(ax, 119, 157.0, widths_dm, ["TERMINAL", "SIGNAL NAME", "CONNECTION & ELECTRICAL SPEC"])
    dm_rows = [
        (["V+ / GND", "+24VDC / 0VDC", "+24VDC Control Supply from PSU 2 Rail"], [C_24V, C_24V, C_24V]),
        (["PUL+ (V-PULSE)", "+24VDC Common", "+24VDC Common Anode Bus (PSU 2)"], [C_24V, C_24V, C_24V]),
        (["PUL- (STEP)", "Step Pulse In", "From NMOS Ch5 (PA5 / D13) Drain"], [C_STEP, C_STEP, C_STEP]),
        (["DIR+ (V-PULSE)", "+24VDC Common", "+24VDC Common Anode Bus (PSU 2)"], [C_24V, C_24V, C_24V]),
        (["DIR- (DIR)", "Direction In", "From NMOS Ch6 (PB2) Drain"], [C_DIR, C_DIR, C_DIR]),
        (["ENA+ / ENA-", "Enable Input", "Not connected (Driver defaults enabled)"], [TXT_MUTED, TXT_MUTED, TXT_MUTED]),
        (["A+ / A-", "Phase A Coils", "To NEMA 17 Pusher Phase A (Red / Blue)"], [TXT_MAIN, TXT_MAIN, TXT_MAIN]),
        (["B+ / B-", "Phase B Coils", "To NEMA 17 Pusher Phase B (Black / Green)"], [TXT_MAIN, TXT_MAIN, TXT_MAIN]),
    ]
    y_r = 153.4
    for rdata, rcols in dm_rows:
        draw_table_row(ax, 119, y_r, widths_dm, rdata, rcols, bg='#FFF7ED' if 'V+' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # DIP Switch Settings Table DM542
    ax.text(119, 118.0, "DIP SWITCH SETTINGS (DM542):", fontsize=8.0, fontweight='bold', color=BORDER_NAVY)
    ax.add_patch(patches.Rectangle((119, 96), 92, 20, facecolor='#F8FAFC', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(122, 112.0, "• Current (SW1 - SW3): ON, OFF, ON -> Peak 2.0A (1.4A RMS)", fontsize=7.2, color=TXT_MAIN)
    ax.text(122, 107.0, "• Standstill (SW4): OFF -> Half current during standstill (idle)", fontsize=7.0, color=TXT_MUTED)
    ax.text(122, 102.0, "• Microstep (SW5 - SW8): ON, OFF, ON, ON -> 1600 pulse/rev", fontsize=7.2, color=C_STEP, fontweight='bold')

    # Motor Z Specifications Card
    ax.add_patch(patches.Rectangle((119, 20), 92, 72, facecolor='#FFFFFF', edgecolor=BORDER_SLATE, linewidth=0.8))
    ax.text(122, 87.0, "MOTOR & ACTUATOR SPECIFICATIONS (AXIS Z):", fontsize=7.8, fontweight='bold', color=HDR_TEAL)
    ax.text(122, 82.0, "• Model: NEMA 17 Stepper (42x42mm, 1.5A / phase)", fontsize=7.0, color=TXT_MAIN)
    ax.text(122, 77.5, "• Actuator: V-Slot Mini Lead Screw Linear Actuator", fontsize=7.0, color=TXT_MAIN)
    ax.text(122, 73.0, "• Lead Screw: T8x8 (Pitch 2mm, 4 Starts = Lead 8.0mm/rev)", fontsize=7.0, color=BORDER_NAVY)
    ax.text(122, 68.5, "• Stroke Length: 150mm Pusher Rod Travel", fontsize=7.0, color=TXT_MAIN)
    ax.text(122, 64.0, "• Kinematic Ratio: 200.00 steps/mm @ 1600 microstep", fontsize=7.0, color=BORDER_NAVY, fontweight='bold')
    ax.text(122, 59.5, "• Push Speed: 50 mm/s | Retract Speed: 80 mm/s", fontsize=7.0, color=TXT_MUTED)
    ax.text(122, 53.0, "SAFETY INTERLOCK GATES (AXIS Z):", fontsize=7.2, fontweight='bold', color=HDR_RED)
    ax.text(122, 48.5, "1. Carriage X/Y motion is locked unless DI4 (Z_MIN) is asserted.", fontsize=6.8, color=C_ALM)
    ax.text(122, 44.0, "2. Push cycle extends to DI5 (Z_MAX), pauses 500ms, retracts.", fontsize=6.8, color=TXT_MAIN)
    ax.text(122, 39.5, "3. Soft-limit timeout: Auto-reverses if stroke exceeds 3.5s.", fontsize=6.8, color=TXT_MUTED)
    ax.text(122, 33.0, "4. Safety Gap: 24V supply recommended to route via KM1 contactor.", fontsize=6.8, color=HDR_RED, fontweight='bold')

    # Column 3: STM32 NUCLEO-G491RE & 6-Ch NMOS Level Shifter (x: 220 to 310)
    draw_card(ax, 220, 15, 90, 160, "STM32 & 6-CH NMOS PULSE INTERFACE", 
              "Hardware Timer Output Compare Pulse Engine + Low-Side Sink Board", header_color=HDR_NAVY)

    # Timer pin mapping table
    ax.text(223, 167.0, "STM32 NUCLEO-G491RE PIN MAPPING:", fontsize=8.0, fontweight='bold', color=BORDER_NAVY)
    widths_stm = [18, 22, 24, 24]
    draw_table_header(ax, 223, 157.0, widths_stm, ["SIGNAL", "PIN", "TIMER / AF", "CONNECTOR"])
    stm_rows = [
        (["X_STEP", "PA8", "TIM1_CH1 / AF6", "CN10 pin 23 (D7)"], [C_STEP, TXT_MAIN, TXT_MAIN, C_STEP]),
        (["X_DIR", "PB0", "GPIO Output", "CN7 pin 34 (A3)"], [C_DIR, TXT_MAIN, TXT_MAIN, C_DIR]),
        (["Y_STEP", "PA9", "TIM1_CH2 / AF6", "CN10 pin 21 (D8)"], [C_STEP, TXT_MAIN, TXT_MAIN, C_STEP]),
        (["Y_DIR", "PB1", "GPIO Output", "CN10 pin 24"], [C_DIR, TXT_MAIN, TXT_MAIN, C_DIR]),
        (["Z_STEP", "PA5", "TIM2_CH1 / AF1", "CN10 pin 11 (D13)"], [C_STEP, TXT_MAIN, TXT_MAIN, C_STEP]),
        (["Z_DIR", "PB2", "GPIO Output", "CN10 pin 22"], [C_DIR, TXT_MAIN, TXT_MAIN, C_DIR]),
        (["GND", "GND", "Digital Ground", "CN10 pin 20 / 9"], [C_0V, TXT_MAIN, TXT_MAIN, C_0V]),
    ]
    y_r = 153.4
    for rdata, rcols in stm_rows:
        draw_table_row(ax, 223, y_r, widths_stm, rdata, rcols)
        y_r -= 3.6

    # 6-Ch NMOS Level Shifter Table
    ax.text(223, 122.0, "6-CH NMOS LEVEL SHIFTER SINK BOARD:", fontsize=8.0, fontweight='bold', color=HDR_SLATE)
    widths_nmos = [18, 28, 42]
    draw_table_header(ax, 223, 112.0, widths_nmos, ["CH", "GATE INPUT", "DRAIN SINK OUTPUT"])
    nmos_rows = [
        (["CH 1", "STM32 PA8 (X_STEP)", "Sinks Driver X PUL-"], [C_STEP, TXT_MAIN, C_STEP]),
        (["CH 2", "STM32 PB0 (X_DIR)", "Sinks Driver X DIR-"], [C_DIR, TXT_MAIN, C_DIR]),
        (["CH 3", "STM32 PA9 (Y_STEP)", "Sinks Driver Y PUL-"], [C_STEP, TXT_MAIN, C_STEP]),
        (["CH 4", "STM32 PB1 (Y_DIR)", "Sinks Driver Y DIR-"], [C_DIR, TXT_MAIN, C_DIR]),
        (["CH 5", "STM32 PA5 (Z_STEP)", "Sinks Driver Z PUL-"], [C_STEP, TXT_MAIN, C_STEP]),
        (["CH 6", "STM32 PB2 (Z_DIR)", "Sinks Driver Z DIR-"], [C_DIR, TXT_MAIN, C_DIR]),
        (["ANODE", "+24VDC (V-PULSE)", "Feeds all PUL+ & DIR+"], [C_24V, C_24V, C_24V]),
        (["SOURCE", "MCU GND + DC 0V", "Common Return Reference"], [C_0V, C_0V, C_0V]),
    ]
    y_r = 108.4
    for rdata, rcols in nmos_rows:
        draw_table_row(ax, 223, y_r, widths_nmos, rdata, rcols, bg='#FFF7ED' if 'ANODE' in rdata[0] else BG_WHITE)
        y_r -= 3.6

    # Critical Pin Warning Box
    ax.add_patch(patches.Rectangle((223, 20), 84, 52, facecolor='#FEF2F2', edgecolor=C_ALM, linewidth=1.0))
    ax.text(265, 67.0, "CRITICAL HARDWARE WIRING WARNINGS:", fontsize=7.5, fontweight='bold', color=C_ALM, ha='center')
    ax.text(225, 62.0, "1. DO NOT plug PB0 into CN10-31! (On Nucleo-64 that is PB3). Connect to CN7 pin 34.", fontsize=6.5, color=TXT_MAIN)
    ax.text(225, 56.5, "2. DO NOT plug PB1 into CN10-7! (That is AVDD 3.3V). Connect to CN10 pin 24.", fontsize=6.5, color=C_ALM, fontweight='bold')
    ax.text(225, 51.0, "3. DO NOT plug PB2 into CN10-15! (That is PA7). Connect to CN10 pin 22.", fontsize=6.5, color=TXT_MAIN)
    ax.text(225, 45.5, "4. DO NOT connect GND to CN10-5, 17, 27! Use CN10 pin 20 or CN10 pin 9 only.", fontsize=6.5, color=C_ALM, fontweight='bold')
    ax.text(225, 40.0, "5. PA5 shares onboard LD2 LED: Firmware MUST disable all LED blink functions.", fontsize=6.5, color=TXT_MAIN)
    ax.text(225, 34.5, "6. Resistors: Rg = 100 Ohm (damping), Rpd = 10k Ohm (tri-state pulldown).", fontsize=6.5, color=BORDER_NAVY)
    ax.text(225, 27.0, "Failure to observe these pin rules will lock direction or damage MCU pins.", fontsize=6.5, color=C_ALM, fontweight='bold')

    return fig

# =============================================================================
# MAIN EXPORT ROUTINE
# =============================================================================
def generate_all_booklet():
    base_dir = r"D:\37-Project Narit Vending Machine\Document\NaritVending"
    doc_dir  = r"D:\37-Project Narit Vending Machine\Document"
    sec_dir  = os.path.join(base_dir, "docs", "schematic_sections")
    doc_sec  = os.path.join(doc_dir, "schematic_sections")

    os.makedirs(sec_dir, exist_ok=True)
    os.makedirs(doc_sec, exist_ok=True)

    pdf_base = os.path.join(base_dir, "narit_vending_schematic_and_pinout_booklet.pdf")
    pdf_docs = os.path.join(base_dir, "docs", "narit_vending_schematic_and_pinout_booklet.pdf")
    pdf_main = os.path.join(doc_dir, "narit_vending_schematic_and_pinout_booklet.pdf")

    poster_base = os.path.join(base_dir, "narit_vending_system_block_and_pinout.png")
    poster_docs = os.path.join(base_dir, "docs", "narit_vending_system_block_and_pinout.png")
    poster_main = os.path.join(doc_dir, "narit_vending_system_block_and_pinout.png")

    pages = [
        ("page1_system_block_diagram", generate_page_1_block_diagram),
        ("page2_ac_mains_and_power_supplies", generate_page_2_power),
        ("page3_controllers_and_communication", generate_page_3_controllers),
        ("page4_sensor_system_and_limits", generate_page_4_sensors),
        ("page5_stepper_drivers_and_motors", generate_page_5_motors),
    ]

    print("Rendering Multi-Page Schematic & Pinout Booklet (5 Pages)...")
    with PdfPages(pdf_base) as pdf:
        for idx, (name, gen_fn) in enumerate(pages):
            print(f"  Rendering Page {idx+1}: {name}...")
            fig = gen_fn()
            
            # Save into PDF
            pdf.savefig(fig, bbox_inches='tight', facecolor=BG_WHITE)

            # Save individual page PNGs
            png_base = os.path.join(sec_dir, f"{name}.png")
            png_doc  = os.path.join(doc_sec, f"{name}.png")
            fig.savefig(png_base, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)
            fig.savefig(png_doc, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)

            # If page 1, also save as standalone poster PNG
            if idx == 0:
                fig.savefig(poster_base, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)
                fig.savefig(poster_docs, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)
                fig.savefig(poster_main, dpi=150, bbox_inches='tight', facecolor=BG_WHITE)

            plt.close(fig)

    # Sync PDF across directories
    shutil.copyfile(pdf_base, pdf_docs)
    shutil.copyfile(pdf_base, pdf_main)

    print("Complete Schematic & Pinout Booklet Generated Successfully!")
    print(f"  -> Booklet PDF: {pdf_main}")
    print(f"  -> Poster PNG:  {poster_main}")
    print(f"  -> Sheets Dir:  {doc_sec}")

if __name__ == "__main__":
    generate_all_booklet()
