from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'/'pdf'/'narit_vending_wiring_diagram.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('TH',r'C:\Windows\Fonts\tahoma.ttf'))
pdfmetrics.registerFont(TTFont('THB',r'C:\Windows\Fonts\tahomabd.ttf'))
W,H=2728.8,1792.8
NAVY=HexColor('#111C31'); INK=HexColor('#243147'); LINE=HexColor('#A6B4C4'); PALE=HexColor('#F7FAFC')
BLUE=HexColor('#0A96C8'); COBALT=HexColor('#254FBD'); GREEN=HexColor('#007A55'); MINT=HexColor('#E9F9F2')
ORANGE=HexColor('#E27A00'); AMBER=HexColor('#FFF1C9'); RED=HexColor('#D52626'); PINK=HexColor('#FFF0F0'); PURPLE=HexColor('#7047D7'); GRAY=HexColor('#EDF2F7')

def tx(c,x,y,s,size=10,bold=False,color=INK):
    c.setFillColor(color); c.setFont('THB' if bold else 'TH',size); c.drawString(x,y,s)
def wrap(c,s,width,size,bold=False):
    font='THB' if bold else 'TH'; parts=[]
    for para in str(s).split('\n'):
        cur=''
        for word in para.split():
            z=word if not cur else cur+' '+word
            if c.stringWidth(z,font,size)<=width:cur=z
            else: parts.append(cur);cur=word
        parts.append(cur or '')
    return parts
def para(c,x,y,s,width,size=9,bold=False,color=INK,lead=None):
    lead=lead or size*1.22
    for i,line in enumerate(wrap(c,s,width,size,bold)):tx(c,x,y-i*lead,line,size,bold,color)
def zone(c,x,y,w,h,title,sub,color):
    c.setStrokeColor(LINE);c.setFillColor(HexColor('#FBFCFE'));c.roundRect(x,y,w,h,5,fill=1,stroke=1)
    tx(c,x+8,y+h+13,title,12,True,NAVY);tx(c,x+8,y+h-2,sub,7,False,HexColor('#536274'))
    c.setFillColor(color);c.rect(x,y+h-7,w,3,fill=1,stroke=0)
def block(c,x,y,w,h,title,subtitle,rows,head,fill=white):
    c.setStrokeColor(HexColor('#7890A8'));c.setFillColor(fill);c.roundRect(x,y,w,h,6,fill=1,stroke=1)
    c.setFillColor(head);c.roundRect(x,y+h-31,w,31,6,fill=1,stroke=0);c.rect(x,y+h-31,w,8,fill=1,stroke=0)
    tx(c,x+12,y+h-19,title,10,True,white);tx(c,x+12,y+h-29,subtitle,6.8,False,white)
    top=y+h-46
    for i,(a,b) in enumerate(rows):
        yy=top-i*25
        if yy<y+9:break
        c.setFillColor(HexColor('#F4F7FA') if i%2==0 else white);c.rect(x+9,yy-16,w-18,18,fill=1,stroke=0)
        tx(c,x+14,yy-4,a,7.3,True,head);para(c,x+w*.42,yy-4,b,w*.54,7.1)
def wire(c,x1,y1,x2,y2,color,label=''):
    c.saveState();c.setStrokeColor(color);c.setLineWidth(2.3);c.line(x1,y1,x2,y2);c.restoreState()
    if label:
        c.setFillColor(white);c.rect((x1+x2)/2-34,(y1+y2)/2-7,68,13,fill=1,stroke=0);tx(c,(x1+x2)/2-30,(y1+y2)/2-3,label,6.5,True,color)
def note(c,x,y,w,h,title,items,color=RED):
    c.setStrokeColor(color);c.setFillColor(PINK if color==RED else AMBER);c.roundRect(x,y,w,h,6,fill=1,stroke=1)
    tx(c,x+12,y+h-20,title,10,True,color)
    yy=y+h-39
    for it in items:
        para(c,x+15,yy,'• '+it,w-25,7.5,False,INK);yy-=28

c=canvas.Canvas(str(OUT),pagesize=(W,H)); c.setTitle('Narit Vending - Complete Electrical & Wiring Diagram')
c.setFillColor(white);c.rect(0,0,W,H,fill=1,stroke=0);c.setStrokeColor(LINE);c.rect(9,9,W-18,H-18,fill=0,stroke=1);c.rect(28,28,W-56,H-56,fill=0,stroke=1)
c.setFillColor(NAVY);c.rect(48,H-121,W-96,75,fill=1,stroke=0)
tx(c,83,H-76,'NARIT VENDING MACHINE -- COMPLETE SYSTEM ELECTRICAL & WIRING DIAGRAM',19,True,white)
tx(c,83,H-100,'AS-CONNECTED PROVISIONAL | Current project configuration + NUCLEO motion source | verify terminals and voltages at machine',8,False,HexColor('#CFDBEB'))
tx(c,W-310,H-74,'DOC REV: 3.0 (CURRENT WIRING)',9,True,BLUE);tx(c,W-310,H-98,'VOLTAGE: 220 VAC / 60 VDC / 24 VDC / V-PULSE',7.5,False,HexColor('#CFDBEB'))

# zone frames
Y=115; ZH=1510
zone(c,48,Y,330,ZH,'[ZONE 1] AC MAINS & POWER SUPPLY','AC input, protection and DC distribution',RED)
zone(c,402,Y,635,ZH,'[ZONE 2] MAIN CONTROLLER & FIELD I/O','IRIV PiControl, IRIV IO and peripherals',BLUE)
zone(c,1060,Y,455,ZH,'[ZONE 3] MOTION CO-PROCESSOR (STM32)','NUCLEO-F439ZI, NMOS interface and safety notes',COBALT)
zone(c,1540,Y,515,ZH,'[ZONE 4] STEPPER MOTOR DRIVERS','common-anode PUL/DIR signal interface',GREEN)
zone(c,2080,Y,600,ZH,'[ZONE 5] MOTORS & SENSORS','axis motors, limits and product sensing',GREEN)

# power
block(c,65,1370,295,120,'AC MAINS INPUT 220V','L / N / PE', [('L (line)','220 VAC'),('N (neutral)','0 VAC'),('PE (earth)','cabinet PE bar')],RED,PINK)
block(c,65,1215,295,120,'MCB + EMI + SPD','protected AC chain', [('MCB','2-pole C16A'),('EMI filter','L/N pass-through'),('SPD','PE bond'),('terminal jumper','AC distribution')],NAVY,GRAY)
block(c,65,1015,295,160,'PSU 60 VDC','motion supply for X/Y', [('+V / -V','60 VDC'),('branch','HBS860H X'),('branch','HBS860H Y'),('safety','KM1 controlled')],RED,PINK)
block(c,65,805,295,165,'PSU 24 VDC','control + field I/O', [('+24 / 0V','IRIV PiControl'),('+24 / 0V','IRIV IO'),('+24 / 0V','DM542 Z supply'),('note','Z isolation via KM1 unproven')],ORANGE,AMBER)
block(c,65,645,295,120,'PSU USB-C 15 W','PiControl auxiliary supply', [('USB-C','5 V / 3 A'),('use','board power path'),('verify','actual installed input')],PURPLE,HexColor('#F6F1FF'))

# iriv controls
block(c,425,1050,590,390,'Cytron IRIV PiControl CM4','main logic / USB host / network',[('24 V input','fused control branch'),('eth0','192.168.70.80 management LAN'),('eth1','10.0.0.2 OT LAN'),('USB-C VCP','NUCLEO control 115200 8-N-1'),('USB1','QR scanner'),('USB2','web camera'),('USB3','audio speaker'),('status','IRIV commands motion; does not create STEP/DIR')],BLUE,HexColor('#EDF9FE'))
block(c,425,820,180,170,'QR SCANNER','USB peripheral',[('USB','IRIV USB1'),('+5 V/GND','USB power'),('signal','barcode / payment')],PURPLE,HexColor('#F6F1FF'))
block(c,625,820,180,170,'WEB CAMERA','USB peripheral',[('USB','IRIV USB2'),('+5 V/GND','USB power'),('status LED','USB device')],PURPLE,HexColor('#F6F1FF'))
block(c,825,820,180,170,'AUDIO SPEAKER','USB audio',[('USB','IRIV USB3'),('+5 V/GND','USB power'),('audio','amp / volume')],PURPLE,HexColor('#F6F1FF'))
block(c,425,245,590,530,'Cytron IRIV IO CONTROLLER','Modbus TCP 10.0.0.10:502 | Unit ID 255',[('DI0','X Min / x_head_limit'),('DI1','X Max / x_tail_limit'),('DI2','Y Min / y_head_limit'),('DI3','Y Max / y_tail_limit'),('DI4','Z Min / z_head_limit'),('DI5','Z Max / z_tail_limit'),('DI6','Z Home / z_home'),('DI7-DI9','parking, drop, pickup sensors'),('DI10','E-stop feedback - polarity UNVERIFIED'),('DO0-DO3','ready, moving, alarm, dispense relay')],ORANGE,HexColor('#FFF9E8'))

# STM32
block(c,1080,1045,415,430,'STM32 NUCLEO-F439ZI','motion pulse generator; USB VCP',[('USB VCP','115200 8-N-1 / control + heartbeat'),('PA8 TIM1_CH1','X_PUL -> Q1 -> X PUL-'),('PB0 GPIO','X_DIR -> Q2 -> X DIR-'),('PA9 TIM1_CH2','Y_PUL -> Q3 -> Y PUL-'),('PB1 GPIO','Y_DIR -> Q4 -> Y DIR-'),('PA5 TIM2_CH1','Z_PUL -> Q5 -> Z PUL-'),('PB2 GPIO','Z_DIR -> Q6 -> Z DIR-'),('MCU GND','CN10 pin 5/17/27 -> NMOS Source')],COBALT,HexColor('#EEF3FF'))
block(c,1080,570,415,430,'6-CH LOGIC-LEVEL NMOS SINK BOARD','low-side / open-drain conversion',[('Q1','PA8 gate -> X PUL-'),('Q2','PB0 gate -> X DIR-'),('Q3','PA9 gate -> Y PUL-'),('Q4','PB1 gate -> Y DIR-'),('Q5','PA5 gate -> Z PUL-'),('Q6','PB2 gate -> Z DIR-'),('V-PULSE','fused 5 V or 24 V ONLY after rating check'),('0V-SIGNAL','common with STM32 GND and NMOS sources')],GREEN,MINT)
note(c,1080,245,415,280,'SAFETY / FIRMWARE GATES',['Default state is disarmed; STEP/DIR LOW at reset.','Source limits: 10-1000 Hz, max 10000 steps, 500 ms heartbeat watchdog.','ENA, limit, alarm and E-stop are NOT wired directly into the Nucleo motion module.','The deployed safe-link binary may be PING/STATUS only; verify flash hash/version.'],RED)

# drivers
block(c,1560,1160,475,285,'DRIVER X: HBS860H','Axis X closed-loop stepper driver',[('60 VDC','from KM1-controlled motion PSU'),('PUL+ / PUL-','V-PULSE / Q1 drain'),('DIR+ / DIR-','V-PULSE / Q2 drain'),('ENA','not assigned by current Nucleo wiring'),('motor','A+/A-/B+/B- and encoder')],GREEN,MINT)
block(c,1560,790,475,285,'DRIVER Y: HBS860H','Axis Y closed-loop stepper driver',[('60 VDC','from KM1-controlled motion PSU'),('PUL+ / PUL-','V-PULSE / Q3 drain'),('DIR+ / DIR-','V-PULSE / Q4 drain'),('ENA','not assigned by current Nucleo wiring'),('motor','A+/A-/B+/B- and encoder')],GREEN,MINT)
block(c,1560,420,475,285,'DRIVER Z: DM542','Axis Z stepper driver',[('24 VDC','control PSU branch; safety isolation gap'),('PUL+ / PUL-','V-PULSE / Q5 drain'),('DIR+ / DIR-','V-PULSE / Q6 drain'),('ENA','not assigned by current Nucleo wiring'),('motor','A+/A-/B+/B-')],GREEN,MINT)
note(c,1560,245,475,135,'KM1 HARDWIRED SAFETY CUTOFF',['E-stop + safety relay must stop motion independently of software. X/Y 60 V cut is documented; prove/close the Z 24 V safety gap before production.'],RED)

# motors and sensors
block(c,2100,1210,560,230,'MOTOR X: 86HBS85 / NEMA 34','HBS860H X load',[('coil A','A+ / A-'),('coil B','B+ / B-'),('encoder','EA+/EA-/EB+/EB-/VCC/EGND'),('mechanical','trace and label actual axis cable')],GREEN,MINT)
block(c,2100,900,560,230,'MOTOR Y: closed-loop stepper','HBS860H Y load',[('coil A','A+ / A-'),('coil B','B+ / B-'),('encoder','EA+/EA-/EB+/EB-/VCC/EGND'),('mechanical','driver model / input rating verify')],GREEN,MINT)
block(c,2100,620,560,205,'MOTOR Z: V-slot mini actuator','DM542 Z load',[('coil A','A+ / A-'),('coil B','B+ / B-'),('mechanical','lead screw / actuator'),('safety','confirm Z is stopped by E-stop')],GREEN,MINT)
block(c,2100,245,560,320,'FIELD SENSORS -> IRIV IO','24 V isolated digital inputs',[('DI0-DI5','X/Y/Z min and max limits'),('DI6','Z home'),('DI7','product drop parking'),('DI8','product drop sensor'),('DI9','product pickup sensor'),('DI10','E-stop / safety relay feedback'),('wiring','shielded pair; bond shield to cabinet PE at one end')],BLUE,HexColor('#EEF8FF'))

# connectivity, drawn on top but sparse routes
wire(c,360,1075,425,1075,RED,'24 V')
wire(c,360,1090,1560,1305,RED,'60 V / KM1')
wire(c,360,1080,1560,935,RED,'60 V / KM1')
wire(c,360,890,1560,565,ORANGE,'24 V')
wire(c,1015,1240,1080,1240,PURPLE,'USB VCP')
wire(c,1495,855,1560,1290,ORANGE,'PUL/DIR')
wire(c,1495,800,1560,920,ORANGE,'PUL/DIR')
wire(c,1495,745,1560,550,ORANGE,'PUL/DIR')
wire(c,2035,1300,2100,1300,GREEN,'motor')
wire(c,2035,930,2100,990,GREEN,'motor')
wire(c,2035,560,2100,700,GREEN,'motor')
wire(c,2100,420,1015,480,BLUE,'DI0-DI10')

tx(c,55,55,'Drawing basis: hardware_config.iriv.json | docs/IRIV_WIRING_TH.md | docs/STM32_NMOS_CURRENT_WIRING_TH.md | NaritVendingV1/stm32/Src/nucleo_motion.c',7,False,HexColor('#556577'))
tx(c,W-815,55,'NOT VERIFIED AS-BUILT: confirm driver label, V-PULSE, NMOS values, terminal continuity, flashed firmware and safety function before energizing.',7,True,RED)
c.save();print(OUT)
