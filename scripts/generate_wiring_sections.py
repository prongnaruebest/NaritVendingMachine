# -*- coding: utf-8 -*-
"""
NARIT Vending Machine — Multi-Section Detailed Electrical Schematic Package
Generates a formal 6-sheet engineering drawing booklet:
- Sheet 1: System Overview & Cable Interconnection Architecture
- Sheet 2: Section 1 — AC Mains Distribution & DC Power Supplies
- Sheet 3: Section 2 — Main Controller (Cytron IRiV PiControl CM4)
- Sheet 4: Section 3 — Remote Field I/O (Cytron IRiV IO) & Sensor Interfacing
- Sheet 5: Section 4 — Motion Co-Processor (STM32 NUCLEO-G491RE) & NMOS Level Shifter
- Sheet 6: Section 5 — Stepper Motor Drivers & Actuators Wiring (Axes X, Y, Z)

Compliant with ISO 7200 / IEC 60617 / IEC 60204-1 Drawing Standards.
Outputs both a consolidated Multi-Page PDF and standalone high-resolution PNG sheets.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import os

# Set font family
plt.rcParams['font.sans-serif'] = ['Leelawadee UI', 'Tahoma', 'Segoe UI', 'DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# Palette constants
BG_CANVAS    = '#FFFFFF'
BORDER_MAIN  = '#0F2744'   # Deep Technical Navy
BORDER_SUB   = '#64748B'   # Technical Gray
GRID_TEXT    = '#64748B'

MOD_HDR_NAVY = '#0F2744'
MOD_HDR_SLATE= '#1E293B'
MOD_HDR_TEAL = '#064E3B'
MOD_HDR_AMBER= '#78350F'
MOD_HDR_RED  = '#7F1D1D'

TERM_BG_EVEN = '#F8FAFC'
TERM_BG_ODD  = '#FFFFFF'
TERM_BORDER  = '#94A3B8'
TEXT_MAIN    = '#0F172A'
TEXT_MUTED   = '#475569'

W_AC_L   = '#991B1B'
W_AC_N   = '#1D4ED8'
W_PE     = '#15803D'
W_60V    = '#7F1D1D'
W_24V    = '#C2410C'
W_GND    = '#1E293B'
W_5V     = '#6B21A8'
W_STEP   = '#0284C7'
W_DIR    = '#B45309'
W_SIG    = '#0F766E'
W_ALM    = '#DC2626'
W_ETH    = '#1E3A8A'
W_USB    = '#4338CA'

def create_base_canvas(sheet_num, total_sheets, sheet_title, section_name):
    fig = plt.figure(figsize=(28, 18), dpi=150)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 280)
    ax.set_ylim(0, 180)
    ax.axis('off')

    # Sheet borders
    ax.add_patch(patches.Rectangle((0, 0), 280, 180, facecolor=BG_CANVAS, edgecolor=BORDER_MAIN, linewidth=3))
    ax.add_patch(patches.Rectangle((3, 3), 274, 174, facecolor='none', edgecolor=BORDER_MAIN, linewidth=1.5))
    ax.add_patch(patches.Rectangle((4.5, 4.5), 271, 171, facecolor='none', edgecolor=BORDER_SUB, linewidth=0.75))

    # Grid references around border
    cols = ['1', '2', '3', '4', '5', '6', '7', '8']
    for i, c in enumerate(cols):
        gx = 4.5 + (271 / 8) * (i + 0.5)
        ax.text(gx, 3.8, c, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')
        ax.text(gx, 175.2, c, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')
    
    rows = ['F', 'E', 'D', 'C', 'B', 'A']
    for i, r in enumerate(rows):
        gy = 4.5 + (171 / 6) * (i + 0.5)
        ax.text(3.8, gy, r, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')
        ax.text(276.2, gy, r, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')

    # Header Title Block
    ax.add_patch(patches.Rectangle((5.5, 163), 269, 11, facecolor=BORDER_MAIN, edgecolor='none'))
    ax.text(9, 169.5, "สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน) — NATIONAL ASTRONOMICAL RESEARCH INSTITUTE OF THAILAND", 
            color='#94A3B8', fontsize=7.8, fontweight='bold', va='center')
    ax.text(9, 165.8, f"PROJECT: NARIT SMART VENDING MACHINE  |  {sheet_title.upper()}", 
            color='white', fontsize=11.5, fontweight='bold', va='center')

    ax.text(272, 169.5, f"DWG NO: NARIT-VEND-E02  |  SHEET {sheet_num} OF {total_sheets}  |  REV: 2.4", 
            color='#38BDF8', fontsize=8.5, fontweight='bold', ha='right', va='center')
    ax.text(272, 165.8, f"SECTION: {section_name.upper()}  |  TOR: 00-TOR-Vending-J69-290", 
            color='#E2E8F0', fontsize=7.8, ha='right', va='center')

    return fig, ax

def draw_module(ax, x, y, w, h, title, subtitle="", header_color=MOD_HDR_SLATE, bg=BG_CANVAS, border=BORDER_SUB):
    ax.add_patch(patches.Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=1.1))
    hdr_h = 3.6
    ax.add_patch(patches.Rectangle((x, y + h - hdr_h), w, hdr_h, facecolor=header_color, edgecolor=border, linewidth=0.9))
    ax.text(x + w/2, y + h - 1.6, title, color='white', fontsize=8.8, fontweight='bold', ha='center', va='center')
    if subtitle:
        ax.text(x + w/2, y + h - 2.8, subtitle, color='#CBD5E1', fontsize=6.5, ha='center', va='center')

def draw_term(ax, x, y, text, subtext="", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=22, height=2.2, text_size=7.0):
    ax.add_patch(patches.Rectangle((x, y), width, height, facecolor=bg, edgecolor=TERM_BORDER, linewidth=0.6))
    ax.text(x + 0.8, y + height/2, text, color=color, fontsize=text_size, fontweight='bold', va='center')
    if subtext:
        ax.text(x + width - 0.8, y + height/2, subtext, color=TEXT_MUTED, fontsize=text_size*0.85, ha='right', va='center')

def draw_wire(ax, pts, color, style='-', lw=1.4):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, linestyle=style, linewidth=lw, solid_capstyle='round')

def draw_dot(ax, x, y, color):
    ax.plot(x, y, marker='o', markersize=4.2, color=color, zorder=6)

# =============================================================================
# SHEET 1: SYSTEM OVERVIEW & INTERCONNECTION ARCHITECTURE
# =============================================================================
def generate_sheet_1():
    fig, ax = create_base_canvas(1, 6, "System Overview & Interconnection Architecture", "General Overview")
    
    # Overview Description Banner
    ax.add_patch(patches.Rectangle((8, 149), 264, 11, facecolor='#F8FAFC', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(12, 156.5, "SYSTEM OVERVIEW & DESIGN SPECIFICATION:", fontsize=8.5, fontweight='bold', color=BORDER_MAIN)
    ax.text(12, 152.5, "This drawing package details the electrical schematics, power distribution, co-processor pulse interfaces, remote field I/O,", fontsize=7.2, color=TEXT_MAIN)
    ax.text(12, 149.5, "and motion safety interlocks for the 3-axis automated electronics dispensing machine (Narit Smart Vending Machine).", fontsize=7.2, color=TEXT_MAIN)
    ax.text(205, 154, "Operating Temp: 0 - 50 °C\nRated Voltage: 220VAC 50Hz\nRated Power: 650W Max", fontsize=7.2, color=BORDER_MAIN, fontweight='bold')

    # Top Block: System Subsystem Blocks
    # Block 1: Power Subsystem
    draw_module(ax, 8, 86, 48, 58, "1. POWER DISTRIBUTION", "AC Mains, MCB, Filter, PSUs", header_color=MOD_HDR_RED)
    ax.text(11, 137, "• AC Mains 220VAC 50Hz Inlet", fontsize=7.0, color=TEXT_MAIN)
    ax.text(11, 132, "• 2-Pole MCB C16 Circuit Breaker", fontsize=7.0, color=TEXT_MAIN)
    ax.text(11, 127, "• CW4L2-20A-S Noise Filter & SPD", fontsize=7.0, color=TEXT_MAIN)
    ax.text(11, 122, "• PSU 1: 60VDC 6.7A (Motors X/Y)", fontsize=7.0, color=W_60V, fontweight='bold')
    ax.text(11, 117, "• PSU 2: 24VDC 5A (Control & Z)", fontsize=7.0, color=W_24V, fontweight='bold')
    ax.text(11, 112, "• PSU 3: 5VDC 3A (CM4 Isolated)", fontsize=7.0, color=W_5V, fontweight='bold')
    ax.text(11, 107, "• KM1 Safety Contactor & Cutoff", fontsize=7.0, color=W_ALM, fontweight='bold')
    ax.text(11, 102, "• E-Stop Hardwired Safety Loop", fontsize=7.0, color=W_ALM)
    ax.text(11, 93, "Refer to SHEET 2 for detailed wiring.", fontsize=6.8, color=BORDER_MAIN, style='italic')

    # Block 2: Main Controller (IRiV PiControl)
    draw_module(ax, 62, 86, 52, 58, "2. MAIN CONTROLLER", "Cytron IRiV PiControl CM4", header_color=MOD_HDR_NAVY)
    ax.text(65, 137, "• Raspberry Pi CM4 (4GB RAM, 32GB eMMC)", fontsize=7.0, color=TEXT_MAIN)
    ax.text(65, 132, "• eth0: MGMT LAN (192.168.70.80 / UI)", fontsize=7.0, color=W_ETH)
    ax.text(65, 127, "• eth1: OT LAN (10.0.0.2 Modbus Master)", fontsize=7.0, color=W_ETH)
    ax.text(65, 122, "• USB4: ST-LINK V3 Serial (115200 8-N-1)", fontsize=7.0, color=W_ALM)
    ax.text(65, 117, "• Local DI0-DI1: X/Y Drive Alarm (ALM)", fontsize=7.0, color=W_ALM)
    ax.text(65, 112, "• Local DI2-DI3: X/Y In-Position (PEND)", fontsize=7.0, color=W_DIR)
    ax.text(65, 107, "• Local DO0: KM1 Coil Control & Reset", fontsize=7.0, color=W_24V)
    ax.text(65, 102, "• Software Watchdog: Auto-disarm 350ms", fontsize=7.0, color=W_ALM)
    ax.text(65, 93, "Refer to SHEET 3 for detailed wiring.", fontsize=6.8, color=BORDER_MAIN, style='italic')

    # Block 3: Remote Field I/O (Cytron IRiV IO)
    draw_module(ax, 120, 86, 48, 58, "3. REMOTE FIELD I/O", "Cytron IRiV IO Modbus TCP", header_color=MOD_HDR_AMBER)
    ax.text(123, 137, "• Modbus TCP Slave (10.0.0.10:502)", fontsize=7.0, color=TEXT_MAIN)
    ax.text(123, 132, "• 11 x Digital Inputs (24V Opto):", fontsize=7.0, color=TEXT_MAIN)
    ax.text(127, 127, "- DI0-DI5: Limits X/Y/Z Min & Max", fontsize=6.8, color=W_SIG)
    ax.text(127, 122, "- DI6: Z Home Reference Sensor", fontsize=6.8, color=W_SIG)
    ax.text(127, 117, "- DI7: Drop Alignment Sensor", fontsize=6.8, color=W_SIG)
    ax.text(127, 112, "- DI8: Drop Beam (Omron E3Z)", fontsize=6.8, color=W_ALM)
    ax.text(127, 107, "- DI9: Pickup Door (Omron E3Z)", fontsize=6.8, color=W_ALM)
    ax.text(127, 102, "- DI10: KM1 E-Stop Loop (NC)", fontsize=6.8, color=W_ALM)
    ax.text(123, 97, "• 4 x Digital Outputs (Pilot Lights/Relay)", fontsize=7.0, color=TEXT_MAIN)
    ax.text(123, 93, "Refer to SHEET 4 for detailed wiring.", fontsize=6.8, color=BORDER_MAIN, style='italic')

    # Block 4: Motion Co-Processor (STM32 + NMOS)
    draw_module(ax, 174, 86, 48, 58, "4. MOTION CO-PROCESSOR", "STM32 NUCLEO-G491RE + NMOS", header_color=MOD_HDR_NAVY)
    ax.text(177, 137, "• ARM Cortex-M4 @ 170MHz", fontsize=7.0, color=TEXT_MAIN)
    ax.text(177, 132, "• Hardware Timer Compare Pulse Gen", fontsize=7.0, color=TEXT_MAIN)
    ax.text(177, 127, "• X: PA8 (TIM1_CH1) / PB0 (GPIO)", fontsize=7.0, color=W_STEP)
    ax.text(177, 122, "• Y: PA9 (TIM1_CH2) / PB1 (GPIO)", fontsize=7.0, color=W_STEP)
    ax.text(177, 117, "• Z: PA5 (TIM2_CH1) / PB2 (GPIO)", fontsize=7.0, color=W_STEP)
    ax.text(177, 112, "• 6-Channel NMOS Open-Drain Board", fontsize=7.0, color=TEXT_MAIN)
    ax.text(177, 107, "• Common Anode V-PULSE (+24VDC)", fontsize=7.0, color=W_24V, fontweight='bold')
    ax.text(177, 102, "• Safe-Link Protocol v3 / Watchdog", fontsize=7.0, color=W_ALM)
    ax.text(177, 93, "Refer to SHEET 5 for detailed wiring.", fontsize=6.8, color=BORDER_MAIN, style='italic')

    # Block 5: Motor Drives & Actuators
    draw_module(ax, 228, 86, 44, 58, "5. DRIVES & ACTUATORS", "HBS860H, DM542, Steppers", header_color=MOD_HDR_TEAL)
    ax.text(231, 137, "• Drive X: HBS860H Closed-Loop", fontsize=7.0, color=TEXT_MAIN)
    ax.text(235, 132, "Motor: 86HBS85 (8.5 N.m)", fontsize=6.8, color=TEXT_MUTED)
    ax.text(231, 127, "• Drive Y: HBS860H Closed-Loop", fontsize=7.0, color=TEXT_MAIN)
    ax.text(235, 122, "Motor: 86HBS85 (SFU1605)", fontsize=6.8, color=TEXT_MUTED)
    ax.text(231, 117, "• Drive Z: DM542 Microstepping", fontsize=7.0, color=TEXT_MAIN)
    ax.text(235, 112, "Motor: NEMA 17 Pusher", fontsize=6.8, color=TEXT_MUTED)
    ax.text(231, 107, "• Differential Optical Encoders", fontsize=7.0, color=W_ETH)
    ax.text(231, 102, "• V-PULSE 24V Opto Isolation", fontsize=7.0, color=W_24V)
    ax.text(231, 93, "Refer to SHEET 6 for detailed wiring.", fontsize=6.8, color=BORDER_MAIN, style='italic')

    # Main interconnecting buses between blocks
    draw_wire(ax, [(56, 115), (62, 115)], W_24V, lw=2.0)  # Power to PiControl
    draw_wire(ax, [(114, 127), (120, 127)], W_ETH, lw=2.0) # Ethernet to IRiV IO
    draw_wire(ax, [(114, 122), (174, 122)], W_ALM, lw=2.0) # USB to STM32
    draw_wire(ax, [(222, 120), (228, 120)], W_STEP, lw=2.0) # Pulses to Drives

    # Bottom Half: Master Cable Interconnection Schedule
    draw_module(ax, 8, 10, 264, 71, "MASTER INTERCONNECTION & CABLE SCHEDULE", 
                "Cable IDs, Signal Types, Terminations, and Specifications", header_color=BORDER_MAIN)

    headers = [("CABLE ID", 11, 22), ("FROM (SOURCE)", 33, 45), ("TO (DESTINATION)", 78, 48), 
               ("SIGNAL / FUNCTION", 126, 45), ("CONDUCTORS / GAUGE", 171, 48), ("ROUTING / REMARKS", 219, 50)]
    for title, xpos, width in headers:
        ax.add_patch(patches.Rectangle((xpos, 68), width, 4, facecolor='#E2E8F0', edgecolor=BORDER_SUB, linewidth=0.6))
        ax.text(xpos + width/2, 70, title, fontsize=7.0, fontweight='bold', color=BORDER_MAIN, ha='center', va='center')

    cables = [
        ("W-01", "AC Inlet C14 / Main Cord", "MCB 2P 16A Input (1, 3)", "220VAC Mains Power", "3 x 2.5 mm² (L, N, PE)", "Mains Cable Raceway"),
        ("W-02", "MCB Output (2, 4)", "CW4L2-20A-S Noise Filter In", "Protected AC Mains", "2 x 2.5 mm² (L, N)", "Cabinet Power Duct"),
        ("W-03", "Noise Filter Load (L', N')", "AC Terminal Bus TB-L / TB-N", "Clean Filtered AC Bus", "2 x 2.5 mm² (L, N)", "DIN Rail Distribution"),
        ("W-04", "TB-L / TB-N / TB-PE", "PSU1, PSU2, PSU3 AC Inputs", "Parallel DC PSU Feeds", "3 x (3 x 1.5 mm²)", "DIN Rail Jumper Bars"),
        ("W-05", "PSU 1 (+60V, 0V)", "KM1 Contactor (1-2, 3-4)", "High Voltage Motor DC", "2 x 2.5 mm² (Red, Blk)", "Direct to KM1 Contacts"),
        ("W-06", "KM1 Contactor Out", "Drivers X & Y AC/AC Terminals", "Motor Bus (+60VDC)", "2 x 2.5 mm² (Red, Blk)", "Separated from Signal"),
        ("W-07", "PSU 2 (+24V, 0V)", "PiControl, IRiV IO, Sensors", "Control & Logic Bus", "2 x 1.5 mm² (Orn, Blk)", "Main DC Control Duct"),
        ("W-08", "PSU 3 USB-C (5V 3A)", "IRiV PiControl CM4 USB-C", "Isolated CM4 Power", "Official 18AWG Type-C", "Dedicated Short Run"),
        ("W-09", "PiControl eth1 (OT LAN)", "IRiV IO Modbus RJ45 Port", "Modbus TCP 10.0.0.10:502", "Cat6 UTP Patch Cable", "Industrial Ethernet"),
        ("W-10", "PiControl USB4 Port", "NUCLEO-G491RE ST-LINK VCP", "Safe-Link Protocol v3", "Shielded USB-A to Micro-B", "Ferrite Choke Protected"),
        ("W-11", "PiControl DO0 (GPIO 23)", "KM1 Contactor Coil A1/A2", "Safety Cutoff / 3s Reset", "2 x 0.75 mm² Twisted", "Series with E-Stop NC"),
        ("W-12", "KM1 Contactor Aux NC", "IRiV IO DI10 Terminal", "Hardware State Feedback", "2 x 0.5 mm² Shielded", "Fail-Safe NC Loop"),
        ("W-13", "STM32 Morpho Headers", "6-Ch NMOS Board Gates", "3.3V Timer Pulse/Dir", "Ribbon Cable 10-pin", "< 150mm Short Run"),
        ("W-14", "NMOS Drains & V-PULSE", "Drivers X, Y, Z (PUL, DIR)", "24V Opto-Isolated Drive", "6 x Twisted Pairs 0.5mm²", "Separated from Motor 60V"),
        ("W-15", "Drivers X & Y Output", "86HBS85 Motors A/B & Encoders", "Motor Coils & Differential", "Shielded 4-core + Enc", "Grounded at Cabinet PE"),
        ("W-16", "Field Proximity & Optical", "IRiV IO DI0 - DI9 Terminals", "24V Limit & Sensor Inputs", "Shielded 3-core 0.5mm²", "Bottom Raceway Duct"),
    ]

    y_pos = 64.5
    for cid, src, dst, sig, cond, rmks in cables:
        bg = '#F8FAFC' if (y_pos % 4 < 2) else '#FFFFFF'
        ax.add_patch(patches.Rectangle((11, y_pos), 258, 3.2, facecolor=bg, edgecolor='#E2E8F0', linewidth=0.5))
        ax.text(22, y_pos + 1.6, cid, fontsize=6.8, fontweight='bold', color=BORDER_MAIN, ha='center', va='center')
        ax.text(34, y_pos + 1.6, src, fontsize=6.5, color=TEXT_MAIN, va='center')
        ax.text(79, y_pos + 1.6, dst, fontsize=6.5, color=TEXT_MAIN, va='center')
        ax.text(127, y_pos + 1.6, sig, fontsize=6.5, color=TEXT_MAIN, va='center')
        ax.text(172, y_pos + 1.6, cond, fontsize=6.5, color=BORDER_MAIN, va='center')
        ax.text(220, y_pos + 1.6, rmks, fontsize=6.5, color=TEXT_MUTED, va='center')
        y_pos -= 3.3

    return fig

# =============================================================================
# SHEET 2: SECTION 1 — AC MAINS DISTRIBUTION & DC POWER SUPPLIES
# =============================================================================
def generate_sheet_2():
    fig, ax = create_base_canvas(2, 6, "Section 1: AC Mains Distribution & DC Power Supplies", "Power Distribution")
    
    # Left Half: AC Distribution Schematic
    draw_module(ax, 8, 14, 130, 144, "AC MAINS 220VAC INLET & NOISE SUPPRESSION", 
                "Single-Phase 220V 50Hz, Circuit Protection, and EMI Filtering", header_color=MOD_HDR_RED)

    # 1.1 Inlet
    draw_module(ax, 14, 122, 54, 28, "AC MAINS INLET (IEC C14)", "220VAC 1-Phase 50Hz", header_color=MOD_HDR_SLATE)
    draw_term(ax, 16, 137, "LINE (L)", "220VAC (Brown)", color=W_AC_L, bg='#FEF2F2', width=22)
    draw_term(ax, 16, 133, "NEUTRAL (N)", "0VAC (Blue)", color=W_AC_N, bg='#EFF6FF', width=22)
    draw_term(ax, 16, 129, "EARTH (PE)", "Chassis Ground", color=W_PE, bg='#F0FDF4', width=22)
    ax.text(42, 134, "FUSED INLET\n10A 250V\nGlass Tube", fontsize=6.8, color=TEXT_MUTED, ha='center', va='center')

    # 1.2 MCB
    draw_module(ax, 78, 122, 54, 28, "MAIN BREAKER (MCB 2P)", "Miniature Circuit Breaker C16", header_color=MOD_HDR_SLATE)
    draw_term(ax, 80, 140, "POLE 1 (L_in)", "Line In", color=W_AC_L, bg='#FEF2F2', width=24)
    draw_term(ax, 80, 136, "POLE 3 (N_in)", "Neutral In", color=W_AC_N, bg='#EFF6FF', width=24)
    draw_term(ax, 80, 130, "POLE 2 (L_out)", "Line Out", color=W_AC_L, bg='#FEF2F2', width=24)
    draw_term(ax, 80, 126, "POLE 4 (N_out)", "Neutral Out", color=W_AC_N, bg='#EFF6FF', width=24)
    ax.text(118, 133, "In = 16A\nCurve C\nIcu = 6kA", fontsize=6.8, color=TEXT_MUTED, ha='center', va='center')

    # Connect Inlet to MCB
    draw_wire(ax, [(38, 138.1), (58, 138.1), (58, 141.1), (80, 141.1)], W_AC_L, lw=1.5)
    draw_wire(ax, [(38, 134.1), (60, 134.1), (60, 137.1), (80, 137.1)], W_AC_N, lw=1.5)

    # 1.3 EMI Filter
    draw_module(ax, 14, 82, 54, 30, "EMI LINE FILTER (CW4L2-20A-S)", "Dual-Stage High Attenuation", header_color=MOD_HDR_SLATE)
    draw_term(ax, 16, 99, "LINE (L)", "Filter Input", color=W_AC_L, bg='#FEF2F2', width=22)
    draw_term(ax, 16, 95, "NEUTRAL (N)", "Filter Input", color=W_AC_N, bg='#EFF6FF', width=22)
    draw_term(ax, 16, 89, "LOAD (L')", "Filtered Live", color=W_AC_L, bg='#FEF2F2', width=22)
    draw_term(ax, 16, 85, "LOAD (N')", "Filtered Neut", color=W_AC_N, bg='#EFF6FF', width=22)
    draw_term(ax, 40, 89, "FG (EARTH)", "Chassis Earth", color=W_PE, bg='#F0FDF4', width=24)

    # Connect MCB to EMI Filter
    draw_wire(ax, [(104, 131.1), (114, 131.1), (114, 116), (72, 116), (72, 100.1), (38, 100.1)], W_AC_L, lw=1.5)
    draw_wire(ax, [(104, 127.1), (112, 127.1), (112, 114), (70, 114), (70, 96.1), (38, 96.1)], W_AC_N, lw=1.5)

    # 1.4 SPD
    draw_module(ax, 78, 82, 54, 30, "SURGE ARRESTER (SPD)", "Type 2 DIN Rail Surge Protection", header_color=MOD_HDR_SLATE)
    draw_term(ax, 80, 99, "L (Phase)", "To Filtered L", color=W_AC_L, bg='#FEF2F2', width=24)
    draw_term(ax, 80, 95, "N (Neutral)", "To Filtered N", color=W_AC_N, bg='#EFF6FF', width=24)
    draw_term(ax, 80, 87, "PE (Earth)", "Ground Bar", color=W_PE, bg='#F0FDF4', width=24)
    ax.text(118, 93, "Uc = 275VAC\nIn = 10kA\nImax = 20kA", fontsize=6.8, color=TEXT_MUTED, ha='center', va='center')

    # Connect EMI to SPD
    draw_wire(ax, [(38, 90.1), (50, 90.1), (50, 100.1), (80, 100.1)], W_AC_L, lw=1.5)
    draw_wire(ax, [(38, 86.1), (48, 86.1), (48, 96.1), (80, 96.1)], W_AC_N, lw=1.5)

    # 1.5 AC DIN Rail Power Distribution Bus
    draw_module(ax, 14, 20, 118, 52, "AC DIN RAIL DISTRIBUTION TERMINAL BLOCKS", 
                "Screw Clamp Terminal Blocks with Jumper Bars (1-in 4-out)", header_color=MOD_HDR_NAVY)
    draw_term(ax, 18, 56, "TB-L (PHASE BUS)", "220VAC Live Distribution", color=W_AC_L, bg='#FEF2F2', width=52)
    draw_term(ax, 18, 50, "TB-N (NEUTRAL BUS)", "0VAC Neutral Distribution", color=W_AC_N, bg='#EFF6FF', width=52)
    draw_term(ax, 18, 44, "TB-PE (EARTH BAR)", "Protective Chassis Earth Bus", color=W_PE, bg='#F0FDF4', width=52)
    
    # Explanatory card
    ax.add_patch(patches.Rectangle((74, 23), 54, 45, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(77, 63, "AC BUS FEED ALLOCATIONS:", fontsize=7.2, fontweight='bold', color=BORDER_MAIN)
    ax.text(77, 58, "• Branch 1: PSU 1 (60V 6.7A Motor Supply)", fontsize=6.8, color=W_60V, fontweight='bold')
    ax.text(77, 53, "• Branch 2: PSU 2 (24V 5A Control Supply)", fontsize=6.8, color=W_24V, fontweight='bold')
    ax.text(77, 48, "• Branch 3: PSU 3 (5V 3A USB-C CM4 Supply)", fontsize=6.8, color=W_5V, fontweight='bold')
    ax.text(77, 43, "• Branch 4: Spare DIN Rail Terminal", fontsize=6.8, color=TEXT_MUTED)
    ax.text(77, 36, "Wiring Standard: IEC 60204-1\nAC Phase: Brown 2.5 mm²\nNeutral: Light Blue 2.5 mm²\nEarth: Green/Yellow 2.5 mm²", fontsize=6.5, color=TEXT_MUTED)

    # Connect SPD/EMI to AC Bus
    draw_wire(ax, [(50, 90.1), (50, 57.1)], W_AC_L, lw=1.5)
    draw_wire(ax, [(48, 86.1), (48, 51.1)], W_AC_N, lw=1.5)

    # Right Half: DC Power Supplies & KM1 Contactor
    draw_module(ax, 144, 14, 128, 144, "DC POWER SUPPLIES & KM1 SAFETY POWER INTERLOCK", 
                "Multi-Voltage DC Power Rails with Hardware Emergency Contactor Cutoff", header_color=MOD_HDR_RED)

    # PSU 1: 60VDC
    draw_module(ax, 148, 108, 58, 44, "PSU 1: 60VDC 6.7A (400W)", "Switching Motor Supply", header_color=MOD_HDR_RED)
    draw_term(ax, 150, 137, "AC INPUT (L, N, FG)", "From TB-L, TB-N, TB-PE", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=32)
    draw_term(ax, 150, 132, "DC OUT +V (+60V)", "Pin V+ (x2)", color=W_60V, bg='#FEF2F2', width=32)
    draw_term(ax, 150, 127, "DC OUT -V (COM)", "Pin V- (x2)", color=W_GND, bg=TERM_BG_EVEN, width=32)
    draw_term(ax, 150, 120, "V-ADJ TRIM", "Trim range 58-62VDC", color=TEXT_MUTED, bg='#FFFFFF', width=32)
    ax.text(194, 128, "Powers Drivers\nX & Y via KM1\nContactor", fontsize=6.8, color=W_60V, ha='center', va='center', fontweight='bold')

    # PSU 2: 24VDC
    draw_module(ax, 148, 58, 58, 44, "PSU 2: 24VDC 5A (120W)", "Industrial Control Supply (Mean Well)", header_color=MOD_HDR_AMBER)
    draw_term(ax, 150, 87, "AC INPUT (L, N, FG)", "From TB-L, TB-N, TB-PE", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=32)
    draw_term(ax, 150, 82, "DC OUT +24V", "Control V+", color=W_24V, bg='#FFF7ED', width=32)
    draw_term(ax, 150, 77, "DC OUT 0V / GND", "Control V-", color=W_GND, bg=TERM_BG_EVEN, width=32)
    draw_term(ax, 150, 70, "DC OK LED", "Green Status Indicator", color=W_PE, bg='#F0FDF4', width=32)
    ax.text(194, 78, "Powers IRiV IO,\nPiControl 24V,\nSensors, Relays,\nV-PULSE & Z Drive", fontsize=6.8, color=W_24V, ha='center', va='center', fontweight='bold')

    # PSU 3: 5VDC
    draw_module(ax, 148, 18, 58, 36, "PSU 3: 5VDC 3A (15W)", "Raspberry Pi USB-C Power Adapter", header_color=MOD_HDR_SLATE)
    draw_term(ax, 150, 42, "AC INPUT (L, N)", "Euro/US 2-pin Plug", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=32)
    draw_term(ax, 150, 37, "USB-C VBUS (+5.1V)", "Dedicated CM4 Power", color=W_5V, bg='#FAF5FF', width=32)
    draw_term(ax, 150, 32, "USB-C GND (0V)", "Isolated Return", color=W_GND, bg=TERM_BG_EVEN, width=32)
    ax.text(194, 34, "Isolated 5V Rail\nProtects CM4 Core\nfrom Ground Loops", fontsize=6.8, color=W_5V, ha='center', va='center')

    # KM1 Safety Contactor (Far Right)
    draw_module(ax, 212, 38, 56, 114, "KM1 SAFETY CONTACTOR & HARDWARE E-STOP", 
                "Independent Safety Power Cutoff Interlock", header_color=MOD_HDR_RED)
    draw_term(ax, 214, 137, "MAIN CONTACT 1 (L1 In)", "+60VDC from PSU 1 V+", color=W_60V, bg='#FEF2F2', width=28)
    draw_term(ax, 214, 133, "MAIN CONTACT 2 (T1 Out)", "+60VDC to Drivers X & Y", color=W_60V, bg='#FEF2F2', width=28)
    draw_term(ax, 214, 126, "MAIN CONTACT 3 (L2 In)", "0VDC from PSU 1 V-", color=W_GND, bg=TERM_BG_EVEN, width=28)
    draw_term(ax, 214, 122, "MAIN CONTACT 4 (T2 Out)", "0VDC to Drivers X & Y", color=W_GND, bg=TERM_BG_EVEN, width=28)
    
    draw_term(ax, 214, 112, "COIL A1 (+24VDC)", "Controlled by PiControl DO0", color=W_24V, bg='#FFF7ED', width=28)
    draw_term(ax, 214, 108, "COIL A2 (0V Return)", "Series with E-Stop NC", color=W_ALM, bg='#FEF2F2', width=28)
    
    draw_term(ax, 214, 98, "AUX NC CONTACT (21-22)", "Feedback -> IRiV IO DI10", color=W_ALM, bg='#FEF2F2', width=28)
    draw_term(ax, 214, 94, "AUX NO CONTACT (13-14)", "Status Indicator / Spare", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=28)

    # Detailed safety explanation box
    ax.add_patch(patches.Rectangle((214, 42), 52, 48, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(216, 85, "SAFETY INTERLOCK SPECIFICATION:", fontsize=7.0, fontweight='bold', color=MOD_HDR_RED)
    ax.text(216, 80, "1. HARDWARE E-STOP PRIORITY:", fontsize=6.8, fontweight='bold', color=TEXT_MAIN)
    ax.text(216, 76, "Emergency Stop button directly breaks the KM1 coil circuit.", fontsize=6.5, color=TEXT_MAIN)
    ax.text(216, 72, "Drops +60V rail within < 15ms. Software cannot override.", fontsize=6.5, color=W_ALM, fontweight='bold')
    ax.text(216, 67, "2. SOFTWARE RESET (PiControl DO0):", fontsize=6.8, fontweight='bold', color=TEXT_MAIN)
    ax.text(216, 63, "Toggles coil off for bounded 3.0s to clear drive alarms.", fontsize=6.5, color=W_24V)
    ax.text(216, 58, "3. FEEDBACK TO IRiV IO DI10:", fontsize=6.8, fontweight='bold', color=TEXT_MAIN)
    ax.text(216, 54, "Confirms physical armature position (Fail-Safe NC loop).", fontsize=6.5, color=TEXT_MAIN)
    ax.text(216, 49, "4. SAFETY NOTICE (Z AXIS):", fontsize=6.8, fontweight='bold', color=MOD_HDR_RED)
    ax.text(216, 45, "Z Drive DM542 24V power should route through safety cutoff.", fontsize=6.5, color=W_ALM)

    # Wires from PSU1 to KM1
    draw_wire(ax, [(182, 133.1), (200, 133.1), (200, 138.1), (214, 138.1)], W_60V, lw=1.8)
    draw_wire(ax, [(182, 128.1), (198, 128.1), (198, 127.1), (214, 127.1)], W_GND, lw=1.8)

    return fig

# =============================================================================
# SHEET 3: SECTION 2 — MAIN CONTROLLER (Cytron IRiV PiControl CM4)
# =============================================================================
def generate_sheet_3():
    fig, ax = create_base_canvas(3, 6, "Section 2: Main Controller (Cytron IRiV PiControl CM4)", "Main Controller")

    # Main PiControl Enclosure (Center Left)
    draw_module(ax, 8, 14, 150, 144, "Cytron IRiV PiControl CM4 WIRELESS CONTROLLER", 
                "Raspberry Pi CM4 (4GB RAM, 32GB eMMC, Wi-Fi, Dual Ethernet, Isolated GPIO)", header_color=MOD_HDR_NAVY)

    # Sub-card: Power & Ethernet
    ax.text(12, 148, "1. SYSTEM POWER & DUAL GIGABIT ETHERNET INTERFACES:", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    draw_term(ax, 12, 139, "DC 24V IN (+)", "Auxiliary 24VDC Terminal", color=W_24V, bg='#FFF7ED', width=42)
    draw_term(ax, 12, 135, "DC 0V IN (-)", "Field Ground 0VDC", color=W_GND, bg=TERM_BG_EVEN, width=42)
    draw_term(ax, 58, 139, "USB-C VBUS (5V)", "CM4 Core Primary Power", color=W_5V, bg='#FAF5FF', width=44)
    draw_term(ax, 58, 135, "PWR / ACT LED", "System Status Indicators", color=W_PE, bg='#F0FDF4', width=44)
    
    draw_term(ax, 106, 139, "eth0: MGMT LAN", "192.168.70.80 / Flask REST", color=W_ETH, bg='#EFF6FF', width=48)
    draw_term(ax, 106, 135, "eth1: OT LAN", "10.0.0.2 / Modbus Master", color=W_ETH, bg='#EFF6FF', width=48)

    # Sub-card: USB 2.0 Peripherals
    ax.text(12, 128, "2. USB 2.0 PERIPHERAL PORTS (DEVICE INTERFACES):", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    draw_term(ax, 12, 119, "USB 1: QR SCANNER", "2D Barcode / Payment QR CDC", color=W_USB, bg='#EEF2FF', width=68)
    draw_term(ax, 84, 119, "USB 2: WEB CAMERA", "FHD 1080p UVC Video Stream", color=W_USB, bg='#EEF2FF', width=70)
    draw_term(ax, 12, 115, "USB 3 / 3.5mm AUDIO", "Chime / Audio Voice Guidance", color=W_5V, bg='#FAF5FF', width=68)
    draw_term(ax, 84, 115, "USB 4: ST-LINK VCP", "To NUCLEO-G491RE (115200 8-N-1)", color=W_ALM, bg='#FEF2F2', width=70)

    # Sub-card: Local Isolated Digital I/O (Pinout & Function Table)
    ax.text(12, 108, "3. LOCAL OPTO-ISOLATED GPIO TERMINAL BLOCK (FAIL-SAFE CHANNELS):", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    
    io_rows = [
        ("DI0 (GPIO 13)", "X_DRIVE_ALM", "Driver X Alarm (Fail-Safe)", "Active HIGH / Trips on open-circuit", W_ALM, '#FEF2F2'),
        ("DI1 (GPIO 17)", "Y_DRIVE_ALM", "Driver Y Alarm (Fail-Safe)", "Active HIGH / Trips on open-circuit", W_ALM, '#FEF2F2'),
        ("DI2 (GPIO 27)", "X_PEND", "Driver X In-Position", "Position-End verification signal", W_DIR, '#FFFBEB'),
        ("DI3 (GPIO 22)", "Y_PEND", "Driver Y In-Position", "Position-End verification signal", W_DIR, '#FFFBEB'),
        ("DO0 (GPIO 23)", "XY_DRIVE_POWER_KM1", "KM1 Safety Contactor Driver", "Hardware 3.0s reset pulse & safety coil", W_24V, '#FFF7ED'),
        ("DO1 (GPIO 24)", "RELAY_AUX_1", "Auxiliary Output 1", "General purpose 24V SSR driver", TEXT_MUTED, TERM_BG_EVEN),
        ("DO2 (GPIO 25)", "RELAY_AUX_2", "Auxiliary Output 2", "General purpose 24V SSR driver", TEXT_MUTED, TERM_BG_EVEN),
        ("DO3 (GPIO 16)", "RELAY_AUX_3", "Auxiliary Output 3", "General purpose 24V SSR driver", TEXT_MUTED, TERM_BG_EVEN),
    ]

    y_t = 98
    for ch, name, desc, note, col, bg in io_rows:
        draw_term(ax, 12, y_t, ch, name, color=col, bg=bg, width=42)
        draw_term(ax, 58, y_t, desc, note, color=TEXT_MAIN, bg='#FFFFFF', width=96)
        y_t -= 5.0

    # Sub-card: Software Daemons & IPC Architecture
    ax.add_patch(patches.Rectangle((12, 20), 142, 34, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(15, 49, "SYSTEM DAEMONS & IPC CONTROL GATES:", fontsize=7.5, fontweight='bold', color=MOD_HDR_NAVY)
    ax.text(15, 45, "• Daemon 1: narit-vending-web-iriv.service (Flask HMI Port 80, Touchscreen Kiosk UI)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 41.5, "• Daemon 2: narit-vending-controller-iriv.service (Hardware Safety Interlock Engine)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 38, "• IPC Bus: Unix Domain Socket /run/narit-vending/ctrl.sock (Non-blocking JSON)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 34.5, "• Modbus TCP Master: Polls IRiV IO (10.0.0.10:502) every 20ms; Disarms if stale > 350ms", fontsize=6.8, color=W_ALM, fontweight='bold')
    ax.text(15, 31, "• Safe-Link Protocol v3: USB Serial to STM32 (115200 8-N-1); Heartbeat timeout 500ms", fontsize=6.8, color=BORDER_MAIN)
    ax.text(15, 27.5, "• Cloud Broker: MQTT Hub (broker.emqx.io:1883) for telemetry, status and inventory", fontsize=6.8, color=W_ETH)
    ax.text(15, 24, "• Persistent Storage: SQLite database + machine_config.iriv.json configuration", fontsize=6.8, color=TEXT_MUTED)

    # Right Half: Peripheral Details & Interconnection Diagram
    draw_module(ax, 164, 14, 108, 144, "PERIPHERAL MODULES & FIELD CABLE TERMINATIONS", 
                "Scanner, Camera, Audio, Ethernet, and ST-LINK Connections", header_color=MOD_HDR_SLATE)

    # Scanner Box
    draw_module(ax, 168, 116, 48, 36, "2D QR CODE SCANNER", "Barcode & Payment Scanner", header_color=MOD_HDR_SLATE)
    draw_term(ax, 170, 137, "VBUS (+5VDC)", "USB Power Pin 1", color=W_5V, bg='#FAF5FF', width=44)
    draw_term(ax, 170, 133, "D- / D+ (DATA)", "USB 2.0 Differential", color=W_USB, bg='#EEF2FF', width=44)
    draw_term(ax, 170, 129, "GND (0V RETURN)", "USB Ground Pin 4", color=W_GND, bg=TERM_BG_EVEN, width=44)
    draw_term(ax, 170, 121, "BEEPER / LED", "Scan Confirmation", color=W_PE, bg='#F0FDF4', width=44)

    # Camera Box
    draw_module(ax, 220, 116, 48, 36, "FHD WEB CAMERA", "Dispense / Pickup Vision", header_color=MOD_HDR_SLATE)
    draw_term(ax, 222, 137, "VBUS (+5VDC)", "USB Power Pin 1", color=W_5V, bg='#FAF5FF', width=44)
    draw_term(ax, 222, 133, "D- / D+ (UVC)", "1080p Video Stream", color=W_USB, bg='#EEF2FF', width=44)
    draw_term(ax, 222, 129, "GND (0V RETURN)", "USB Ground Pin 4", color=W_GND, bg=TERM_BG_EVEN, width=44)
    draw_term(ax, 222, 121, "INDICATOR LED", "Active Stream Light", color=W_SIG, bg='#F0FDFA', width=44)

    # Audio Speaker Box
    draw_module(ax, 168, 72, 48, 38, "AUDIO AMPLIFIER & SPEAKER", "Voice Guidance / Chime", header_color=MOD_HDR_SLATE)
    draw_term(ax, 170, 95, "AUDIO L / R IN", "3.5mm Stereo Jack", color=W_5V, bg='#FAF5FF', width=44)
    draw_term(ax, 170, 91, "POWER (+5V / 0V)", "USB Power Supply", color=W_5V, bg='#FAF5FF', width=44)
    draw_term(ax, 170, 87, "SPEAKER OUT (3W)", "4-Ohm Transducer", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=44)
    draw_term(ax, 170, 79, "VOLUME POT", "Hardware Gain Adjust", color=TEXT_MUTED, bg='#FFFFFF', width=44)

    # ST-LINK Serial Link Box
    draw_module(ax, 220, 72, 48, 38, "ST-LINK V3 SERIAL VCP", "To NUCLEO-G491RE", header_color=MOD_HDR_RED)
    draw_term(ax, 222, 95, "USB CDC ACM", "/dev/serial/by-id/...", color=W_ALM, bg='#FEF2F2', width=44)
    draw_term(ax, 222, 91, "BAUDRATE", "115200 8-N-1", color=MOD_HDR_NAVY, bg='#EFF6FF', width=44)
    draw_term(ax, 222, 87, "PROTOCOL", "Safe-Link v3 Binary", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=44)
    draw_term(ax, 222, 79, "HEARTBEAT", "Timeout = 500 ms", color=W_ALM, bg='#FEF2F2', width=44)

    # Ethernet Architecture Card
    draw_module(ax, 168, 18, 100, 48, "ETHERNET DUAL-SUBNET ARCHITECTURE", 
                "Physical Network Separation (Air-Gapped Management vs OT)", header_color=MOD_HDR_NAVY)
    ax.text(171, 55, "SUBNET 1: MANAGEMENT LAN (eth0)", fontsize=7.2, fontweight='bold', color=W_ETH)
    ax.text(171, 51, "• IP: 192.168.70.80 / 24 | Gateway: 192.168.70.1", fontsize=6.8, color=TEXT_MAIN)
    ax.text(171, 47, "• Function: Kiosk Touchscreen HMI, Web API, Cloud MQTT, Remote SSH", fontsize=6.8, color=TEXT_MAIN)
    ax.text(171, 41, "SUBNET 2: OPERATIONAL TECHNOLOGY LAN (eth1)", fontsize=7.2, fontweight='bold', color=MOD_HDR_AMBER)
    ax.text(171, 37, "• IP: 10.0.0.2 / 24 | Target: 10.0.0.10 (Cytron IRiV IO Modbus)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(171, 33, "• Function: High-speed cyclic I/O polling (20ms interval)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(171, 28, "• Safety: Isolated industrial broadcast domain; prevents network collisions.", fontsize=6.8, color=W_ALM, fontweight='bold')

    return fig

# =============================================================================
# SHEET 4: SECTION 3 — REMOTE FIELD I/O & SENSOR INTERFACING
# =============================================================================
def generate_sheet_4():
    fig, ax = create_base_canvas(4, 6, "Section 3: Remote Field I/O & Sensor Interfacing", "Field I/O & Sensors")

    # Cytron IRiV IO Box (Left Side)
    draw_module(ax, 8, 14, 136, 144, "Cytron IRiV IO CONTROLLER (MODBUS TCP)", 
                "Industrial Remote Field I/O (11 DI, 4 DO, 24VDC Opto-Isolated)", header_color=MOD_HDR_AMBER)

    # Power & Modbus Terminals
    draw_term(ax, 12, 140, "MODBUS TCP RJ45", "IP: 10.0.0.10:502 / ID: 255", color=W_ETH, bg='#EFF6FF', width=62)
    draw_term(ax, 78, 140, "POWER (+24V, 0V, S/S)", "S/S tied to 0V (PNP Mode)", color=W_24V, bg='#FFF7ED', width=62)

    # Table of 11 Digital Inputs
    ax.text(12, 134, "DIGITAL INPUTS (DI0 - DI10) — 24VDC OPTO-ISOLATED:", fontsize=7.8, fontweight='bold', color=MOD_HDR_AMBER)
    
    di_table = [
        ("DI0", "x_head_limit", "X Min Limit / Home Sensor", "Normally Closed (NC)", "Inductive Proximity", W_SIG),
        ("DI1", "x_tail_limit", "X Max Limit Sensor", "Normally Closed (NC)", "Inductive Proximity", W_SIG),
        ("DI2", "y_head_limit", "Y Min Limit / Drop Level", "Normally Closed (NC)", "Inductive Proximity", W_SIG),
        ("DI3", "y_tail_limit", "Y Max Limit / Top Level", "Normally Closed (NC)", "Inductive Proximity", W_SIG),
        ("DI4", "z_head_limit", "Z Min Limit / Retract End", "Normally Closed (NC)", "Inductive Proximity", W_SIG),
        ("DI5", "z_tail_limit", "Z Max Limit / Extend End", "Normally Closed (NC)", "Inductive Proximity", W_SIG),
        ("DI6", "z_home", "Z Home Reference Sensor", "Normally Open (NO)", "Inductive Proximity", W_SIG),
        ("DI7", "product_drop_parking", "Drop Alignment Proximity", "Normally Open (NO)", "Inductive Proximity", W_SIG),
        ("DI8", "product_drop_sensor", "Completed Drop Sensor", "Beam Interrupted", "Omron E3Z-D81 Optical", W_ALM),
        ("DI9", "product_pickup_sensor", "Door Access Pickup Sensor", "Door Flap Opened", "Omron E3Z-D81 Optical", W_ALM),
        ("DI10", "estop / KM1_FEEDBACK", "Safety Contactor Aux NC", "Fail-Safe NC Loop", "KM1 Contactor Aux", W_ALM),
    ]

    y_di = 125
    for ch, name, func, logic, stype, col in di_table:
        draw_term(ax, 12, y_di, f"{ch}: {name}", func, color=col, bg='#FFFFFF', width=80)
        draw_term(ax, 96, y_di, logic, stype, color=TEXT_MAIN, bg=TERM_BG_EVEN, width=44)
        y_di -= 5.2

    # Table of 4 Digital Outputs
    ax.text(12, 64, "DIGITAL OUTPUTS (DO0 - DO3) — 24VDC SSR / RELAYS:", fontsize=7.8, fontweight='bold', color=MOD_HDR_AMBER)
    do_table = [
        ("DO0", "ready", "Green Pilot Light", "Machine Ready Indication", W_PE, '#F0FDF4'),
        ("DO1", "moving", "Yellow Pilot Light", "Carriage Moving Indication", W_DIR, '#FFFBEB'),
        ("DO2", "alarm", "Red Light & Audible Buzzer", "Fault / Emergency Indication", W_ALM, '#FEF2F2'),
        ("DO3", "dispense", "Solenoid Drop Gate Relay", "Timed Pulse 500ms Trigger", W_ETH, '#EFF6FF'),
    ]

    y_do = 55
    for ch, name, load, desc, col, bg in do_table:
        draw_term(ax, 12, y_do, f"{ch}: {name}", load, color=col, bg=bg, width=62)
        draw_term(ax, 78, y_do, desc, "24V / 0.5A SSR", color=TEXT_MAIN, bg='#FFFFFF', width=62)
        y_do -= 5.5

    # Right Side: Sensor Wiring Diagrams & Safety Hold Points
    draw_module(ax, 150, 14, 122, 144, "FIELD SENSOR WIRING SCHEMATICS & SAFETY LOGIC", 
                "Inductive Proximity, Optical Sensors, and Safety Relay Loops", header_color=MOD_HDR_SLATE)

    # Sub-card 1: 3-Wire Inductive Proximity Sensors
    draw_module(ax, 154, 98, 114, 54, "3-WIRE INDUCTIVE PROXIMITY SENSORS (PNP NO/NC)", 
                "Connection Diagram for Limit Sensors X, Y, Z (DI0 - DI7)", header_color=MOD_HDR_NAVY)
    
    # Sensor Diagram Box
    ax.add_patch(patches.Rectangle((158, 102), 34, 38, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(175, 134, "INDUCTIVE\nSENSOR\n(PNP)", fontsize=7.2, fontweight='bold', color=BORDER_MAIN, ha='center', va='center')
    ax.text(175, 112, "Shield Grounded\nat Cabinet PE", fontsize=6.5, color=W_PE, ha='center', va='center')

    # Terminals & Wire Colors
    draw_term(ax, 196, 134, "BROWN (BN)", "+24VDC Power (From PSU 2 Rail)", color=W_24V, bg='#FFF7ED', width=68)
    draw_term(ax, 196, 126, "BLUE (BU)", "0VDC / COM Return (From PSU 2 Rail)", color=W_GND, bg=TERM_BG_EVEN, width=68)
    draw_term(ax, 196, 118, "BLACK (BK)", "Signal Output -> IRiV IO (DI0 - DI7)", color=W_SIG, bg='#F0FDFA', width=68)
    draw_term(ax, 196, 106, "S/S TERMINAL", "Must be jumpered to 0V for PNP inputs", color=TEXT_MAIN, bg='#FFFFFF', width=68)

    # Sub-card 2: Omron Photoelectric Sensors (E3Z-D81)
    draw_module(ax, 154, 52, 114, 42, "OMRON E3Z-D81 PHOTOELECTRIC SENSORS", 
                "Connection Diagram for Drop (DI8) & Pickup (DI9) Verification", header_color=MOD_HDR_NAVY)
    draw_term(ax, 158, 77, "BROWN (BN)", "+24VDC Supply Rail", color=W_24V, bg='#FFF7ED', width=52)
    draw_term(ax, 214, 77, "BLUE (BU)", "0VDC Power Return", color=W_GND, bg=TERM_BG_EVEN, width=50)
    draw_term(ax, 158, 69, "BLACK (BK)", "Output -> DI8 (Drop Beam)", color=W_ALM, bg='#FEF2F2', width=52)
    draw_term(ax, 214, 69, "WHITE (WH)", "Output -> DI9 (Pickup Flap)", color=W_ALM, bg='#FEF2F2', width=50)
    draw_term(ax, 158, 59, "SENSITIVITY", "Single-turn trimmer adjust for beam distance", color=TEXT_MUTED, bg='#FFFFFF', width=106)

    # Sub-card 3: Safety Interlock Rules
    draw_module(ax, 154, 18, 114, 30, "CRITICAL SAFETY HOLD POINTS & INVARIANTS", 
                "Hardware Interlocks that MUST be verified before operation", header_color=MOD_HDR_RED)
    ax.text(157, 39, "1. FAIL-SAFE NC LIMIT CONFIGURATION:", fontsize=6.8, fontweight='bold', color=MOD_HDR_RED)
    ax.text(157, 35.5, "Limit sensors DI0-DI5 use Normally Closed contacts. A broken cable trips E-Stop instantly.", fontsize=6.5, color=TEXT_MAIN)
    ax.text(157, 31, "2. DI10 POLARITY VERIFICATION (E-STOP LOOP):", fontsize=6.8, fontweight='bold', color=MOD_HDR_RED)
    ax.text(157, 27.5, "DI10 active LOW (NC loop). Software blocks motion if contactor drops or loop opens.", fontsize=6.5, color=W_ALM)
    ax.text(157, 23, "3. MODBUS TIMEOUT GUARD: Controller disarms all axes if poll response stale > 350ms.", fontsize=6.5, color=TEXT_MAIN)

    return fig

# =============================================================================
# SHEET 5: SECTION 4 — MOTION CO-PROCESSOR (STM32) & 6-CH NMOS SINK BOARD
# =============================================================================
def generate_sheet_5():
    fig, ax = create_base_canvas(5, 6, "Section 4: Motion Co-Processor (STM32) & NMOS Level Shifter", "Motion Co-Processor")

    # Left Side: STM32 NUCLEO-G491RE Box
    draw_module(ax, 8, 14, 134, 144, "STM32 NUCLEO-G491RE MOTION CO-PROCESSOR", 
                "ARM Cortex-M4 @ 170MHz (Hardware Timer Output Compare Pulse Engine)", header_color=MOD_HDR_NAVY)

    # ST-LINK USB Port
    draw_term(ax, 12, 140, "ST-LINK V3 USB (VCP)", "LPUART1 PA2/PA3 @ 115200 8-N-1", color=W_ALM, bg='#FEF2F2', width=62)
    draw_term(ax, 78, 140, "PROTOCOL: SAFE-LINK v3", "Binary Frame with CRC & Watchdog", color=MOD_HDR_NAVY, bg='#EFF6FF', width=60)

    # Detailed Morpho Pin Mapping
    ax.text(12, 134, "HARDWARE TIMER & GPIO PIN MAPPING (NUCLEO-64 MORPHO & ARDUINO HEADERS):", fontsize=7.5, fontweight='bold', color=MOD_HDR_NAVY)
    
    mcu_pins = [
        ("X_STEP", "PA8", "TIM1_CH1 (AF6)", "Morpho CN10 pin 23", "Arduino D7", W_STEP, '#EFF6FF'),
        ("X_DIR",  "PB0", "GPIO Output",    "Morpho CN7 pin 34",  "Arduino A3", W_DIR,  '#FFFBEB'),
        ("Y_STEP", "PA9", "TIM1_CH2 (AF6)", "Morpho CN10 pin 21", "Arduino D8", W_STEP, '#EFF6FF'),
        ("Y_DIR",  "PB1", "GPIO Output",    "Morpho CN10 pin 24", "(No Arduino)", W_DIR, '#FFFBEB'),
        ("Z_STEP", "PA5", "TIM2_CH1 (AF1)", "Morpho CN10 pin 11", "Arduino D13", W_STEP, '#EFF6FF'),
        ("Z_DIR",  "PB2", "GPIO Output",    "Morpho CN10 pin 22", "(No Arduino)", W_DIR, '#FFFBEB'),
        ("MCU_GND","GND", "Reference 0V",   "Morpho CN10 pin 20", "CN7 pin 20", W_GND,  TERM_BG_EVEN),
    ]

    y_p = 125
    for sig, pin, af, morpho, ard, col, bg in mcu_pins:
        draw_term(ax, 12, y_p, sig, f"{pin} ({af})", color=col, bg=bg, width=54)
        draw_term(ax, 70, y_p, morpho, ard, color=TEXT_MAIN, bg='#FFFFFF', width=68)
        y_p -= 5.5

    # CRITICAL PIN MISWIRING WARNING CARD (Below Pins)
    ax.add_patch(patches.Rectangle((12, 48), 126, 36, facecolor='#FEF2F2', edgecolor=W_ALM, linewidth=1.0))
    ax.text(15, 78, "CRITICAL PIN MISWIRING WARNINGS (DO NOT USE OLD NUCLEO-144 PINS):", fontsize=7.2, fontweight='bold', color=W_ALM)
    ax.text(15, 74, "1. X_DIR (PB0): DO NOT plug into CN10-31! On Nucleo-64 that pin is PB3. Connect to CN7 pin 34.", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 69.5, "2. Y_DIR (PB1): DO NOT plug into CN10-7! On Nucleo-64 that is AVDD 3.3V power (locks DIR HIGH). Connect to CN10 pin 24.", fontsize=6.8, color=W_ALM, fontweight='bold')
    ax.text(15, 65, "3. Z_DIR (PB2): DO NOT plug into CN10-15! On Nucleo-64 that is PA7. Connect to CN10 pin 22.", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 60.5, "4. GROUND: DO NOT connect GND to CN10-5, 17, 27! Those are GPIO pins. Use ONLY CN10 pin 20 or CN10 pin 9.", fontsize=6.8, color=W_ALM, fontweight='bold')
    ax.text(15, 56, "5. Z_STEP (PA5) CONFLICT: PA5 shares user LED LD2. Firmware MUST have all LED blink code disabled.", fontsize=6.8, color=W_ALM)
    ax.text(15, 51, "Failure to follow this mapping will cause false motion steps, frozen direction, or damaged MCU pins.", fontsize=6.5, color=TEXT_MUTED)

    # Firmware Safety Limits Card
    ax.add_patch(patches.Rectangle((12, 18), 126, 26, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(15, 38.5, "FIRMWARE OPERATIONAL SAFETY LIMITS:", fontsize=7.2, fontweight='bold', color=MOD_HDR_NAVY)
    ax.text(15, 34.5, "• Boot Invariant: Starts DISARMED, timers stopped, STEP & DIR lines held LOW.", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 30.5, "• Frequency Range: Hardware Timer output compare clamped strictly between 10 Hz and 50,000 Hz.", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 26.5, "• Block Batch Limit: Maximum 1,000,000 steps per block command.", fontsize=6.8, color=TEXT_MAIN)
    ax.text(15, 22.5, "• Axis Mutual Exclusion: Only 1 motion axis actively steps at any given moment.", fontsize=6.8, color=TEXT_MAIN)

    # Right Side: 6-Channel NMOS Open-Drain Level Shifter Board
    draw_module(ax, 148, 14, 124, 144, "6-CHANNEL LOGIC-LEVEL NMOS SINK BOARD", 
                "Open-Drain Level Translation (3.3V MCU Logic -> 24V Optocoupler Sink)", header_color=MOD_HDR_SLATE)

    # Circuit Schematic Graphic
    ax.add_patch(patches.Rectangle((152, 102), 116, 48, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(155, 144, "OPTOCOUPLER DRIVE CIRCUIT TOPOLOGY (PER CHANNEL):", fontsize=7.5, fontweight='bold', color=MOD_HDR_NAVY)
    
    # Textual schematic
    ax.text(155, 137, "+24VDC (V-PULSE Bus) --------------------------+--> Driver PUL+ / DIR+ (Anode)", fontsize=6.8, color=W_24V, fontweight='bold')
    ax.text(155, 131, "                                               |    (Internal Optocoupler LED)", fontsize=6.5, color=TEXT_MUTED)
    ax.text(155, 125, "STM32 GPIO ----[ 100 Ohm ]---+--- Gate (Qn)     +--> Driver PUL- / DIR- (Cathode)", fontsize=6.8, color=BORDER_MAIN)
    ax.text(155, 119, "                           |                   ^", fontsize=6.8, color=TEXT_MUTED)
    ax.text(155, 113, "                       [ 10k Ohm ]        Drain (Qn)", fontsize=6.8, color=TEXT_MUTED)
    ax.text(155, 107, "                           |                   |", fontsize=6.8, color=TEXT_MUTED)
    ax.text(155, 103, "MCU GND -------------------+--------------- Source (Qn) ---> Field 0VDC / 0V-SIGNAL", fontsize=6.8, color=W_GND, fontweight='bold')

    # Channel Assignments Table
    ax.text(152, 96, "6-CHANNEL NMOS PIN ASSIGNMENTS:", fontsize=7.5, fontweight='bold', color=MOD_HDR_NAVY)
    
    nmos_channels = [
        ("CH 1: X_PULSE", "Gate: STM32 PA8 (CN10-23)", "Drain -> Driver X PUL-", W_STEP, '#EFF6FF'),
        ("CH 2: X_DIR",   "Gate: STM32 PB0 (CN7-34)",  "Drain -> Driver X DIR-", W_DIR,  '#FFFBEB'),
        ("CH 3: Y_PULSE", "Gate: STM32 PA9 (CN10-21)", "Drain -> Driver Y PUL-", W_STEP, '#EFF6FF'),
        ("CH 4: Y_DIR",   "Gate: STM32 PB1 (CN10-24)", "Drain -> Driver Y DIR-", W_DIR,  '#FFFBEB'),
        ("CH 5: Z_PULSE", "Gate: STM32 PA5 (CN10-11)", "Drain -> Driver Z PUL-", W_STEP, '#EFF6FF'),
        ("CH 6: Z_DIR",   "Gate: STM32 PB2 (CN10-22)", "Drain -> Driver Z DIR-", W_DIR,  '#FFFBEB'),
    ]

    y_n = 87
    for ch, g, d, col, bg in nmos_channels:
        draw_term(ax, 152, y_n, ch, g, color=col, bg=bg, width=62)
        draw_term(ax, 218, y_n, d, "Low-Side Sink", color=TEXT_MAIN, bg='#FFFFFF', width=50)
        y_n -= 5.5

    # Power Rails & Common Anode Terminals
    draw_term(ax, 152, 48, "V-PULSE BUS (+24VDC)", "Common Anode Rail to all PUL+ & DIR+", color=W_24V, bg='#FFF7ED', width=116)
    draw_term(ax, 152, 42, "0V-SIGNAL / COMMON GND", "Tied to all NMOS Sources, MCU GND, and PSU 2 0V", color=W_GND, bg=TERM_BG_EVEN, width=116)

    # Component Specifications Card
    ax.add_patch(patches.Rectangle((152, 18), 116, 21, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.8))
    ax.text(155, 34, "COMPONENT SPECIFICATIONS & ENGINEERING NOTES:", fontsize=7.0, fontweight='bold', color=BORDER_MAIN)
    ax.text(155, 29.5, "• MOSFET: Logic-Level N-Channel (2N7002 / AO3400 / IRF520 / BSS138), Vds >= 50V, Vgs(th) <= 2.0V.", fontsize=6.5, color=TEXT_MAIN)
    ax.text(155, 25.5, "• Gate Resistor: 100-Ohm series damping resistor prevents ringing on high-frequency edges.", fontsize=6.5, color=TEXT_MAIN)
    ax.text(155, 21.5, "• Pulldown Resistor: 10k-Ohm pulldown guarantees off-state when MCU pins are in reset/tri-state.", fontsize=6.5, color=TEXT_MUTED)

    return fig

# =============================================================================
# SHEET 6: SECTION 5 — STEPPER MOTOR DRIVERS & ACTUATORS WIRING
# =============================================================================
def generate_sheet_6():
    fig, ax = create_base_canvas(6, 6, "Section 5: Stepper Motor Drivers & Actuators Wiring (Axes X, Y, Z)", "Drives & Actuators")

    # Left Column: Driver X (HBS860H) & Motor X (86HBS85)
    draw_module(ax, 8, 14, 88, 144, "AXIS X: HORIZONTAL CARRIAGE DRIVE", 
                "Leadshine HBS860H Closed-Loop Driver + 86HBS85 NEMA 34 Motor", header_color=MOD_HDR_SLATE)

    # Driver X Block
    draw_module(ax, 12, 78, 80, 74, "DRIVER X: HBS860H (CLOSED-LOOP)", "Peak 8.2A, Continuous 5.6A, Microstep 1600", header_color=MOD_HDR_SLATE)
    draw_term(ax, 14, 137, "AC / AC (V+ / V-)", "+60VDC & 0V from KM1 Contactor", color=W_60V, bg='#FEF2F2', width=76)
    draw_term(ax, 14, 131, "PUL+ (V-PULSE)", "+24VDC Common Anode Bus", color=W_24V, bg='#FFF7ED', width=36)
    draw_term(ax, 52, 131, "PUL- (STEP)", "From NMOS Ch1 (PA8)", color=W_STEP, bg='#EFF6FF', width=38)
    draw_term(ax, 14, 125, "DIR+ (V-PULSE)", "+24VDC Common Anode Bus", color=W_24V, bg='#FFF7ED', width=36)
    draw_term(ax, 52, 125, "DIR- (DIR)", "From NMOS Ch2 (PB0)", color=W_DIR, bg='#FFFBEB', width=38)
    draw_term(ax, 14, 119, "ALM+ / ALM-", "Alarm Opto -> PiControl DI0", color=W_ALM, bg='#FEF2F2', width=36)
    draw_term(ax, 52, 119, "PEND+ / PEND-", "In-Pos Opto -> PiControl DI2", color=W_DIR, bg='#FFFBEB', width=38)
    draw_term(ax, 14, 112, "COIL A+ / A-", "Phase A (Red / Blue)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=36)
    draw_term(ax, 52, 112, "COIL B+ / B-", "Phase B (Black / Green)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=38)
    draw_term(ax, 14, 106, "EA+ / EA-", "Channel A Differential", color=W_ETH, bg='#EFF6FF', width=36)
    draw_term(ax, 52, 106, "EB+ / EB-", "Channel B Differential", color=W_ETH, bg='#EFF6FF', width=38)
    draw_term(ax, 14, 100, "VCC / EGND", "Enc Power (+5V Red / 0V Wht)", color=W_5V, bg='#FAF5FF', width=76)
    draw_term(ax, 14, 94, "DIP SW1-SW4", "Current: SW1-SW4 = ON, ON, ON, ON (Peak 8.2A)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=76)
    draw_term(ax, 14, 88, "DIP SW5-SW8", "Microstep: SW5-SW8 = ON, OFF, ON, ON (1600 steps/rev)", color=BORDER_MAIN, bg='#EFF6FF', width=76)
    ax.text(14, 82, "RS232 Tuning Port: ProTuner parameter configuration interface", fontsize=6.5, color=TEXT_MUTED)

    # Motor X Block
    draw_module(ax, 12, 18, 80, 56, "MOTOR X: 86HBS85 (NEMA 34)", "8.5 N.m Closed-Loop Stepper + 1000 CPR Encoder", header_color=MOD_HDR_TEAL)
    draw_term(ax, 14, 59, "COIL LEADS (4-PIN)", "Red: A+ | Blu: A- | Blk: B+ | Grn: B-", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=76)
    draw_term(ax, 14, 53, "ENCODER (6-PIN)", "EA+, EA-, EB+, EB-, VCC(+5V), EGND(0V)", color=W_ETH, bg='#EFF6FF', width=76)
    draw_term(ax, 14, 46, "SHAFT & TRANSMISSION", "14mm Keyed Shaft -> HTD 5M 25mm Timing Belt", color=BORDER_MAIN, bg='#FFFFFF', width=76)
    draw_term(ax, 14, 40, "KINEMATIC RATIO", "78.43 steps/mm @ 1600 microstep (Pitch Dia 63.66mm)", color=BORDER_MAIN, bg='#FFFFFF', width=76)
    draw_term(ax, 14, 34, "TRAVERSE PERFORMANCE", "Rapid: 450 mm/s | Accel: 800 mm/s² | Dual HGR20 Guides", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=76)
    ax.text(14, 24, "Closed-loop feedback eliminates stalling. Trips ALM on > 1000 count lag.", fontsize=6.5, color=W_ALM)

    # Middle Column: Driver Y (HBS860H) & Motor Y (86HBS85 Elevator)
    draw_module(ax, 100, 14, 88, 144, "AXIS Y: VERTICAL ELEVATOR DRIVE", 
                "Leadshine HBS860H Closed-Loop Driver + 86HBS85 NEMA 34 Motor", header_color=MOD_HDR_SLATE)

    # Driver Y Block
    draw_module(ax, 104, 78, 80, 74, "DRIVER Y: HBS860H (CLOSED-LOOP)", "Peak 8.2A, Continuous 5.6A, Microstep 1600", header_color=MOD_HDR_SLATE)
    draw_term(ax, 106, 137, "AC / AC (V+ / V-)", "+60VDC & 0V from KM1 Contactor", color=W_60V, bg='#FEF2F2', width=76)
    draw_term(ax, 106, 131, "PUL+ (V-PULSE)", "+24VDC Common Anode Bus", color=W_24V, bg='#FFF7ED', width=36)
    draw_term(ax, 144, 131, "PUL- (STEP)", "From NMOS Ch3 (PA9)", color=W_STEP, bg='#EFF6FF', width=38)
    draw_term(ax, 106, 125, "DIR+ (V-PULSE)", "+24VDC Common Anode Bus", color=W_24V, bg='#FFF7ED', width=36)
    draw_term(ax, 144, 125, "DIR- (DIR)", "From NMOS Ch4 (PB1)", color=W_DIR, bg='#FFFBEB', width=38)
    draw_term(ax, 106, 119, "ALM+ / ALM-", "Alarm Opto -> PiControl DI1", color=W_ALM, bg='#FEF2F2', width=36)
    draw_term(ax, 144, 119, "PEND+ / PEND-", "In-Pos Opto -> PiControl DI3", color=W_DIR, bg='#FFFBEB', width=38)
    draw_term(ax, 106, 112, "COIL A+ / A-", "Phase A (Red / Blue)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=36)
    draw_term(ax, 144, 112, "COIL B+ / B-", "Phase B (Black / Green)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=38)
    draw_term(ax, 106, 106, "EA+ / EA-", "Channel A Differential", color=W_ETH, bg='#EFF6FF', width=36)
    draw_term(ax, 144, 106, "EB+ / EB-", "Channel B Differential", color=W_ETH, bg='#EFF6FF', width=36)
    draw_term(ax, 106, 100, "VCC / EGND", "Enc Power (+5V Red / 0V Wht)", color=W_5V, bg='#FAF5FF', width=76)
    draw_term(ax, 106, 94, "DIP SW1-SW4", "Current: SW1-SW4 = ON, ON, ON, ON (Peak 8.2A)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=76)
    draw_term(ax, 106, 88, "DIP SW5-SW8", "Microstep: SW5-SW8 = ON, OFF, ON, ON (1600 steps/rev)", color=BORDER_MAIN, bg='#EFF6FF', width=76)
    ax.text(106, 82, "Elevator Holding: Holding current maintains vertical level under load", fontsize=6.5, color=TEXT_MUTED)

    # Motor Y Block
    draw_module(ax, 104, 18, 80, 56, "MOTOR Y: 86HBS85 (NEMA 34)", "8.5 N.m Closed-Loop Stepper + SFU1605 Ball Screw", header_color=MOD_HDR_TEAL)
    draw_term(ax, 106, 59, "COIL LEADS (4-PIN)", "Red: A+ | Blu: A- | Blk: B+ | Grn: B-", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=76)
    draw_term(ax, 106, 53, "ENCODER (6-PIN)", "EA+, EA-, EB+, EB-, VCC(+5V), EGND(0V)", color=W_ETH, bg='#EFF6FF', width=76)
    draw_term(ax, 106, 46, "SHAFT & TRANSMISSION", "14mm Shaft -> Direct Flexible Coupling to SFU1605", color=BORDER_MAIN, bg='#FFFFFF', width=76)
    draw_term(ax, 106, 40, "KINEMATIC RATIO", "320.00 steps/mm @ 1600 microstep (Ball Screw Lead 5mm)", color=BORDER_MAIN, bg='#FFFFFF', width=76)
    draw_term(ax, 106, 34, "ELEVATOR PERFORMANCE", "Speed: 120 mm/s | Accel: 600 mm/s² | Direct Lift Carriage", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=76)
    ax.text(106, 24, "Lifts Dispensing Basket to target product shelf slots (Levels 1 to 5).", fontsize=6.5, color=BORDER_MAIN)

    # Right Column: Driver Z (DM542) & Motor Z (NEMA 17 Pusher)
    draw_module(ax, 192, 14, 80, 144, "AXIS Z: DISPENSER PUSHER DRIVE", 
                "Leadshine DM542 Driver + NEMA 17 V-Slot Mini Actuator", header_color=MOD_HDR_SLATE)

    # Driver Z Block
    draw_module(ax, 196, 78, 72, 74, "DRIVER Z: DM542 (MICROSTEPPING)", "Peak 4.2A, 20-50VDC Supply", header_color=MOD_HDR_SLATE)
    draw_term(ax, 198, 137, "V+ / GND (24-48V)", "+24VDC & 0V from PSU 2 Control Rail", color=W_24V, bg='#FFF7ED', width=68)
    draw_term(ax, 198, 131, "PUL+ (V-PULSE)", "+24VDC Common Anode Bus", color=W_24V, bg='#FFF7ED', width=32)
    draw_term(ax, 232, 131, "PUL- (STEP)", "NMOS Ch5 (PA5)", color=W_STEP, bg='#EFF6FF', width=34)
    draw_term(ax, 198, 125, "DIR+ (V-PULSE)", "+24VDC Common Anode Bus", color=W_24V, bg='#FFF7ED', width=32)
    draw_term(ax, 232, 125, "DIR- (DIR)", "NMOS Ch6 (PB2)", color=W_DIR, bg='#FFFBEB', width=34)
    draw_term(ax, 198, 118, "ENA+ / ENA-", "Enable Input (Not connected / enabled)", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=68)
    draw_term(ax, 198, 111, "COIL A+ / A-", "Phase A Motor (Red / Blue)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=32)
    draw_term(ax, 232, 111, "COIL B+ / B-", "Phase B (Black / Green)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=34)
    draw_term(ax, 198, 103, "DIP SW1-SW4", "Current: SW1=ON, SW2=OFF, SW3=ON, SW4=OFF (Peak 2.0A)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=68)
    draw_term(ax, 198, 97, "DIP SW5-SW8", "Microstep: SW5=ON, SW6=OFF, SW7=ON, SW8=ON (1600 step/rev)", color=BORDER_MAIN, bg='#EFF6FF', width=68)
    ax.text(198, 90, "Safety Recommendation: Route 24V supply through KM1", fontsize=6.5, color=W_ALM, fontweight='bold')
    ax.text(198, 83, "contactor to prevent unmonitored plunger motion during E-Stop.", fontsize=6.2, color=W_ALM)

    # Motor Z Block
    draw_module(ax, 196, 18, 72, 56, "MOTOR Z: NEMA 17 PUSHER", "V-Slot Lead Screw Mini Actuator (150mm Stroke)", header_color=MOD_HDR_TEAL)
    draw_term(ax, 198, 59, "COIL LEADS (4-PIN)", "Red: A+ | Blu: A- | Blk: B+ | Grn: B-", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=68)
    draw_term(ax, 198, 53, "ACTUATOR TYPE", "T8x8 Lead Screw (Pitch 2mm, 4 Starts = 8mm/rev)", color=BORDER_MAIN, bg='#FFFFFF', width=68)
    draw_term(ax, 198, 46, "KINEMATIC RATIO", "200.00 steps/mm @ 1600 microstep (Lead 8.0mm/rev)", color=BORDER_MAIN, bg='#FFFFFF', width=68)
    draw_term(ax, 198, 40, "STROKE & TRAVEL", "Stroke: 150mm | Plunger pushes items onto basket tray", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=68)
    draw_term(ax, 198, 34, "INTERLOCK RULE", "Must confirm Z_MIN (Retracted) before X/Y move", color=W_ALM, bg='#FEF2F2', width=68)
    ax.text(198, 24, "Hardware interlock prevents carriage collision while pusher is extended.", fontsize=6.5, color=MOD_HDR_RED)

    return fig

# =============================================================================
# MAIN EXPORT ROUTINE
# =============================================================================
def generate_all():
    base_dir = r"D:\37-Project Narit Vending Machine\Document\NaritVending"
    doc_dir  = r"D:\37-Project Narit Vending Machine\Document"
    sec_dir  = os.path.join(base_dir, "docs", "wiring_sections")
    doc_sec  = os.path.join(doc_dir, "wiring_sections")
    
    os.makedirs(sec_dir, exist_ok=True)
    os.makedirs(doc_sec, exist_ok=True)

    pdf_path_base = os.path.join(base_dir, "narit_vending_wiring_diagram_sections.pdf")
    pdf_path_docs = os.path.join(base_dir, "docs", "narit_vending_wiring_diagram_sections.pdf")
    pdf_path_main = os.path.join(doc_dir, "narit_vending_wiring_diagram_sections.pdf")

    sheets = [
        ("sheet1_system_overview", generate_sheet_1),
        ("sheet2_power_distribution", generate_sheet_2),
        ("sheet3_main_controller_picontrol", generate_sheet_3),
        ("sheet4_field_io_sensors", generate_sheet_4),
        ("sheet5_stm32_nmos_pulse", generate_sheet_5),
        ("sheet6_motor_drivers_actuators", generate_sheet_6),
    ]

    print("Generating Multi-Page PDF and standalone PNG sheets...")
    
    # Generate Multi-Page PDF
    with PdfPages(pdf_path_base) as pdf:
        for name, gen_fn in sheets:
            print(f"  Rendering {name}...")
            fig = gen_fn()
            
            # Save into PDF
            pdf.savefig(fig, bbox_inches='tight', facecolor=BG_CANVAS)
            
            # Save individual PNG
            png_base = os.path.join(sec_dir, f"{name}.png")
            png_doc  = os.path.join(doc_sec, f"{name}.png")
            fig.savefig(png_base, dpi=150, bbox_inches='tight', facecolor=BG_CANVAS)
            fig.savefig(png_doc, dpi=150, bbox_inches='tight', facecolor=BG_CANVAS)
            
            plt.close(fig)

    # Copy PDF to target folders
    import shutil
    shutil.copyfile(pdf_path_base, pdf_path_docs)
    shutil.copyfile(pdf_path_base, pdf_path_main)

    print("Multi-Section Electrical Drawing Package generated successfully!")
    print(f"  -> PDF: {pdf_path_main}")
    print(f"  -> PNGs: {doc_sec}")

if __name__ == "__main__":
    generate_all()
