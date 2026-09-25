from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "pdf" / "narit_vending_wiring_diagram.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
IMG = Path(r"C:\Users\NARUEB~1\AppData\Local\Temp\codex-clipboard-a4bedcc6-608b-44f2-9b17-96a2edc5666f.png")
pdfmetrics.registerFont(TTFont("TH", r"C:\Windows\Fonts\tahoma.ttf"))
pdfmetrics.registerFont(TTFont("THB", r"C:\Windows\Fonts\tahomabd.ttf"))
PAGE = landscape(A3); W, H = PAGE; M = 32
INK=HexColor("#17202A"); BLUE=HexColor("#1769AA"); GREEN=HexColor("#DFF4E4"); CYAN=HexColor("#DFF3FF")
YELLOW=HexColor("#FFF4C2"); RED=HexColor("#B83227"); PINK=HexColor("#FBE1DF"); GRAY=HexColor("#EFF2F4"); MID=HexColor("#64727D")

def lines(s, font, size, width):
    out=[]
    for para in str(s).split("\n"):
        cur=""
        for word in para.split():
            trial=word if not cur else cur+" "+word
            if stringWidth(trial,font,size)<=width: cur=trial
            else: out.append(cur); cur=word
        out.append(cur or "")
    return out
def txt(c,x,y,s,size=9,font="TH",color=INK,width=None,lead=None):
    c.setFillColor(color); c.setFont(font,size); ls=lines(s,font,size,width) if width else str(s).split("\n"); lead=lead or size*1.35
    for i,line in enumerate(ls): c.drawString(x,y-i*lead,line)
    return y-len(ls)*lead
def center(c,x,y,s,size=9,font="TH",color=INK):
    c.setFillColor(color); c.setFont(font,size); c.drawCentredString(x,y,s)
def box(c,x,y,w,h,title,body="",fill=GRAY,stroke=MID):
    c.setFillColor(fill); c.setStrokeColor(stroke); c.setLineWidth(1.1); c.roundRect(x,y,w,h,5,fill=1,stroke=1)
    center(c,x+w/2,y+h-17,title,10,"THB")
    ls=lines(body,"TH",8,w-12); start=y+h-32
    for i,line in enumerate(ls[:5]): center(c,x+w/2,start-i*10.5,line,8)
def arrow(c,x1,y1,x2,y2,label="",color=INK,dash=False):
    import math
    c.saveState(); c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(1.4)
    if dash:c.setDash(5,3)
    c.line(x1,y1,x2,y2); a=math.atan2(y2-y1,x2-x1)
    for off in (2.55,-2.55): c.line(x2,y2,x2+8*math.cos(a+off),y2+8*math.sin(a+off))
    c.restoreState()
    if label:
        tw=stringWidth(label,"TH",7.3); c.setFillColor(white); c.rect((x1+x2)/2-tw/2-3,(y1+y2)/2-5,tw+6,11,fill=1,stroke=0); center(c,(x1+x2)/2,(y1+y2)/2-2,label,7.3,"TH",color)
def header(c,title,sub,p):
    c.setFillColor(INK); c.rect(0,H-55,W,55,fill=1,stroke=0); txt(c,M,H-24,title,17,"THB",white); txt(c,M,H-43,sub,8.2,"TH",HexColor("#DDE6EC"))
    c.setFont("THB",9); c.setFillColor(white); c.drawRightString(W-M,H-24,"NARIT VENDING | AS-CONNECTED PROVISIONAL")
    c.setFont("TH",8); c.drawRightString(W-M,H-42,f"Sheet {p}/3 | 25 Sep 2026")
def footer(c):
    c.setStrokeColor(MID); c.setLineWidth(.5); c.line(M,22,W-M,22)
    txt(c,M,10,"ห้ามใช้เอกสารนี้แทนวงจร E-Stop hardwired; ตัดไฟและ Lockout/Tagout ก่อนตรวจสาย. ข้อมูลที่ต้องยืนยันหน้างานระบุสีเหลือง/แดง.",7.2,"TH",RED)
def table(c,x,y,widths,rows,rowh=25,size=7.5):
    for ri,row in enumerate(rows):
        c.setFillColor(INK if ri==0 else (GRAY if ri%2==0 else white)); c.rect(x,y-rowh,sum(widths),rowh,fill=1,stroke=0); xx=x
        for cell,w in zip(row,widths):
            c.setStrokeColor(HexColor("#AAB4BA")); c.rect(xx,y-rowh,w,rowh,fill=0,stroke=1)
            color=white if ri==0 else INK; font="THB" if ri==0 else "TH"; ls=lines(cell,font,size,w-7)
            for i,line in enumerate(ls[:2]): txt(c,xx+3,y-9-i*(size+1),line,size,font,color)
            xx+=w
        y-=rowh
    return y

c=canvas.Canvas(str(OUT),pagesize=PAGE); c.setTitle("Narit Vending Wiring Diagram - Current Pin Map")
# Sheet 1
header(c,"Narit Vending Wiring Diagram - Wiring ที่ใช้งานปัจจุบัน","ฐานข้อมูล: hardware_config.iriv.json, IRIV_WIRING_TH.md, STM32_NMOS_CURRENT_WIRING_TH.md และ source nucleo_motion.c",1)
box(c,38,340,145,86,"IRIV PiControl CM4","24 VDC control\nUSB VCP 115200 8-N-1\neth0 192.168.70.80",GREEN)
box(c,250,340,150,86,"NUCLEO-F439ZI","motion pulse generator\nSTEP/DIR 3.3 V\ndefault: disarmed",CYAN)
box(c,470,340,145,86,"Q1-Q6 NMOS","6 x low-side / open-drain\nSource -> MCU GND / 0V signal",YELLOW)
box(c,690,410,155,62,"HBS860H X","PUL-/DIR- from Q1/Q2\n60 VDC motion supply",CYAN)
box(c,690,334,155,62,"HBS860H Y","PUL-/DIR- from Q3/Q4\n60 VDC motion supply",CYAN)
box(c,690,258,155,62,"DM542 Z","PUL-/DIR- from Q5/Q6\n24 VDC motion supply",CYAN)
arrow(c,183,383,250,383,"USB control / heartbeat",BLUE); arrow(c,400,383,470,383,"PA/PB GPIO",BLUE)
arrow(c,615,398,690,441,"PUL/DIR",BLUE); arrow(c,615,383,690,365,"PUL/DIR",BLUE); arrow(c,615,368,690,289,"PUL/DIR",BLUE)
box(c,38,170,145,86,"IRIV IO","Modbus TCP 10.0.0.10:502\nDI0-DI10 / DO0-DO3",GREEN)
box(c,250,170,150,86,"Field inputs","limits, Z home, product\nsensors, E-stop feedback",GRAY)
box(c,470,170,145,86,"Field outputs","ready / moving / alarm\ndispense relay",GRAY)
arrow(c,250,213,183,213,"24 V isolated DI",BLUE); arrow(c,400,213,470,213,"SSR auxiliary DO",BLUE)
box(c,900,344,205,125,"Safety circuit - hardwired","E-stop + safety relay/KM1 must stop motion independently of Pi, USB, Modbus and firmware.\n\nKNOWN GAP: X/Y 60 V is cut by KM1; Z DM542 24 V is not proven through KM1.",PINK,RED)
txt(c,38,120,"Signal topology (common-anode): V-PULSE (5 V or 24 V after verification) -> driver PUL+/DIR+; NMOS drain -> PUL-/DIR-. MCU HIGH turns NMOS ON. Never apply V-PULSE to STM32 GPIO.",8.4,"TH",INK,1080)
txt(c,38,90,"Status: Pins and channels on Sheets 2-3 reflect the latest configuration/source. Driver input voltage, NMOS component values, exact terminal numbering and physical cable continuity remain field-verification items.",8.4,"TH",RED,1080)
footer(c); c.showPage()
# Sheet 2
header(c,"Pin Schedule - NUCLEO, IRIV IO และสายสัญญาณ","Pin map for commissioning; use STM32 port name + CN pin as the primary identifier",2)
rows=[["Tag","Function","Controller pin / channel","Connector / path","Destination","Status"],
["S300/S301","X pulse","PA8 / TIM1_CH1","CN12 pin 23 -> Q1","HBS860H X PUL-","source-confirmed"],
["S302/S303","X direction","PB0 GPIO","CN10 pin 31 / D33 -> Q2","HBS860H X DIR-","source-confirmed"],
["S310/S311","Y pulse","PA9 / TIM1_CH2","CN12 pin 21 -> Q3","HBS860H Y PUL-","source-confirmed"],
["S312/S313","Y direction","PB1 GPIO","CN10 pin 7 / A6 -> Q4","HBS860H Y DIR-","source-confirmed"],
["S320/S321","Z pulse","PA5 / TIM2_CH1","CN12 pin 11 / CN7 pin 10 -> Q5","DM542 Z PUL-","source-confirmed"],
["S322/S323","Z direction","PB2 GPIO","CN10 pin 15 / D27 -> Q6","DM542 Z DIR-","source-confirmed"],
["S331","signal reference","MCU GND","CN10 pin 5/17/27 -> NMOS Source","0V-SIGNAL","verify continuity"],
["S330","signal common +","V-PULSE fused","terminal distribution","X/Y/Z PUL+ and DIR+","verify 5/24 V rating"]]
table(c,35,H-80,[100,145,175,235,250,180],rows,28,7.7)
txt(c,38,390,"IRIV IO input mapping",10,"THB",BLUE)
di=[["Channel","Software name","Field signal"],
["DI0","x_head_limit","X Min"],["DI1","x_tail_limit","X Max"],["DI2","y_head_limit","Y Min"],["DI3","y_tail_limit","Y Max"],["DI4","z_head_limit","Z Min"],["DI5","z_tail_limit","Z Max"],["DI6","z_home","Z Home"],["DI7","product_drop_parking","Product drop parking"],["DI8","product_drop_sensor","Product drop sensor"],["DI9","product_pickup_sensor","Product pickup sensor"],["DI10","estop","E-stop / safety relay feedback; polarity NOT verified"]]
table(c,38,370,[100,210,270],di,20,7.5)
txt(c,690,390,"IRIV IO output mapping",10,"THB",BLUE)
do=[["Channel","Software name","Load / rule"],["DO0","ready","Machine-ready / green light"],["DO1","moving","Moving / yellow light"],["DO2","alarm","Alarm light / buzzer"],["DO3","dispense","Interposing relay only"]]
table(c,690,370,[100,190,350],do,25,7.5)
txt(c,690,207,"DO0-DO3 are SSR auxiliary outputs. They must not be used for STEP, DIR, PWM, driver enable or E-stop. DI10 is fail-safe in configuration until both pressed/released raw states are recorded.",8.2,"TH",RED,530)
footer(c); c.showPage()
# Sheet 3
header(c,"Comparison - ผังที่แนบ vs Wiring ที่กำลังใช้งาน","ภาพที่ผู้ใช้แนบใช้เป็น reference diagram only; current source/configuration takes precedence",3)
if IMG.exists(): c.drawImage(str(IMG),35,315,width=530,height=326,preserveAspectRatio=True,anchor='sw')
else: box(c,35,315,530,326,"Attached reference diagram","Source image unavailable at generation time",GRAY)
txt(c,35,290,"Reference diagram supplied by user",9,"THB",MID)
current=[["Topic","Attached/reference diagram","Current wiring confirmed in project","Action before energizing"],
["Motion source","IRIV PiControl shown near drivers","NUCLEO-F439ZI creates X/Y/Z STEP/DIR; IRIV commands it through USB VCP","Do not wire Pi/IRIV SSR outputs as pulses"],
["Motion pins","No individual controller pins shown","PA8/PB0 = X, PA9/PB1 = Y, PA5/PB2 = Z through Q1-Q6 NMOS","Label CN pins and perform continuity test"],
["I/O sensors","Limits + product sensors shown","IRIV IO DI0-DI10 mapping includes X/Y/Z limits, Z home, three product sensors, E-stop feedback","Commission every DI; DI10 polarity unverified"],
["Driver assignment","3 drivers pictured","X HBS860H; Y HBS860H; Z DM542 (Y model/input rating still field verify)","Read driver labels and input-voltage rating"],
["Safety / power","General 60 V / 24 V supplies shown","Safety must be hardwired. Known gap: Z 24 V DM542 not proven isolated by KM1","Close gap and validate stop category"],
["ENA / feedback","Not detailed","No ENA, limit, alarm or E-stop is wired directly into current Nucleo motion module","Do not claim production safety from firmware"]]
table(c,590,640,[65,100,215,185],current,54,6.3)
txt(c,590,230,"Firmware note: the repository includes a motion-capable source candidate, but the discovered safe-link binary supports PING/STATUS only. Confirm the flashed binary hash/version and scope Gate/Drain outputs before connecting a driver or motor.",8.0,"TH",RED,565)
txt(c,590,165,"Acceptance gate: this drawing is AS-CONNECTED PROVISIONAL, not verified as-built or issued for construction. It must be signed off after physical terminal, voltage, NMOS and safety tests.",8.0,"TH",RED,565)
footer(c); c.save(); print(OUT)
