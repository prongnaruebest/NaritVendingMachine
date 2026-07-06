import time
import sys
import select
from gpiozero import OutputDevice, DigitalInputDevice

# ====================================================
# 🛠️ 1. HARDWARE CONFIGURATION (พินพายตามที่คุณกำหนด 100%)
# ====================================================
# 🎛️ พินไดรเวอร์มอเตอร์ 3 แกน (โครงสร้าง Common Cathode แชร์กราวด์ลบ)
pul_x = OutputDevice(16, active_high=True, initial_value=False) # พินทางกายภาพหมายเลข 36
dir_x = OutputDevice(23, active_high=True, initial_value=False) # พินทางกายภาพหมายเลข 16

pul_y = OutputDevice(26, active_high=True, initial_value=False) # พินทางกายภาพหมายเลข 37
dir_y = OutputDevice(24, active_high=True, initial_value=False) # พินทางกายภาพหมายเลข 18

pul_z = OutputDevice(18, active_high=True, initial_value=False) # พินทางกายภาพหมายเลข 12
dir_z = OutputDevice(25, active_high=True, initial_value=False) # พินทางกายภาพหมายเลข 22

# 🔍 พินสวิตช์ลิมิต NO 6 ตัว (อีกขาต่อไฟ 3.3V เมื่อชนสวิตช์ต่อวงจร ค่าจะเป็น 1)
lim_x_head = DigitalInputDevice(17, pull_up=False) # พิน 11 (X Min / Home)
lim_x_tail = DigitalInputDevice(27, pull_up=False) # พิน 13 (X Max)

lim_y_head = DigitalInputDevice(22, pull_up=False) # พิน 15 (Y Min / Home)
lim_y_tail = DigitalInputDevice(9,  pull_up=False) # พิน 21 (Y Max)

lim_z_head = DigitalInputDevice(11, pull_up=False) # พิน 23 (Z Min / Home)
lim_z_tail = DigitalInputDevice(5,  pull_up=False) # พิน 29 (Z Max)

# 🚨 พินปุ่มหยุดฉุกเฉินฮาร์ดแวร์ภายนอก GPIO 6 (พินทางกายภาพหมายเลข 31)
estop_button = DigitalInputDevice(6, pull_up=False)

# ====================================================
# ⚙️ 2. PARAMETERS (ลงตัวที่ 400 Pulses/Rev ทุกแกนแล้ว)
# ====================================================
STEPS_PER_REV = 400       
DISTANCE_PER_REV_MM = 1.0 
STEPS_PER_MM = STEPS_PER_REV / DISTANCE_PER_REV_MM  # = 400 steps/mm

# ความเร็วสูงสุดสำหรับการเคลื่อนที่แบบ Absolute
PULSE_DELAY_MAX = 0.00035     

# ความเร็วปลอดภัยสำหรับวิ่งกลับบ้าน (Homing) ห้ามเร่งเกินไปป้องกันการกระแทกแรง
HOMING_PULSE_DELAY = 0.00080  

# ตัวแปรจำพิกัดตำแหน่งปัจจุบันในแรม (หน่วย: mm)
current_positions = {'x': 0.0, 'y': 0.0, 'z': 0.0}

# ====================================================
# 🔍 3. NON-BLOCKING KEYBOARD CHECKER
# ====================================================
def check_keyboard_stop():
    """เช็คอินพุตแป้นพิมพ์แบบ Real-time ไม่หน่วงลูปส่งพัลส์"""
    if select.select([sys.stdin], [], [], 0.0)[0]:
        line = sys.stdin.readline().strip().lower()
        if line == 's':
            return True
    return False

# ====================================================
# 🏠 4. AUTOMATIC HOMING ENGINE (ระบบวิ่งหาจุดศูนย์สัมบูรณ์)
# ====================================================
def execute_axis_homing(axis_name):
    """ฟังก์ชันสั่งแกนวิ่งถอยหลังกลับไปหา Limit Min เพื่อเซ็ตค่าเป็น 0"""
    global current_positions
    
    if axis_name == 'x':
        pul, _dir, lim_head = pul_x, dir_x, lim_x_head
    elif axis_name == 'y':
        pul, _dir, lim_head = pul_y, dir_y, lim_y_head
    elif axis_name == 'z':
        pul, _dir, lim_head = pul_z, dir_z, lim_z_head

    if estop_button.value:
        print(f"🚨 [Homing ถูกระงับ]: ปุ่มฉุกเฉิน E-STOP ทำงานอยู่ ไม่สามารถขยับแกน {axis_name.upper()} ได้")
        return

    # 1. เช็คก่อนว่าจอดทับลิมิตอยู่แล้วหรือไม่
    if lim_head.value:
        current_positions[axis_name] = 0.0
        print(f"📍 แกน {axis_name.upper()} จอดทับสวิตช์ลิมิตอยู่แล้ว -> รีเซ็ตตำแหน่งเป็น 0.0 mm ทันที\n")
        return

    print(f"🏠 [Homing]: แกน {axis_name.upper()} กำลังวิ่งถอยหลังกลับจุด Home (Limit Min)...")
    _dir.off() # สับลอจิกถอยหลังมุ่งหน้าสู่สวิตช์ฝั่งหัว
    time.sleep(0.005)

    is_aborted = False
    
    # เคลียร์บัฟเฟอร์คีย์บอร์ดเก่า
    while select.select([sys.stdin], [], [], 0.0)[0]:
        sys.stdin.readline()

    # ลูปส่งพัลส์ต่อเนื่องเพื่อวิ่งกลับบ้านแบบไม่จำกัดระยะ (Infinite Loop จนกว่าจะชนสวิตช์)
    while True:
        # ระบบเฝ้าระวังความปลอดภัยระดับมิลลิวินาที
        if check_keyboard_stop():
            print(f"\n🛑 [STOP]: สั่งเบรกกระบวนการ Homing ของแกน {axis_name.upper()} ทันที")
            is_aborted = True
            break
        if estop_button.value:
            print("\n🚨 [EMERGENCY]: ปุ่มหยุดฉุกเฉินภายนอกถูกกดตัดการทำ Homing!")
            is_aborted = True
            break
            
        # 💥 หัวใจหลัก: เมื่อขยับชนลิมิตสวิตช์ Min (HEAD) สำเร็จ
        if lim_head.value:
            pul.off()
            current_positions[axis_name] = 0.0 # รีเซ็ตพิกัดในแรมเป็นศูนย์สัมบูรณ์
            print(f"\n🎯 [HOME REACHED]: แกน {axis_name.upper()} แตะโดนเซนเซอร์ Min เรียบร้อยแล้ว! -> ปรับตำแหน่งเป็น 0.0 mm")
            break

        # ส่งพัลส์ความเร็วคงที่ปลอดภัย
        pul.on()
        time.sleep(HOMING_PULSE_DELAY)
        pul.off()
        time.sleep(HOMING_PULSE_DELAY)

    if is_aborted:
        pul.off()
        print(f"⚠️ กระบวนการ Homing ล้มเหลว! พิกัดปัจจุบันแกน {axis_name.upper()} อาจคลาดเคลื่อน\n")
    else:
        print(f"🟢 แกน {axis_name.upper()} คาริเบรตเสร็จสิ้น พร้อมใช้งาน\n")

# ====================================================
# 📈 5. SAFETY INTEGRATED Absolute MOTION ENGINE
# ====================================================
def move_axis_absolute(axis_name, target_mm):
    """ฟังก์ชันสั่งขยับแกนเดี่ยวไปยังพิกัด Absolute พร้อมระบบเร่งความเร็วสั้นและเซฟตี้ขัดจังหวะรอบด้าน"""
    global current_positions
    
    if axis_name == 'x':
        pul, _dir, lim_head, lim_tail = pul_x, dir_x, lim_x_head, lim_x_tail
    elif axis_name == 'y':
        pul, _dir, lim_head, lim_tail = pul_y, dir_y, lim_y_head, lim_y_tail
    elif axis_name == 'z':
        pul, _dir, lim_head, lim_tail = pul_z, dir_z, lim_z_head, lim_z_tail

    if target_mm < 0 or target_mm > 200:
        print(f"❌ [คำสั่งระงับ]: พิกัด {target_mm} mm อยู่นอกช่วงปลอดภัยตู้ (0-200 mm)!\n")
        return

    if estop_button.value:
        print("🚨 [ระงับการขยับ]: ไม่สามารถทำงานได้เนื่องจากปุ่มฉุกเฉิน E-STOP ทำงานอยู่!")
        return

    current_mm = current_positions[axis_name]
    delta_mm = target_mm - current_mm
    
    if delta_mm == 0:
        print(f"ℹ️ แกน {axis_name.upper()} อยู่ที่ตำแหน่ง {target_mm} mm อยู่แล้ว\n")
        return

    if delta_mm > 0 and lim_tail.value:
        print(f"⚠️ [คำสั่งระงับ]: แกน {axis_name.upper()} ชนลิมิตฝั่ง TAIL อยู่แล้ว ไม่สามารถเดินหน้าได้!")
        return
    if delta_mm < 0 and lim_head.value:
        current_positions[axis_name] = 0.0
        print(f"💥 แกน {axis_name.upper()} จอดทับลิมิตฝั่ง HEAD (Min) อยู่แล้ว -> รีเซ็ตพิกัดปัจจุบันเป็น 0.0 mm")
        return

    # สั่งลоจิกควบคุมและกลับทิศทางอัตโนมัติ
    if delta_mm > 0:
        _dir.on()          # ทิศเดินหน้า
        direction_flag = 1
        step_modifier = 1
        print(f"-> [แกน {axis_name.upper()}] เร่งสปีดวิ่งไปข้างหน้า -> เป้าหมายสัมบูรณ์: {target_mm:.1f} mm")
    else:
        _dir.off()         # ทิศถอยหลัง
        direction_flag = 0
        step_modifier = -1
        print(f"-> [แกน {axis_name.upper()}] เร่งสปีดวิ่งถอยหลัง -> เป้าหมายสัมบูรณ์: {target_mm:.1f} mm")

    total_steps = int(abs(delta_mm) * STEPS_PER_MM)
    time.sleep(0.005)

    START_DELAY = 0.0015  
    ACCEL_STEPS = 150 if total_steps > 300 else total_steps // 2
    
    is_aborted = False
    hit_min_limit = False 

    while select.select([sys.stdin], [], [], 0.0)[0]:
        sys.stdin.readline()

    for i in range(total_steps):
        if check_keyboard_stop() or estop_button.value:
            is_aborted = True
            break
            
        if direction_flag == 0 and lim_head.value:
            print(f"\n💥 [LIMIT MIN INTERRUPT]: แกน {axis_name.upper()} วิ่งเข้าชนเซนเซอร์ฝั่ง HEAD (Min)!")
            is_aborted = True
            hit_min_limit = True 
            break
            
        if direction_flag == 1 and lim_tail.value:
            print(f"\n💥 [LIMIT MAX INTERRUPT]: แกน {axis_name.upper()} วิ่งชนเซนเซอร์ฝั่ง TAIL (Max)!")
            is_aborted = True
            break

        if i < ACCEL_STEPS:
            current_delay = START_DELAY - ((START_DELAY - PULSE_DELAY_MAX) * (i / ACCEL_STEPS))
        else:
            current_delay = PULSE_DELAY_MAX

        pul.on()
        time.sleep(current_delay)
        pul.off()
        time.sleep(current_delay)

        current_positions[axis_name] += (step_modifier / STEPS_PER_MM)

    if is_aborted:
        pul.off()
        if hit_min_limit:
            current_positions[axis_name] = 0.0
            print(f"🔄 [AUTO-HOME]: คาริเบรตอัตโนมัติ $\rightarrow$ ตั้งค่าแกน {axis_name.upper()} เป็น 0.0 mm")
        print(f"🛑 แกน {axis_name.upper()} หยุดฉุกเฉินคาตำแหน่ง: {current_positions[axis_name]:.2f} mm\n")
    else:
        print(f"📍 สำเร็จ | ตำแหน่งปัจจุบันของแกน {axis_name.upper()}: {current_positions[axis_name]:.2f} mm\n")

# ====================================================
# 🏁 6. CONTROL LOOP TERMINAL INTERFACE
# ====================================================
print("=================================================================")
print("  ระบบควบคุมพิกัด 3 แกนตู้ Vending (พร้อมคำสั่ง xhome, yhome, zhome)  ")
print("=================================================================")
print("🎯 [รูปแบบคำสั่งใหม่บน Terminal]:")
print("-> พิมพ์ 'xhome' เพื่อสั่งแกน X วิ่งกลับไปชนลิมิตและปรับเป็นตำแหน่ง 0")
print("-> พิมพ์ 'yhome' เพื่อสั่งแกน Y วิ่งกลับไปชนลิมิตและปรับเป็นตำแหน่ง 0")
print("-> พิมพ์ 'zhome' เพื่อสั่งแกน Z วิ่งกลับไปชนลิมิตและปรับเป็นตำแหน่ง 0")
print("-> สั่งวิ่งพิกัด Absolute ปกติคงเดิม เช่น 'x150', 'y80' (ช่วง 0-200 mm)")
print("-> ขณะแกนกำลังวิ่งขยับ พิมพ์ 's' แล้ว Enter เพื่อเบรกฉุกเฉิน")
print("-----------------------------------------------------------------\n")

try:
    while True:
        pos_str = f"X: {current_positions['x']:.1f} | Y: {current_positions['y']:.1f} | Z: {current_positions['z']:.1f}"
        estop_status = "🚨 EMERGENCY ACTIVE" if estop_button.value else "🟢 NORMAL"
        
        user_input = input(f"ระบบ [{estop_status}] | พิกัด [{pos_str}] -> สั่งงาน: ").strip().lower()

        if user_input == 'q':
            print("กำลังปิดระบบควบคุมตู้จำหน่ายสินค้า...")
            break

        # 🏠 ตรวจจับคำสั่ง Homing ของแต่ละแกน
        if user_input in ['xhome', 'yhome', 'zhome']:
            axis = user_input[0] # ดึงอักษรตัวแรกออกมา เช่น 'x', 'y', 'z'
            execute_axis_homing(axis_name=axis)
            
        # 🎯 ตรวจจับคำสั่งพิกัด Absolute ปกติ
        elif user_input.startswith(('x', 'y', 'z')):
            axis = user_input[0]
            num_str = user_input[1:]
            try:
                val_mm = float(num_str)
                move_axis_absolute(axis_name=axis, target_mm=val_mm)
            except ValueError:
                print("❌ รูปแบบตัวเลขผิดพลาด กรุณาระบุเช่น 'x100'\n")
        else:
            if user_input != 's':
                print("❌ คำสั่งไม่ถูกต้อง พิมพ์ระบุเช่น 'xhome' หรือพิกัดพิกเซล 'x150'\n")

except KeyboardInterrupt:
    print("\nระงับการทำงานฉุกเฉินจากคีย์บอร์ด (Ctrl+C)")

finally:
    pul_x.close(); dir_x.close(); pul_y.close(); dir_y.close(); pul_z.close(); dir_z.close()
    lim_x_head.close(); lim_x_tail.close(); lim_y_head.close(); lim_y_tail.close(); lim_z_head.close(); lim_z_tail.close()
    estop_button.close()
    print("🔓 [Safe Shutdown] ปิดพินและคืนสิทธิ์พิน GPIO เรียบร้อย ระบบปลอดภัย 100% ครับ")