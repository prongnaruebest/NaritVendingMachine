# -*- coding: utf-8 -*-
"""
NARIT Vending Machine — Publication-Grade Electrical Schematic & Wiring Diagram Generator
Compliant with ISO 7200 / IEC 60617 / IEC 60204-1 Engineering Drawing Standards.
Features formal industrial CAD palette, exact pinouts, terminal references, and wireway routing.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os

def generate_diagram(output_path, is_pdf=False):
    # Professional typography setup
    plt.rcParams['font.sans-serif'] = ['Leelawadee UI', 'Tahoma', 'Segoe UI', 'DejaVu Sans', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    # Drawing Canvas: 380 x 250 units (Ratio ~ 1.52, standard A1 / D-size landscape)
    dpi = 300 if not is_pdf else 150
    fig = plt.figure(figsize=(38, 25), dpi=150)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 380)
    ax.set_ylim(0, 250)
    ax.axis('off')

    # =========================================================================
    # FORMAL INDUSTRIAL CAD COLOR PALETTE (IEC 60204-1 / IEC 60446 Standards)
    # =========================================================================
    BG_CANVAS    = '#FFFFFF'   # Crisp Engineering White
    BORDER_MAIN  = '#0F2744'   # Deep Navy Technical Slate
    BORDER_SUB   = '#64748B'   # Technical Gray
    GRID_TEXT    = '#64748B'   # Grid Reference Coordinates
    
    # Module Framing
    MOD_HDR_NAVY = '#0F2744'   # Primary Controller / Power (Deep Navy)
    MOD_HDR_SLATE= '#1E293B'   # Secondary / Motor Drives (Slate Charcoal)
    MOD_HDR_TEAL = '#064E3B'   # Field Actuators & Motors (Deep Forest / Teal)
    MOD_HDR_AMBER= '#78350F'   # I/O & Sensor Interface (Deep Ochre / Bronze)
    MOD_HDR_RED  = '#7F1D1D'   # Safety Interlock / Contactor (Deep Crimson)
    
    MOD_BG_WHITE = '#FFFFFF'   # Clean white module interiors
    TERM_BG_EVEN = '#F8FAFC'   # Subtle alternate row shading
    TERM_BG_ODD  = '#FFFFFF'
    TERM_BORDER  = '#94A3B8'   # Crisp terminal borders
    TEXT_MAIN    = '#0F172A'   # Jet Black / Dark Slate for max legibility
    TEXT_MUTED   = '#475569'   # Technical Secondary Text
    TEXT_ACCENT  = '#0369A1'   # Technical Highlights
    
    # Official Standard Wire Colors (IEC 60204-1 / NFPA 79)
    W_AC_L   = '#991B1B'   # AC 220V Phase / Line (Deep Red / Brown standard)
    W_AC_N   = '#1D4ED8'   # AC Neutral (Engineering Blue)
    W_PE     = '#15803D'   # Protective Earth (Safety Green)
    W_60V    = '#7F1D1D'   # +60VDC Motor Bus (Deep Crimson)
    W_24V    = '#C2410C'   # +24VDC Control Supply (Industrial Orange-Red)
    W_GND    = '#1E293B'   # 0VDC / Signal GND / COM Return (Solid Dark Slate)
    W_5V     = '#6B21A8'   # +5VDC Logic / USB Rail (Deep Purple)
    W_STEP   = '#0284C7'   # STEP / Pulse Signals (Technical Cobalt)
    W_DIR    = '#B45309'   # DIR / Direction Signals (Technical Amber)
    W_SIG    = '#0F766E'   # Sensor Signals (Technical Teal)
    W_ALM    = '#DC2626'   # Alarm / E-Stop / Safety Loop (Signal Red)
    W_ETH    = '#1E3A8A'   # Ethernet LAN / Modbus TCP (Deep Navy Blue)
    W_USB    = '#4338CA'   # USB Peripherals (Dark Indigo)

    # -------------------------------------------------------------------------
    # Canvas Frame & Coordinate Margin Grid (Standard Drawing Sheet Border)
    # -------------------------------------------------------------------------
    ax.add_patch(patches.Rectangle((0, 0), 380, 250, facecolor=BG_CANVAS, edgecolor=BORDER_MAIN, linewidth=3))
    ax.add_patch(patches.Rectangle((4, 4), 372, 242, facecolor='none', edgecolor=BORDER_MAIN, linewidth=1.5))
    ax.add_patch(patches.Rectangle((6, 6), 368, 238, facecolor='none', edgecolor=BORDER_SUB, linewidth=0.75))

    # Grid reference marks around border (1..8 horizontally, A..F vertically)
    cols = ['1', '2', '3', '4', '5', '6', '7', '8']
    for i, c in enumerate(cols):
        gx = 6 + (368 / 8) * (i + 0.5)
        ax.text(gx, 5.0, c, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')
        ax.text(gx, 243.0, c, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')
    
    rows = ['F', 'E', 'D', 'C', 'B', 'A']
    for i, r in enumerate(rows):
        gy = 6 + (238 / 6) * (i + 0.5)
        ax.text(5.0, gy, r, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')
        ax.text(373.0, gy, r, color=GRID_TEXT, fontsize=7, ha='center', va='center', fontweight='bold')

    # =========================================================================
    # 1. TOP TITLE BLOCK (ISO 7200 FORMAL ENGINEERING HEADER)
    # =========================================================================
    ax.add_patch(patches.Rectangle((7, 231), 366, 12, facecolor=BORDER_MAIN, edgecolor='none'))
    
    # Organization and Main Title
    ax.text(12, 238.2, "สถาบันวิจัยดาราศาสตร์แห่งชาติ (องค์การมหาชน) — NATIONAL ASTRONOMICAL RESEARCH INSTITUTE OF THAILAND", 
            color='#94A3B8', fontsize=8.5, fontweight='bold', va='center')
    ax.text(12, 234.0, "PROJECT: NARIT SMART VENDING MACHINE  |  ELECTRICAL CONTROL & SCHEMATIC WIRING DIAGRAM", 
            color='white', fontsize=13, fontweight='bold', va='center')

    # Metadata Badges (Right Aligned)
    ax.text(368, 238.2, "DOCUMENT NO: NARIT-VEND-E01  |  REV: 2.4 (AS-BUILT)", 
            color='#38BDF8', fontsize=9.5, fontweight='bold', ha='right', va='center')
    ax.text(368, 234.0, "TOR: 00-TOR-Vending-J69-290  |  SYSTEM: 220VAC / 60VDC / 24VDC / 5VDC", 
            color='#E2E8F0', fontsize=8.5, ha='right', va='center')

    # =========================================================================
    # DRAWING HELPERS
    # =========================================================================
    def draw_module(x, y, w, h, title, subtitle="", header_color=MOD_HDR_SLATE, bg=MOD_BG_WHITE, border=BORDER_SUB):
        # Base container
        ax.add_patch(patches.Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=1.2))
        # Header banner
        hdr_h = 3.6
        ax.add_patch(patches.Rectangle((x, y + h - hdr_h), w, hdr_h, facecolor=header_color, edgecolor=border, linewidth=1.0))
        ax.text(x + w/2, y + h - 1.6, title, color='white', fontsize=9.2, fontweight='bold', ha='center', va='center')
        if subtitle:
            ax.text(x + w/2, y + h - 2.8, subtitle, color='#CBD5E1', fontsize=6.8, ha='center', va='center')

    def draw_terminal(x, y, text, subtext="", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=22, height=2.3, text_size=7.2):
        ax.add_patch(patches.Rectangle((x, y), width, height, facecolor=bg, edgecolor=TERM_BORDER, linewidth=0.6))
        ax.text(x + 0.8, y + height/2, text, color=color, fontsize=text_size, fontweight='bold', va='center')
        if subtext:
            ax.text(x + width - 0.8, y + height/2, subtext, color=TEXT_MUTED, fontsize=text_size*0.85, ha='right', va='center')

    def draw_wire(pts, color, style='-', lw=1.4):
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=color, linestyle=style, linewidth=lw, solid_capstyle='round')

    def draw_dot(x, y, color):
        ax.plot(x, y, marker='o', markersize=4.2, color=color, zorder=6)

    # Column Zone Titles (Formal Section Headers)
    ax.text(8, 226, "ZONE 1: AC MAINS & POWER SUPPLIES", color=BORDER_MAIN, fontsize=10.5, fontweight='bold')
    ax.text(62, 226, "ZONE 2: MAIN CONTROLLER & FIELD I/O", color=BORDER_MAIN, fontsize=10.5, fontweight='bold')
    ax.text(148, 226, "ZONE 3: MOTION CO-PROCESSOR (STM32)", color=BORDER_MAIN, fontsize=10.5, fontweight='bold')
    ax.text(230, 226, "ZONE 4: STEPPER MOTOR DRIVERS", color=BORDER_MAIN, fontsize=10.5, fontweight='bold')
    ax.text(304, 226, "ZONE 5: ACTUATORS & SENSORS", color=BORDER_MAIN, fontsize=10.5, fontweight='bold')

    # =========================================================================
    # ZONE 1: AC MAINS & POWER DISTRIBUTION (x: 8 to 48)
    # =========================================================================
    # 1.1 AC Input Terminal Block
    draw_module(8, 204, 40, 19, "AC MAINS INLET 220VAC", "1-Phase 220V 50Hz Standard IEC C14", header_color=MOD_HDR_RED)
    draw_terminal(10, 215, "L (Line)", "220VAC (Brown)", color=W_AC_L, bg='#FEF2F2', width=16)
    draw_terminal(10, 211.5, "N (Neutral)", "0VAC (Blue)", color=W_AC_N, bg='#EFF6FF', width=16)
    draw_terminal(10, 208, "PE (Earth)", "Ground Bar", color=W_PE, bg='#F0FDF4', width=16)
    ax.text(32, 212, "Power Cord\n10A 250VAC\nwith Fuse 10A", fontsize=7.0, color=TEXT_MUTED, ha='center', va='center')

    # 1.2 Main Circuit Breaker (MCB 2P)
    draw_module(8, 180, 40, 20, "MCB 2-POLE (C16)", "Main Overcurrent Breaker 16A", header_color=MOD_HDR_SLATE)
    draw_terminal(10, 192.5, "IN 1 (L_in)", "Line In", color=W_AC_L, bg='#FEF2F2', width=16)
    draw_terminal(10, 189, "IN 3 (N_in)", "Neutral In", color=W_AC_N, bg='#EFF6FF', width=16)
    draw_terminal(10, 185, "OUT 2 (L_out)", "Line Out", color=W_AC_L, bg='#FEF2F2', width=16)
    draw_terminal(10, 181.5, "OUT 4 (N_out)", "Neutral Out", color=W_AC_N, bg='#EFF6FF', width=16)
    ax.text(32, 186.5, "Thermal-Magnetic\nTrip Curve C\nIcu = 6kA", fontsize=7.0, color=TEXT_MUTED, ha='center', va='center')

    # 1.3 EMI Power Line Filter
    draw_module(8, 156, 40, 20, "EMI NOISE FILTER", "CW4L2-20A-S High Attenuation", header_color=MOD_HDR_SLATE)
    draw_terminal(10, 168.5, "LINE (L)", "Filter In", color=W_AC_L, bg='#FEF2F2', width=16)
    draw_terminal(10, 165, "NEUT (N)", "Filter In", color=W_AC_N, bg='#EFF6FF', width=16)
    draw_terminal(10, 161, "LOAD (L')", "Filtered L", color=W_AC_L, bg='#FEF2F2', width=16)
    draw_terminal(10, 157.5, "LOAD (N')", "Filtered N", color=W_AC_N, bg='#EFF6FF', width=16)
    draw_terminal(28, 161, "FG / EARTH", "Chassis Earth", color=W_PE, bg='#F0FDF4', width=18)

    # 1.4 Surge Protective Device (SPD)
    draw_module(8, 133, 40, 19, "SURGE ARRESTER (SPD)", "Type 2 Arrester Uc 275V Imax 20kA", header_color=MOD_HDR_SLATE)
    draw_terminal(10, 144.5, "L (Phase)", "To L Rail", color=W_AC_L, bg='#FEF2F2', width=16)
    draw_terminal(10, 141, "N (Neutral)", "To N Rail", color=W_AC_N, bg='#EFF6FF', width=16)
    draw_terminal(10, 137.5, "PE (Earth)", "Ground Bus", color=W_PE, bg='#F0FDF4', width=16)
    ax.text(32, 141, "Status Window\nGreen = OK\nRed = Replace", fontsize=6.8, color=W_PE, ha='center', va='center', fontweight='bold')

    # 1.5 AC Distribution Bus (Terminal Blocks)
    draw_module(8, 108, 40, 21, "AC POWER BUS (DIN RAIL)", "Terminal Blocks 1-in 4-out", header_color=MOD_HDR_NAVY)
    draw_terminal(10, 120.5, "TB-L BUS", "220VAC Live", color=W_AC_L, bg='#FEF2F2', width=16)
    draw_terminal(10, 117, "TB-N BUS", "Neutral Rail", color=W_AC_N, bg='#EFF6FF', width=16)
    draw_terminal(10, 113.5, "TB-PE BUS", "Earth Rail", color=W_PE, bg='#F0FDF4', width=16)
    ax.text(32, 117, "Feeds 3 DC Power\nSupplies (Parallel\nBranch Circuit)", fontsize=6.8, color=TEXT_MAIN, ha='center', va='center')

    # 1.6 PSU 1: 60VDC 6.7A (400W)
    draw_module(8, 77, 40, 27, "PSU 1: 60VDC 6.7A (400W)", "Motor Drive Power Supply (X & Y Axis)", header_color=MOD_HDR_RED)
    draw_terminal(10, 94.5, "L, N, FG", "AC Input", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=16)
    draw_terminal(10, 91, "+V (+60V)", "V+ (Double Term)", color=W_60V, bg='#FEF2F2', width=16)
    draw_terminal(10, 87.5, "-V (COM)", "V- (Double Term)", color=W_GND, bg=TERM_BG_EVEN, width=16)
    draw_terminal(10, 81.5, "V-ADJ", "Trim 58-62V", color=TEXT_MUTED, bg='#FFFFFF', width=16)
    ax.text(32, 89, "Dedicated Motor Bus\nRoutable through\nKM1 Safety Contactor", fontsize=6.8, color=W_60V, ha='center', va='center', fontweight='bold')

    # 1.7 PSU 2: 24VDC 5A (120W Mean Well)
    draw_module(8, 46, 40, 27, "PSU 2: 24VDC 5A (120W)", "Industrial Control Supply (DIN Rail NDR-120)", header_color=MOD_HDR_AMBER)
    draw_terminal(10, 63.5, "L, N, FG", "AC Input", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=16)
    draw_terminal(10, 60, "+24VDC", "DC Out V+", color=W_24V, bg='#FFF7ED', width=16)
    draw_terminal(10, 56.5, "0V / GND", "DC Out V-", color=W_GND, bg=TERM_BG_EVEN, width=16)
    ax.text(32, 58, "Supplies IRiV IO,\nSensors, Relays,\nV-PULSE & Z Drive", fontsize=6.8, color=W_24V, ha='center', va='center', fontweight='bold')

    # 1.8 PSU 3: 5VDC 3A (15W USB-C Adapter)
    draw_module(8, 14, 40, 28, "PSU 3: 5VDC 3A (15W)", "Raspberry Pi Official USB-C Adapter", header_color=MOD_HDR_SLATE)
    draw_terminal(10, 32.5, "L, N", "AC Inlet", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=16)
    draw_terminal(10, 29, "USB-C VBUS", "+5.1VDC (Isolated)", color=W_5V, bg='#FAF5FF', width=16)
    draw_terminal(10, 25.5, "USB-C GND", "Power Return", color=W_GND, bg=TERM_BG_EVEN, width=16)
    ax.text(32, 27.5, "Isolated Logic Rail\nPowering CM4 Core\n(Prevents ground loop)", fontsize=6.8, color=W_5V, ha='center', va='center')

    # AC Line Interconnects
    draw_wire([(18, 215), (18, 194.8)], W_AC_L, lw=1.4)
    draw_wire([(22, 211.5), (22, 191.3)], W_AC_N, lw=1.4)

    draw_wire([(18, 185), (18, 170.8)], W_AC_L, lw=1.4)
    draw_wire([(22, 181.5), (22, 167.3)], W_AC_N, lw=1.4)

    draw_wire([(18, 161), (18, 146.8)], W_AC_L, lw=1.4)
    draw_wire([(22, 157.5), (22, 143.3)], W_AC_N, lw=1.4)

    draw_wire([(18, 137.5), (18, 122.8)], W_AC_L, lw=1.4)
    draw_wire([(22, 137.5), (22, 119.3)], W_AC_N, lw=1.4)

    # Earth Bar wire
    draw_wire([(26, 208), (50, 208), (50, 114.6), (26, 114.6)], W_PE, style='--', lw=1.3)

    # AC Bus to 3 DC Power Supplies
    # Live
    draw_wire([(26, 121.6), (51, 121.6), (51, 95.6), (26, 95.6)], W_AC_L, lw=1.4)
    draw_dot(51, 95.6, W_AC_L)
    draw_wire([(51, 95.6), (51, 64.6), (26, 64.6)], W_AC_L, lw=1.4)
    draw_dot(51, 64.6, W_AC_L)
    draw_wire([(51, 64.6), (51, 33.6), (26, 33.6)], W_AC_L, lw=1.4)

    # Neutral
    draw_wire([(26, 118.1), (52.5, 118.1), (52.5, 94.5), (26, 94.5)], W_AC_N, lw=1.4)
    draw_dot(52.5, 94.5, W_AC_N)
    draw_wire([(52.5, 94.5), (52.5, 63.5), (26, 63.5)], W_AC_N, lw=1.4)
    draw_dot(52.5, 63.5, W_AC_N)
    draw_wire([(52.5, 63.5), (52.5, 32.5), (26, 32.5)], W_AC_N, lw=1.4)

    # =========================================================================
    # ZONE 2: MAIN CONTROLLER & FIELD I/O (x: 62 to 142)
    # =========================================================================
    # 2.1 Cytron IRiV PiControl CM4 Box (Upper Half)
    draw_module(62, 124, 80, 99, "Cytron IRiV PiControl CM4 WIRELESS", 
                "Raspberry Pi CM4 (4GB RAM, 32GB eMMC, Dual Ethernet, Isolated GPIO)", 
                header_color=MOD_HDR_NAVY)

    # Power Input Terminals
    ax.text(65, 218, "POWER INPUT TERMINALS:", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    draw_terminal(65, 212.5, "DC 24V IN (+)", "Auxiliary 24V Rail", color=W_24V, bg='#FFF7ED', width=36)
    draw_terminal(65, 209.5, "DC 0V IN (-)", "Field 0V Return", color=W_GND, bg=TERM_BG_EVEN, width=36)
    draw_terminal(103, 212.5, "USB-C (5V 3A)", "CM4 Primary Power", color=W_5V, bg='#FAF5FF', width=36)
    draw_terminal(103, 209.5, "PWR / ACT LED", "System Status Indicators", color=W_PE, bg='#F0FDF4', width=36)

    # Dual Ethernet Ports
    ax.text(65, 205.5, "NETWORK ETHERNET PORTS (DUAL RJ45):", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    draw_terminal(65, 200, "eth0: MGMT LAN", "192.168.70.80 / Flask REST HMI", color=W_ETH, bg='#EFF6FF', width=36)
    draw_terminal(103, 200, "eth1: OT LAN", "10.0.0.2 / Modbus TCP Master", color=W_ETH, bg='#EFF6FF', width=36)

    # USB Peripherals
    ax.text(65, 196, "USB 2.0 PORTS (PERIPHERAL INTERFACE):", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    draw_terminal(65, 190.5, "USB1: QR SCANNER", "2D Barcode / Payment QR CDC", color=W_USB, bg='#EEF2FF', width=36)
    draw_terminal(103, 190.5, "USB2: WEB CAMERA", "FHD 1080p Dispense/Pickup Vision", color=W_USB, bg='#EEF2FF', width=36)
    draw_terminal(65, 187, "USB3 / 3.5mm AUDIO", "Chime / Audio Voice Guidance", color=W_5V, bg='#FAF5FF', width=36)
    draw_terminal(103, 187, "USB4: ST-LINK VCP", "To NUCLEO-G491RE (115200 8-N-1)", color=W_ALM, bg='#FEF2F2', width=36)

    # PiControl Local Isolated GPIO Terminal
    ax.text(65, 183, "ISOLATED GPIO TERMINAL (LOCAL I/O):", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    draw_terminal(65, 177.5, "DI0 (GPIO 13)", "X_DRIVE_ALM (Opto Fail-safe)", color=W_ALM, bg='#FEF2F2', width=36)
    draw_terminal(65, 174.5, "DI1 (GPIO 17)", "Y_DRIVE_ALM (Opto Fail-safe)", color=W_ALM, bg='#FEF2F2', width=36)
    draw_terminal(65, 171.5, "DI2 (GPIO 27)", "X_PEND (Position-End Input)", color=W_DIR, bg='#FFFBEB', width=36)
    draw_terminal(65, 168.5, "DI3 (GPIO 22)", "Y_PEND (Position-End Input)", color=W_DIR, bg='#FFFBEB', width=36)

    draw_terminal(103, 177.5, "DO0 (GPIO 23)", "XY_DRIVE_POWER_KM1 (Coil Drive)", color=W_24V, bg='#FFF7ED', width=36)
    draw_terminal(103, 174.5, "DO1 (GPIO 24)", "Auxiliary Relay Output 1", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=36)
    draw_terminal(103, 171.5, "DO2 (GPIO 25)", "Auxiliary Relay Output 2", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=36)
    draw_terminal(103, 168.5, "DO3 (GPIO 16)", "Auxiliary Relay Output 3", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=36)

    # Software Architecture Summary Box
    ax.add_patch(patches.Rectangle((65, 127), 74, 38, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.9))
    ax.text(67, 161.5, "SOFTWARE DAEMONS & RUNTIME INTERLOCKS:", fontsize=7.5, fontweight='bold', color=MOD_HDR_NAVY)
    ax.text(67, 158, "1. narit-vending-web-iriv.service : HMI Web UI Port 80 (Touchscreen Kiosk)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(67, 154.5, "2. narit-vending-controller-iriv.service : Core Safety Interlock Controller", fontsize=6.8, color=TEXT_MAIN)
    ax.text(67, 151, "3. IPC Bus : /run/narit-vending/ctrl.sock (Unix Domain Socket)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(67, 147.5, "4. Protocol : Safe-Link v3 over USB VCP (/dev/serial/by-id/STLINK...)", fontsize=6.8, color=TEXT_MAIN)
    ax.text(67, 144, "5. Modbus TCP Master : Polls IRiV IO (10.0.0.10:502) every 20ms", fontsize=6.8, color=TEXT_MAIN)
    ax.text(67, 140.5, "6. Watchdog Policy : Auto-disarm motion if Modbus data stale > 350ms", fontsize=6.8, color=W_ALM, fontweight='bold')
    ax.text(67, 137, "7. KM1 Reset Policy : Hardware 3.0s cut -> restore -> verify ALM cleared", fontsize=6.8, color=W_24V)
    ax.text(67, 133.5, "8. Telemetry Hub : MQTT (broker.emqx.io:1883) for cloud dashboard", fontsize=6.8, color=W_ETH)
    ax.text(67, 130, "9. Database : Persistent SQLite slots.json / machine_config.iriv.json", fontsize=6.8, color=TEXT_MUTED)

    # External USB Peripherals Boxes (Placed below PiControl)
    draw_module(62, 100, 24, 20, "SCANNER 2D QR", "Barcode/QR Reader", header_color=MOD_HDR_SLATE)
    draw_terminal(64, 111.5, "USB D+ / D-", "Serial CDC Data", color=W_USB, bg='#FFFFFF', width=20)
    draw_terminal(64, 108.5, "+5V / GND", "USB Power Bus", color=W_5V, bg='#FFFFFF', width=20)
    draw_terminal(64, 105.5, "Beeper / LED", "Scan Confirm", color=W_PE, bg='#FFFFFF', width=20)

    draw_module(90, 100, 24, 20, "WEB CAMERA", "FHD Video UVC", header_color=MOD_HDR_SLATE)
    draw_terminal(92, 111.5, "USB Video UVC", "1080p Stream", color=W_USB, bg='#FFFFFF', width=20)
    draw_terminal(92, 108.5, "+5V / GND", "USB Power Bus", color=W_5V, bg='#FFFFFF', width=20)
    draw_terminal(92, 105.5, "Status LED", "Streaming Ind.", color=W_SIG, bg='#FFFFFF', width=20)

    draw_module(118, 100, 24, 20, "AUDIO SPEAKER", "Voice Guidance", header_color=MOD_HDR_SLATE)
    draw_terminal(120, 111.5, "Audio L / R", "3.5mm Analog", color=W_5V, bg='#FFFFFF', width=20)
    draw_terminal(120, 108.5, "+5V / GND", "USB Power Bus", color=W_5V, bg='#FFFFFF', width=20)
    draw_terminal(120, 105.5, "Amp Volume", "3W Speaker", color=TEXT_MUTED, bg='#FFFFFF', width=20)

    # 2.2 Cytron IRiV IO Controller Box (Lower Half x: 62 to 142, y: 14 to 96)
    draw_module(62, 14, 80, 82, "Cytron IRiV IO CONTROLLER", 
                "Industrial Modbus TCP Remote I/O (11 DI, 4 DO, 24VDC Opto-Isolated)", 
                header_color=MOD_HDR_AMBER)

    # Modbus RJ45 & Power
    draw_terminal(65, 87.5, "MODBUS TCP (RJ45)", "IP: 10.0.0.10:502 / ID: 255", color=W_ETH, bg='#EFF6FF', width=36)
    draw_terminal(103, 87.5, "POWER (+24V / 0V / S/S)", "S/S tied to 0V (PNP Sensor Mode)", color=W_24V, bg='#FFF7ED', width=36)

    # Digital Inputs Table (DI0 to DI10)
    ax.text(65, 84, "FIELD DIGITAL INPUTS (24VDC OPTO-ISOLATED):", fontsize=7.5, fontweight='bold', color=MOD_HDR_AMBER)
    draw_terminal(65, 78.5, "DI0: x_head_limit", "X Min Limit / Home (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 75.5, "DI1: x_tail_limit", "X Max Limit (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 72.5, "DI2: y_head_limit", "Y Min Limit / Drop Level (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 69.5, "DI3: y_tail_limit", "Y Max Limit / Top Level (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 66.5, "DI4: z_head_limit", "Z Min Limit / Retract (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 63.5, "DI5: z_tail_limit", "Z Max Limit / Extend (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 60.5, "DI6: z_home", "Z Home Reference Sensor (NO)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 57.5, "DI7: product_drop_parking", "Drop Alignment Proximity (NO)", color=TEXT_MAIN, bg='#FFFFFF', width=36)
    draw_terminal(65, 54.5, "DI8: product_drop_sensor", "Completed Sensor (Omron E3Z)", color=W_ALM, bg='#FEF2F2', width=36)
    draw_terminal(65, 51.5, "DI9: product_pickup_sensor", "Pickup Sensor (Omron E3Z)", color=W_ALM, bg='#FEF2F2', width=36)
    draw_terminal(65, 48.5, "DI10: estop / KM1_FEEDBACK", "Contactor Aux NC (Fail-Safe)", color=W_ALM, bg='#FEF2F2', width=36)

    # Digital Outputs Table (DO0 to DO3)
    ax.text(103, 84, "FIELD DIGITAL OUTPUTS (SSR / RELAY):", fontsize=7.5, fontweight='bold', color=MOD_HDR_AMBER)
    draw_terminal(103, 78.5, "DO0: ready", "Green Pilot Light (Machine Ready)", color=W_PE, bg='#F0FDF4', width=36)
    draw_terminal(103, 75.5, "DO1: moving", "Yellow Pilot Light (Moving)", color=W_DIR, bg='#FFFBEB', width=36)
    draw_terminal(103, 72.5, "DO2: alarm", "Red Light / Audio Buzzer", color=W_ALM, bg='#FEF2F2', width=36)
    draw_terminal(103, 69.5, "DO3: dispense", "Drop Gate Solenoid Relay", color=W_ETH, bg='#EFF6FF', width=36)

    # Sensor & Wiring Specifications Card inside IRiV IO
    ax.add_patch(patches.Rectangle((103, 17), 36, 49, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.9))
    ax.text(105, 62.5, "FIELD WIRING RULES & SPEC:", fontsize=7.2, fontweight='bold', color=MOD_HDR_NAVY)
    ax.text(105, 59, "• 3-Wire Inductive Proximity:", fontsize=6.8, fontweight='bold', color=TEXT_MAIN)
    ax.text(107, 56, "Brown (BN) : +24VDC (PS2 Rail)", fontsize=6.5, color=W_24V)
    ax.text(107, 53, "Blue (BU)  : 0VDC / COM (PS2 Rail)", fontsize=6.5, color=W_GND)
    ax.text(107, 50, "Black (BK) : Signal -> DI0 to DI7", fontsize=6.5, color=W_SIG)
    ax.text(105, 46.5, "• Photoelectric Sensors (Omron E3Z):", fontsize=6.8, fontweight='bold', color=TEXT_MAIN)
    ax.text(107, 43.5, "Brown : +24VDC | Blue : 0VDC", fontsize=6.5, color=TEXT_MAIN)
    ax.text(107, 40.5, "Black : Out -> DI8 (Drop) / DI9 (Pick)", fontsize=6.5, color=W_ALM)
    ax.text(105, 37, "• Fail-Safe Safety Loop:", fontsize=6.8, fontweight='bold', color=W_ALM)
    ax.text(107, 34, "DI10 active LOW (NC loop).", fontsize=6.5, color=W_ALM)
    ax.text(107, 31, "Broken wire instantly trips E-Stop.", fontsize=6.5, color=W_ALM)
    ax.text(107, 28, "S/S jumper tied to 0V for PNP sensors.", fontsize=6.5, color=TEXT_MUTED)
    ax.text(107, 25, "Shielded cables grounded at cabinet PE.", fontsize=6.5, color=TEXT_MUTED)
    ax.text(107, 21.5, "DO outputs require flyback diode on coils.", fontsize=6.5, color=TEXT_MUTED)

    # =========================================================================
    # CHANNEL 1: POWER GUTTER (x: 50 to 60)
    # =========================================================================
    # +24V Power Bus (Orange-Red)
    draw_wire([(26, 61.1), (54, 61.1), (54, 213.6), (65, 213.6)], W_24V, lw=1.6)
    draw_dot(54, 88.6, W_24V)
    draw_wire([(54, 88.6), (103, 88.6)], W_24V, lw=1.5)

    # 0VDC Power Bus (Solid Dark Slate)
    draw_wire([(26, 57.6), (56, 57.6), (56, 210.6), (65, 210.6)], W_GND, lw=1.6)
    draw_dot(56, 86.5, W_GND)
    draw_wire([(56, 86.5), (103, 86.5)], W_GND, lw=1.5)

    # 5V USB-C Power (Deep Purple)
    draw_wire([(26, 30.1), (58, 30.1), (58, 213.6), (103, 213.6)], W_5V, lw=1.6)

    # Connect Peripherals to PiControl USB
    draw_wire([(74, 120), (74, 190.5)], W_USB, lw=1.3)
    draw_wire([(102, 120), (102, 160), (115, 160), (115, 190.5)], W_USB, lw=1.3)
    draw_wire([(130, 120), (130, 165), (83, 165), (83, 187)], W_5V, lw=1.3)

    # =========================================================================
    # ZONE 3: MOTION CO-PROCESSOR & PULSE INTERFACE (x: 148 to 222)
    # =========================================================================
    # 3.1 STM32 NUCLEO-G491RE Box (Upper Half)
    draw_module(148, 124, 74, 99, "STM32 NUCLEO-G491RE", 
                "ARM Cortex-M4 @ 170MHz (Hardware Timer Output Compare Pulse Gen)", 
                header_color=MOD_HDR_NAVY)

    # ST-LINK USB Input
    draw_terminal(151, 212.5, "ST-LINK V3 USB", "LPUART1 PA2/PA3", color=W_ALM, bg='#FEF2F2', width=33)
    draw_terminal(186, 212.5, "BAUD: 115200 8-N-1", "Safe-Link Protocol v3", color=MOD_HDR_NAVY, bg='#EFF6FF', width=33)
    ax.text(151, 209, "USB Serial Link from PiControl USB4", fontsize=7.0, color=TEXT_MUTED)

    # Pulse / Direction Pins Table
    ax.text(151, 204.5, "PULSE & DIRECTION HARDWARE TIMERS & GPIO:", fontsize=7.8, fontweight='bold', color=MOD_HDR_NAVY)
    
    # X Axis
    draw_terminal(151, 198, "PA8 (TIM1_CH1 / AF6)", "CN10 pin 23 (D7)", color=W_STEP, bg='#EFF6FF', width=33)
    draw_terminal(186, 198, "PB0 (GPIO Output)", "CN7 pin 34 (A3)", color=W_DIR, bg='#FFFBEB', width=33)
    ax.text(151, 194.5, "X Axis STEP (HW Timer) / DIR (Non-inverting)", fontsize=6.8, color=TEXT_MUTED)

    # Y Axis
    draw_terminal(151, 187.5, "PA9 (TIM1_CH2 / AF6)", "CN10 pin 21 (D8)", color=W_STEP, bg='#EFF6FF', width=33)
    draw_terminal(186, 187.5, "PB1 (GPIO Output)", "CN10 pin 24", color=W_DIR, bg='#FFFBEB', width=33)
    ax.text(151, 184, "Y Axis STEP (HW Timer) / DIR (Non-inverting)", fontsize=6.8, color=TEXT_MUTED)

    # Z Axis
    draw_terminal(151, 177, "PA5 (TIM2_CH1 / AF1)", "CN10 pin 11 (D13)", color=W_STEP, bg='#EFF6FF', width=33)
    draw_terminal(186, 177, "PB2 (GPIO Output)", "CN10 pin 22", color=W_DIR, bg='#FFFBEB', width=33)
    ax.text(151, 173.5, "Z Axis STEP (LD2 blink code disabled) / DIR", fontsize=6.8, color=TEXT_MUTED)

    # MCU GND
    draw_terminal(151, 166.5, "MCU GND (Digital Ground)", "Morpho CN10 pin 20 / CN7 pin 20", color=W_GND, bg=TERM_BG_EVEN, width=68)
    ax.text(151, 163, "Must be tied to NMOS Source and Field 0VDC Reference", fontsize=6.8, color=TEXT_MUTED)

    # Firmware Safety Invariants Card - Positioned inside lower STM32
    ax.add_patch(patches.Rectangle((151, 127), 42, 33, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.9))
    ax.text(153, 156.5, "G491RE SAFETY GATES:", fontsize=7.2, fontweight='bold', color=W_ALM)
    ax.text(153, 152.5, "1. Boot: DISARMED, Low, Timers Off", fontsize=6.5, color=TEXT_MAIN)
    ax.text(153, 148.5, "2. Frequency: 10 Hz to 50,000 Hz", fontsize=6.5, color=TEXT_MAIN)
    ax.text(153, 144.5, "3. Batch Limit: 1,000,000 steps/block", fontsize=6.5, color=TEXT_MAIN)
    ax.text(153, 140.5, "4. Watchdog: Heartbeat lost > 500ms", fontsize=6.5, color=W_ALM, fontweight='bold')
    ax.text(153, 136.5, "5. LED Conflict: PB0/PA5 code-disabled", fontsize=6.5, color=TEXT_MUTED)
    ax.text(153, 132.5, "6. Stop: E-Stop/Alarm halts timers", fontsize=6.5, color=W_ALM)
    ax.text(153, 128.5, "7. Exclusive: 1 active axis at a time", fontsize=6.5, color=TEXT_MUTED)

    # 3.2 6-Channel NMOS Open-Drain Level Shifter Board (Middle y: 52 to 121)
    draw_module(148, 52, 74, 69, "6-CH LOGIC-LEVEL NMOS SINK BOARD", 
                "Low-Side Open-Drain Converter (3.3V Logic Input -> 24V Opto Sink)", 
                header_color=MOD_HDR_SLATE)

    # Circuit Topology
    ax.text(151, 114, "OPTO-ISOLATED DRIVE CIRCUIT TOPOLOGY (PER CHANNEL):", fontsize=7.5, fontweight='bold', color=MOD_HDR_NAVY)
    ax.text(151, 110.5, "STM32 GPIO --[Rg 100 Ohm]-- Gate (Qn)    |  Source (Qn) -- Field 0VDC", fontsize=6.8, color=TEXT_MAIN)
    ax.text(151, 107.5, "Gate (Qn) --[Rpd 10k Ohm]-- GND          |  Drain (Qn)  -- Driver PUL- / DIR-", fontsize=6.8, color=TEXT_MAIN)

    # NMOS Channels Table
    draw_terminal(151, 100, "CH1: Gate Q1 (PA8)", "Drain -> X PUL-", color=W_STEP, bg='#EFF6FF', width=33)
    draw_terminal(186, 100, "CH2: Gate Q2 (PB0)", "Drain -> X DIR-", color=W_DIR, bg='#FFFBEB', width=33)

    draw_terminal(151, 94.5, "CH3: Gate Q3 (PA9)", "Drain -> Y PUL-", color=W_STEP, bg='#EFF6FF', width=33)
    draw_terminal(186, 94.5, "CH4: Gate Q4 (PB1)", "Drain -> Y DIR-", color=W_DIR, bg='#FFFBEB', width=33)

    draw_terminal(151, 89, "CH5: Gate Q5 (PA5)", "Drain -> Z PUL-", color=W_STEP, bg='#EFF6FF', width=33)
    draw_terminal(186, 89, "CH6: Gate Q6 (PB2)", "Drain -> Z DIR-", color=W_DIR, bg='#FFFBEB', width=33)

    # V-PULSE and GND Rails
    draw_terminal(151, 81.5, "V-PULSE BUS (+24VDC)", "Common Anode (To all PUL+ & DIR+)", color=W_24V, bg='#FFF7ED', width=68)
    draw_terminal(151, 78, "0V-SIGNAL / COMMON GND", "All Sources + MCU GND + DC 0V", color=W_GND, bg=TERM_BG_EVEN, width=68)

    # 3.3 KM1 Safety Contactor & Hardware Cutoff (Bottom y: 14 to 48)
    draw_module(148, 14, 74, 34, "KM1 SAFETY CONTACTOR & HARDWARE CUTOFF", 
                "Emergency Power Interlock (Independent from Software)", 
                header_color=MOD_HDR_RED)
    draw_terminal(151, 39, "COIL A1 / A2 (24VDC)", "Controlled by PiControl DO0 & E-Stop", color=W_ALM, bg='#FEF2F2', width=33)
    draw_terminal(186, 39, "AUX NC / NO CONTACT", "Feedback -> IRiV IO DI10", color=W_PE, bg='#F0FDF4', width=33)
    draw_terminal(151, 34.5, "MAIN CONTACT 1-2 (+60V)", "In: PSU 60V V+  -> Out: Drivers V+", color=W_60V, bg='#FEF2F2', width=33)
    draw_terminal(186, 34.5, "MAIN CONTACT 3-4 (0V)", "In: PSU 60V COM -> Out: Drivers COM", color=W_GND, bg=TERM_BG_EVEN, width=33)
    ax.text(151, 30.5, "E-Stop button hard-cuts KM1 coil directly; drops 60V DC bus to X/Y drives.", fontsize=6.8, color=W_ALM)
    ax.text(151, 27, "Software Reset: PiControl DO0 toggles coil off 3s to discharge drive alarm.", fontsize=6.8, color=W_24V)
    ax.text(151, 23.5, "Feedback to IRiV IO DI10 confirms physical contactor state (Fail-Safe NC).", fontsize=6.8, color=W_PE)

    # =========================================================================
    # CHANNEL 2: SIGNAL & USB GUTTER (x: 142 to 148)
    # =========================================================================
    # USB ST-LINK from PiControl USB4 to STM32 ST-LINK
    draw_wire([(139, 188.1), (145, 188.1), (145, 213.6), (151, 213.6)], W_ALM, lw=1.6)

    # Modbus TCP Ethernet from PiControl eth1 to IRiV IO Modbus TCP
    draw_wire([(139, 201.1), (146.5, 201.1), (146.5, 88.6), (101, 88.6)], W_ETH, lw=1.8)
    ax.text(147.2, 140, "Modbus TCP\n10.0.0.10:502", color=W_ETH, fontsize=6.8, fontweight='bold', va='center')

    # Wires from STM32 to NMOS Board (routed via right channel x: 196 to 222)
    # X Axis STEP/DIR
    draw_wire([(184, 199.1), (196, 199.1), (196, 101.1), (184, 101.1)], W_STEP, lw=1.3)
    draw_wire([(219, 199.1), (220, 199.1), (220, 101.1), (219, 101.1)], W_DIR, lw=1.3)
    # Y Axis STEP/DIR
    draw_wire([(184, 188.6), (198, 188.6), (198, 95.6), (184, 95.6)], W_STEP, lw=1.3)
    draw_wire([(219, 188.6), (221, 188.6), (221, 95.6), (219, 95.6)], W_DIR, lw=1.3)
    # Z Axis STEP/DIR
    draw_wire([(184, 178.1), (200, 178.1), (200, 90.1), (184, 90.1)], W_STEP, lw=1.3)
    draw_wire([(219, 178.1), (222, 178.1), (222, 90.1), (219, 90.1)], W_DIR, lw=1.3)

    # MCU GND to NMOS Common GND
    draw_wire([(219, 167.6), (224, 167.6), (224, 79.1), (219, 79.1)], W_GND, lw=1.4)

    # 60V from PSU1 into KM1 Contactor
    draw_wire([(26, 92.1), (49, 92.1), (49, 35.6), (151, 35.6)], W_60V, lw=1.8)
    draw_wire([(26, 88.6), (47, 88.6), (47, 32), (186, 32), (186, 33.3)], W_GND, lw=1.8)

    # DO0 from PiControl to KM1 Coil
    draw_wire([(139, 178.6), (144, 178.6), (144, 40.1), (151, 40.1)], W_24V, lw=1.4)

    # =========================================================================
    # ZONE 4: STEPPER MOTOR DRIVERS (x: 230 to 294)
    # =========================================================================
    # 4.1 Driver X: HBS860H (Hybrid Closed-Loop Stepper)
    draw_module(230, 160, 64, 63, "DRIVER X: HBS860H", 
                "Hybrid Closed-Loop Stepper Drive (Leadshine/ReadySky)", 
                header_color=MOD_HDR_SLATE)
    # Power
    draw_terminal(232, 214.5, "AC / AC (V+ / V-)", "+60VDC from KM1 Out", color=W_60V, bg='#FEF2F2', width=29)
    # Control signals
    draw_terminal(232, 211, "PUL+ (V-PULSE)", "+24V Common Anode", color=W_24V, bg='#FFF7ED', width=29)
    draw_terminal(232, 207.5, "PUL- (STEP)", "From NMOS Ch1 (PA8)", color=W_STEP, bg='#EFF6FF', width=29)
    draw_terminal(232, 204, "DIR+ (V-PULSE)", "+24V Common Anode", color=W_24V, bg='#FFF7ED', width=29)
    draw_terminal(232, 200.5, "DIR- (DIRECTION)", "From NMOS Ch2 (PB0)", color=W_DIR, bg='#FFFBEB', width=29)
    draw_terminal(232, 197, "ENA+ / ENA-", "Enable (Optocoupler)", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=29)
    # Feedback
    draw_terminal(232, 192.5, "ALM+ / ALM-", "Alarm -> PiControl DI0", color=W_ALM, bg='#FEF2F2', width=29)
    draw_terminal(232, 189, "PEND+ / PEND-", "In-Pos -> PiControl DI2", color=W_DIR, bg='#FFFBEB', width=29)
    # Motor Coils & Encoder
    draw_terminal(263, 214.5, "A+ / A- (Coil A)", "Phase A Motor (Red/Blu)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 211, "B+ / B- (Coil B)", "Phase B Motor (Blk/Grn)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 206, "EA+ / EA-", "Encoder A Differential", color=W_ETH, bg='#EFF6FF', width=29)
    draw_terminal(263, 202.5, "EB+ / EB-", "Encoder B Differential", color=W_ETH, bg='#EFF6FF', width=29)
    draw_terminal(263, 199, "VCC / EGND", "Enc +5V / 0V (Internal)", color=W_5V, bg='#FAF5FF', width=29)
    draw_terminal(263, 193.5, "DIP SWITCHES", "SW1-SW8: Microstep/Amps", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 190, "TUNING PORT", "RS232 ProTuner config", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=29)
    ax.text(232, 185, "Closed-loop feedback prevents stalling; trips ALM if position lost.", fontsize=6.8, color=MOD_HDR_TEAL)
    ax.text(232, 181.5, "Peak Current: 8.2A, Continuous 5.6A, Microstep default 1600.", fontsize=6.8, color=TEXT_MUTED)

    # 4.2 Driver Y: HBS860H (Hybrid Closed-Loop Stepper)
    draw_module(230, 94, 64, 63, "DRIVER Y: HBS860H", 
                "Hybrid Closed-Loop Stepper Drive (Leadshine/ReadySky)", 
                header_color=MOD_HDR_SLATE)
    # Power
    draw_terminal(232, 148.5, "AC / AC (V+ / V-)", "+60VDC from KM1 Out", color=W_60V, bg='#FEF2F2', width=29)
    # Control signals
    draw_terminal(232, 145, "PUL+ (V-PULSE)", "+24V Common Anode", color=W_24V, bg='#FFF7ED', width=29)
    draw_terminal(232, 141.5, "PUL- (STEP)", "From NMOS Ch3 (PA9)", color=W_STEP, bg='#EFF6FF', width=29)
    draw_terminal(232, 138, "DIR+ (V-PULSE)", "+24V Common Anode", color=W_24V, bg='#FFF7ED', width=29)
    draw_terminal(232, 134.5, "DIR- (DIRECTION)", "From NMOS Ch4 (PB1)", color=W_DIR, bg='#FFFBEB', width=29)
    draw_terminal(232, 131, "ENA+ / ENA-", "Enable (Optocoupler)", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=29)
    # Feedback
    draw_terminal(232, 126.5, "ALM+ / ALM-", "Alarm -> PiControl DI1", color=W_ALM, bg='#FEF2F2', width=29)
    draw_terminal(232, 123, "PEND+ / PEND-", "In-Pos -> PiControl DI3", color=W_DIR, bg='#FFFBEB', width=29)
    # Motor Coils & Encoder
    draw_terminal(263, 148.5, "A+ / A- (Coil A)", "Phase A Motor (Red/Blu)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 145, "B+ / B- (Coil B)", "Phase B Motor (Blk/Grn)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 140, "EA+ / EA-", "Encoder A Differential", color=W_ETH, bg='#EFF6FF', width=29)
    draw_terminal(263, 136.5, "EB+ / EB-", "Encoder B Differential", color=W_ETH, bg='#EFF6FF', width=29)
    draw_terminal(263, 133, "VCC / EGND", "Enc +5V / 0V (Internal)", color=W_5V, bg='#FAF5FF', width=29)
    draw_terminal(263, 127.5, "DIP SWITCHES", "SW1-SW8: Microstep/Amps", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 124, "TUNING PORT", "RS232 ProTuner config", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=29)
    ax.text(232, 119, "Elevator Vertical Axis: Drives SFU1605 Ball Screw + Carriage.", fontsize=6.8, color=MOD_HDR_TEAL)
    ax.text(232, 115.5, "Brake / Holding torque maintains vertical elevator level.", fontsize=6.8, color=TEXT_MUTED)

    # 4.3 Driver Z: DM542 (Digital Microstepping Driver)
    draw_module(230, 38, 64, 53, "DRIVER Z: DM542", 
                "2-Phase Digital Stepper Drive (Peak 4.2A, 20-50VDC)", 
                header_color=MOD_HDR_SLATE)
    # Power
    draw_terminal(232, 82.5, "V+ / GND (24-48V)", "+24VDC from PS2 Rail", color=W_24V, bg='#FFF7ED', width=29)
    # Control signals
    draw_terminal(232, 79, "PUL+ (V-PULSE)", "+24V Common Anode", color=W_24V, bg='#FFF7ED', width=29)
    draw_terminal(232, 75.5, "PUL- (STEP)", "From NMOS Ch5 (PA5)", color=W_STEP, bg='#EFF6FF', width=29)
    draw_terminal(232, 72, "DIR+ (V-PULSE)", "+24V Common Anode", color=W_24V, bg='#FFF7ED', width=29)
    draw_terminal(232, 68.5, "DIR- (DIRECTION)", "From NMOS Ch6 (PB2)", color=W_DIR, bg='#FFFBEB', width=29)
    draw_terminal(232, 65, "ENA+ / ENA-", "Enable Input", color=TEXT_MUTED, bg=TERM_BG_EVEN, width=29)
    # Motor Coils
    draw_terminal(263, 82.5, "A+ / A- (Coil A)", "Phase A Motor (Red/Blu)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 79, "B+ / B- (Coil B)", "Phase B Motor (Blk/Grn)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 73.5, "DIP SW1-SW4", "Current: Peak 2.0A", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    draw_terminal(263, 70, "DIP SW5-SW8", "Microstep: 1600 pulse/rev", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=29)
    ax.text(232, 60.5, "Dispenser Plunger Axis: Drives V-Slot Lead Screw Actuator.", fontsize=6.8, color=MOD_HDR_TEAL)
    ax.text(232, 57, "Safety Notice: Recommend routing 24V through safety contactor.", fontsize=6.8, color=W_ALM)

    # =========================================================================
    # CHANNEL 3: DRIVER PULSE & POWER GUTTER (x: 222 to 230)
    # =========================================================================
    # PUL/DIR Signals from NMOS to Drivers
    # X Axis PUL/DIR
    draw_wire([(184, 101.1), (225, 101.1), (225, 208.6), (232, 208.6)], W_STEP, lw=1.3)
    draw_wire([(219, 101.1), (226, 101.1), (226, 201.6), (232, 201.6)], W_DIR, lw=1.3)
    # Y Axis PUL/DIR
    draw_wire([(184, 95.6), (227, 95.6), (227, 142.6), (232, 142.6)], W_STEP, lw=1.3)
    draw_wire([(219, 95.6), (228, 95.6), (228, 135.6), (232, 135.6)], W_DIR, lw=1.3)
    # Z Axis PUL/DIR
    draw_wire([(184, 90.1), (224, 90.1), (224, 76.6), (232, 76.6)], W_STEP, lw=1.3)
    draw_wire([(219, 90.1), (225, 90.1), (225, 69.6), (232, 69.6)], W_DIR, lw=1.3)

    # V-PULSE (+24V) Bus to all PUL+ & DIR+
    draw_wire([(219, 82.6), (229, 82.6), (229, 212.1), (232, 212.1)], W_24V, lw=1.2)
    draw_dot(229, 212.1, W_24V)
    draw_wire([(229, 212.1), (229, 205.1), (232, 205.1)], W_24V, lw=1.2)
    draw_dot(229, 205.1, W_24V)
    draw_wire([(229, 205.1), (229, 146.1), (232, 146.1)], W_24V, lw=1.2)
    draw_dot(229, 146.1, W_24V)
    draw_wire([(229, 146.1), (229, 139.1), (232, 139.1)], W_24V, lw=1.2)
    draw_dot(229, 139.1, W_24V)
    draw_wire([(229, 139.1), (229, 80.1), (232, 80.1)], W_24V, lw=1.2)
    draw_dot(229, 80.1, W_24V)
    draw_wire([(229, 80.1), (229, 73.1), (232, 73.1)], W_24V, lw=1.2)

    # 60V Power from KM1 to Drivers X and Y
    draw_wire([(184, 35.6), (223, 35.6), (223, 215.6), (232, 215.6)], W_60V, lw=1.8)
    draw_dot(223, 149.6, W_60V)
    draw_wire([(223, 149.6), (232, 149.6)], W_60V, lw=1.8)

    # Feedback Wires from Drivers X/Y to PiControl DI0-DI3
    draw_wire([(232, 193.6), (227.5, 193.6), (227.5, 224), (60, 224), (60, 178.6), (65, 178.6)], W_ALM, lw=1.2)
    draw_wire([(232, 190.1), (226.5, 190.1), (226.5, 222), (61, 222), (61, 172.6), (65, 172.6)], W_DIR, lw=1.2)
    draw_wire([(232, 127.6), (227.5, 127.6), (227.5, 175.6), (101, 175.6)], W_ALM, lw=1.2)
    draw_wire([(232, 124.1), (226.5, 124.1), (226.5, 169.6), (101, 169.6)], W_DIR, lw=1.2)

    # =========================================================================
    # ZONE 5: MOTORS & FIELD SENSORS (x: 304 to 370)
    # =========================================================================
    # 5.1 Motor X: 86HBS85 (NEMA 34 Closed-Loop)
    draw_module(304, 172, 66, 51, "MOTOR X: 86HBS85 (NEMA 34)", 
                "8.5 N.m, 5.6A Hybrid Closed-Loop Stepper + 1000 CPR Encoder", 
                header_color=MOD_HDR_TEAL)
    draw_terminal(306, 214.5, "COIL A: A+ / A-", "Stator Phase A (Red/Blu)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 211, "COIL B: B+ / B-", "Stator Phase B (Blk/Grn)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 206, "ENC: EA+ / EA-", "Channel A Differential", color=W_ETH, bg='#FFFFFF', width=30)
    draw_terminal(306, 202.5, "ENC: EB+ / EB-", "Channel B Differential", color=W_ETH, bg='#FFFFFF', width=30)
    draw_terminal(306, 199, "ENC PWR: VCC/GND", "+5V Red / 0V White", color=W_5V, bg='#FFFFFF', width=30)
    draw_terminal(306, 193.5, "MECHANICAL SHAFT: 14mm Keyed", "HTD 5M 25mm Width Timing Belt Drive", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=62)
    draw_terminal(306, 189.5, "KINEMATICS: 78.43 steps/mm", "Microstep 1600, Pulley Pitch Dia 63.66mm", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=62)
    ax.text(306, 184, "Horizontal Carriage Axis: Rapid Traverse 450 mm/s, Accel 800 mm/s²", fontsize=6.8, color=MOD_HDR_TEAL)
    ax.text(306, 180, "Dual Linear Motion Guide HGR20 for high-rigidity payload movement.", fontsize=6.8, color=TEXT_MUTED)

    # 5.2 Motor Y: 86HBS85 (NEMA 34 Closed-Loop)
    draw_module(304, 114, 66, 51, "MOTOR Y: 86HBS85 (NEMA 34)", 
                "8.5 N.m, 5.6A Hybrid Closed-Loop Stepper + 1000 CPR Encoder", 
                header_color=MOD_HDR_TEAL)
    draw_terminal(306, 148.5, "COIL A: A+ / A-", "Stator Phase A (Red/Blu)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 145, "COIL B: B+ / B-", "Stator Phase B (Blk/Grn)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 140, "ENC: EA+ / EA-", "Channel A Differential", color=W_ETH, bg='#FFFFFF', width=30)
    draw_terminal(306, 136.5, "ENC: EB+ / EB-", "Channel B Differential", color=W_ETH, bg='#FFFFFF', width=30)
    draw_terminal(306, 133, "ENC PWR: VCC/GND", "+5V Red / 0V White", color=W_5V, bg='#FFFFFF', width=30)
    draw_terminal(306, 127.5, "MECHANICAL SHAFT: 14mm Keyed", "SFU1605 Precision Ball Screw (Lead 5mm)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=62)
    draw_terminal(306, 123.5, "KINEMATICS: 320.00 steps/mm", "Microstep 1600, Lead 5.0mm (Direct Coupling)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=62)
    ax.text(306, 118, "Vertical Lift Elevator Axis: Speed 120 mm/s, Accel 600 mm/s²", fontsize=6.8, color=MOD_HDR_TEAL)
    ax.text(306, 114, "Carries Dispensing Basket to product target levels (Slots 1 to 5).", fontsize=6.8, color=TEXT_MUTED)

    # 5.3 Motor Z: NEMA 17 (V-Slot Mini Actuator)
    draw_module(304, 66, 66, 43, "MOTOR Z: NEMA 17 ACTUATOR", 
                "V-Slot Lead Screw Mini Actuator (Dispenser Push Rod)", 
                header_color=MOD_HDR_TEAL)
    draw_terminal(306, 94.5, "COIL A: A+ / A-", "Phase A (Red / Blue)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 91, "COIL B: B+ / B-", "Phase B (Black / Green)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 85.5, "LEAD SCREW: T8x8", "Pitch 2mm, 4 Starts (Lead 8mm/rev)", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=62)
    draw_terminal(306, 81.5, "KINEMATICS: 200.00 steps/mm", "Microstep 1600, Lead 8.0mm/rev", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=62)
    draw_terminal(306, 76.5, "STROKE: 150mm PUSHER", "Pushes product from shelf onto tray", color=TEXT_MAIN, bg=TERM_BG_EVEN, width=62)
    ax.text(306, 71, "Dispenser Pusher: Extends to eject product, retracts before carriage moves.", fontsize=6.8, color=MOD_HDR_TEAL)

    # Motor cables (Driver -> Motor)
    draw_wire([(292, 215.6), (306, 215.6)], W_GND, lw=1.5)
    draw_wire([(292, 212.1), (306, 212.1)], W_GND, lw=1.5)
    draw_wire([(292, 207.1), (306, 207.1)], W_ETH, lw=1.3)
    draw_wire([(292, 203.6), (306, 203.6)], W_ETH, lw=1.3)
    draw_wire([(292, 200.1), (306, 200.1)], W_5V, lw=1.3)

    draw_wire([(292, 149.6), (306, 149.6)], W_GND, lw=1.5)
    draw_wire([(292, 146.1), (306, 146.1)], W_GND, lw=1.5)
    draw_wire([(292, 141.1), (306, 141.1)], W_ETH, lw=1.3)
    draw_wire([(292, 137.6), (306, 137.6)], W_ETH, lw=1.3)
    draw_wire([(292, 134.1), (306, 134.1)], W_5V, lw=1.3)

    draw_wire([(292, 83.6), (306, 83.6)], W_GND, lw=1.5)
    draw_wire([(292, 80.1), (306, 80.1)], W_GND, lw=1.5)

    # 5.4 Industrial Sensors Box (Bottom Right x: 304 to 370, y: 14 to 62)
    draw_module(304, 14, 66, 49, "FIELD SENSORS (INPUTS TO IRiV IO)", 
                "Inductive Proximity & Optical Sensors (24VDC Industrial)", 
                header_color=MOD_HDR_AMBER)
    # Limit Sensors List
    draw_terminal(306, 51.5, "LIMIT MIN X (DI0)", "Head limit / Home (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(338, 51.5, "LIMIT MAX X (DI1)", "Tail limit X (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 48, "LIMIT MIN Y (DI2)", "Bottom limit / Drop (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(338, 48, "LIMIT MAX Y (DI3)", "Top limit Y (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 44.5, "LIMIT MIN Z (DI4)", "Retract limit Z (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(338, 44.5, "LIMIT MAX Z (DI5)", "Extend limit Z (NC)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(306, 41, "Z HOME SENSOR (DI6)", "Home Ref Sensor (NO)", color=TEXT_MAIN, bg='#FFFFFF', width=30)
    draw_terminal(338, 41, "PARKING SENSOR (DI7)", "Carriage Drop Align (NO)", color=TEXT_MAIN, bg='#FFFFFF', width=30)

    # Optical Sensors
    draw_terminal(306, 36.5, "COMPLETED SENSOR (DI8)", "Omron E3Z-D81 (Drop Verification Beam)", color=W_ALM, bg='#FEF2F2', width=62)
    draw_terminal(306, 33, "PICKUP SENSOR (DI9)", "Omron E3Z-D81 (Pickup Door Verification)", color=W_ALM, bg='#FEF2F2', width=62)
    draw_terminal(306, 29.5, "E-STOP AUX FEEDBACK (DI10)", "KM1 Aux NC Contact (Software Interlock)", color=W_ALM, bg='#FEF2F2', width=62)
    draw_terminal(306, 25, "SENSOR POWER RAILS", "Brown = +24V (PS2) | Blue = 0VDC (PS2)", color=W_24V, bg='#FFF7ED', width=62)
    ax.text(306, 20.5, "Shielded twisted pair cables used for all limit sensors; grounded at cabinet PE.", fontsize=6.8, color=TEXT_MUTED)
    ax.text(306, 17, "Active-Low fail-safe NC configuration: Disconnected sensor immediately stops motion.", fontsize=6.8, color=W_ALM)

    # =========================================================================
    # HIGHWAY: SENSOR TRACES ROUTED VIA BOTTOM OPEN CHANNEL (y: 6 to 12)
    # =========================================================================
    # DI0 (X Min)
    draw_wire([(65, 79.6), (60, 79.6), (60, 11.5), (300, 11.5), (300, 52.6), (306, 52.6)], W_SIG, lw=1.2)
    # DI1 (X Max)
    draw_wire([(65, 76.6), (59, 76.6), (59, 10.5), (301, 10.5), (301, 52.6), (338, 52.6)], W_SIG, lw=1.2)
    # DI2 (Y Min)
    draw_wire([(65, 73.6), (58, 73.6), (58, 9.5), (298, 9.5), (298, 49.1), (306, 49.1)], W_SIG, lw=1.2)
    # DI3 (Y Max)
    draw_wire([(65, 70.6), (57, 70.6), (57, 8.5), (299, 8.5), (299, 49.1), (338, 49.1)], W_SIG, lw=1.2)
    # DI4 (Z Min)
    draw_wire([(65, 67.6), (56, 67.6), (56, 7.5), (296, 7.5), (296, 45.6), (306, 45.6)], W_SIG, lw=1.2)
    # DI5 (Z Max)
    draw_wire([(65, 64.6), (55, 64.6), (55, 6.5), (297, 6.5), (297, 45.6), (338, 45.6)], W_SIG, lw=1.2)

    # DI8 (Completed Sensor)
    draw_wire([(65, 55.6), (54, 55.6), (54, 5.5), (302, 5.5), (302, 37.6), (306, 37.6)], W_ALM, lw=1.3)
    # DI9 (Pickup Sensor)
    draw_wire([(65, 52.6), (53, 52.6), (53, 4.5), (303, 4.5), (303, 34.1), (306, 34.1)], W_ALM, lw=1.3)

    # DI10 (E-Stop Feedback) to KM1 Aux NC
    draw_wire([(65, 49.6), (52, 49.6), (52, 3.5), (180, 3.5), (180, 40.1), (186, 40.1)], W_ALM, lw=1.3)

    # Label on bottom sensor highway
    ax.text(220, 8.5, "SHIELDED SENSOR SIGNAL HIGHWAY (DI0 - DI10) ROUTED VIA BASE RACEWAY", 
            color=W_SIG, fontsize=7.2, fontweight='bold', ha='center', va='center')

    # =========================================================================
    # 6. SYSTEM PINOUT & CONNECTION SUMMARY TABLE (ZONE 4 BOTTOM x: 230 to 294)
    # =========================================================================
    ax.add_patch(patches.Rectangle((230, 14), 64, 21, facecolor='#FFFFFF', edgecolor=BORDER_SUB, linewidth=0.9))
    ax.text(232, 31.5, "SYSTEM PINOUT QUICK REFERENCE:", fontsize=7.5, fontweight='bold', color=MOD_HDR_NAVY)
    ax.text(232, 28, "• X Axis: STM32 PA8 (STEP) -> Q1 -> PUL- | PB0 (DIR) -> Q2 -> DIR-", fontsize=6.8, color=TEXT_MAIN)
    ax.text(232, 24.5, "• Y Axis: STM32 PA9 (STEP) -> Q3 -> PUL- | PB1 (DIR) -> Q4 -> DIR-", fontsize=6.8, color=TEXT_MAIN)
    ax.text(232, 21, "• Z Axis: STM32 PA5 (STEP) -> Q5 -> PUL- | PB2 (DIR) -> Q6 -> DIR-", fontsize=6.8, color=TEXT_MAIN)
    ax.text(232, 17.5, "• All Drivers: PUL+ and DIR+ tied to V-PULSE (+24VDC Common Anode)", fontsize=6.8, color=W_24V, fontweight='bold')

    # Save figure
    plt.tight_layout()
    if is_pdf:
        plt.savefig(output_path, format='pdf', bbox_inches='tight', facecolor=BG_CANVAS)
    else:
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=BG_CANVAS)
    plt.close()
    print(f"Publication-grade wiring diagram generated: {output_path}")

if __name__ == "__main__":
    import sys
    base_dir = r"D:\37-Project Narit Vending Machine\Document\NaritVending"
    doc_dir  = r"D:\37-Project Narit Vending Machine\Document"
    
    # Target files
    targets = [
        (os.path.join(base_dir, "narit_vending_wiring_diagram.png"), False),
        (os.path.join(base_dir, "narit_vending_wiring_diagram.pdf"), True),
        (os.path.join(base_dir, "docs", "narit_vending_wiring_diagram.png"), False),
        (os.path.join(base_dir, "docs", "narit_vending_wiring_diagram.pdf"), True),
        (os.path.join(doc_dir, "narit_vending_wiring_diagram.png"), False),
        (os.path.join(doc_dir, "narit_vending_wiring_diagram.pdf"), True),
    ]

    for path, is_pdf in targets:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        generate_diagram(path, is_pdf=is_pdf)
