---
name: mechatronics-motion-control
description: >-
  Use this skill whenever working on motion planning, stepper motor sizing, speed/acceleration tuning,
  lead screw kinematics, closed-loop stepper drives (HBS860H), pulse frequencies, RPM conversions, or
  direction polarity for the Narit Vending Machine.
---

# Mechatronics Motion Control Skill (Narit Vending Machine)

Expert knowledge and operational boundaries for industrial stepper motion control on the Narit Vending Machine.

---

## 1. Kinematic Constants & Conversion Formulas

The machine uses NEMA hybrid stepper motors driven by Leadshine/StepperOnline HBS860H closed-loop drives:

* **Motor Step Angle**: 1.8° (200 full steps per revolution)
* **Driver Microstepping**: 8 microsteps (DIP switches configured for 1,600 pulses/rev)
* **Pulses per Revolution (PPR)**:
  $$\text{PPR} = 200 \times 8 = 1,600 \text{ pulses/rev}$$

### Axis Kinematics:

| Axis | Drive Mechanism | Pitch / Travel per Rev | Pulses per mm (`steps_per_mm`) |
| :--- | :--- | :--- | :--- |
| **X** | Lead Screw | $24.727273 \text{ mm/rev}$ | $64.705882 \text{ pulses/mm}$ |
| **Y** | Lead Screw | $24.727273 \text{ mm/rev}$ | $64.705882 \text{ pulses/mm}$ |
| **Z** | Timing Belt | $177.777778 \text{ mm/rev}$ | $9.000000 \text{ pulses/mm}$ |

### Conversion Formulas:

* **Linear Speed $\rightarrow$ RPM**:
  $$\text{RPM} = \frac{\text{speed\_mm\_s} \times 60}{\text{pitch\_mm}} = \text{speed\_mm\_s} \times 2.4265 \quad (\text{for X and Y})$$
* **RPM $\rightarrow$ Linear Speed**:
  $$\text{speed\_mm\_s} = \frac{\text{RPM} \times \text{pitch\_mm}}{60} = \text{RPM} \times 0.41212 \quad (\text{for X and Y})$$
* **Linear Speed $\rightarrow$ Pulse Frequency (Hz)**:
  $$\text{pulse\_hz} = \text{speed\_mm\_s} \times \text{steps\_per\_mm} = \frac{\text{RPM} \times 1,600}{60} = \text{RPM} \times 26.667$$

---

## 2. Safe Operating Envelopes (Speed, Accel, Jerk)

> [!CAUTION]
> Stepper motors lose torque rapidly at higher rotational speeds. On heavy lead-screw carriages, commanding speeds above 120 mm/s (>300 RPM) or accelerations above 200 mm/s² will cause the rotor to lag behind the stator field, tripping HBS860H position error alarms.

The repository currently records `commissioned_max_speed_mm_s = 210.0` for X/Y,
but the repository does not contain the raw external measurement, ALM/PEND trace,
or encoder evidence needed to treat that value as independently verified. Never
convert a configured ceiling or driver pulse-input rating into a mechanical-safe
speed claim.

* **Commissioning entry speed**: Start each single-axis test at or below
  $20.0 \text{ mm/s}$ with the operator at the machine, then increase only after
  external distance, ALM, PEND, limits and mechanical behavior pass.
* **Current conservative operating values (not a substitute for a new commissioning gate)**:
  * **X/Y Homing Search**: $20.0 \text{ mm/s}$ ($\sim 48.5 \text{ RPM}$, $1,294 \text{ Hz}$). This lower legacy-path entry speed mitigates the observed HBS860H 7-flash following error caused by a frequency step without an acceleration ramp.
  * **Z Homing Search**: $50.0 \text{ mm/s}$ on its separately commissioned belt/DM542 mechanism.
  * **Homing Latch / Crawl**: $5.0 \text{ mm/s}$ ($\sim 12 \text{ RPM}$, $324 \text{ Hz}$).
  * **Normal Dispense / Goto Slot**: $50.0 - 80.0 \text{ mm/s}$ ($121 - 194 \text{ RPM}$, $3,235 - 5,176 \text{ Hz}$).
  * Values above $100.0 \text{ mm/s}$ require a recorded commissioning result;
    do not infer safety from the current 210/250 mm/s configuration fields.

* **Acceleration & Deceleration**:
  * Keep `acceleration` and `deceleration` between $100.0 - 150.0 \text{ mm/s}^2$ ($6,470 - 9,705 \text{ Hz/s}$).
  * Never configure $>200 \text{ mm/s}^2$ without load verification.

* **Jerk**:
  * Keep between $100.0 - 500.0 \text{ mm/s}^3$. Never set $1,500+ \text{ mm/s}^3$.

---

## 3. Direction Polarity Standards

The machine hardware wiring enforces the following physical pin levels, but the
wire-level direction number is not shared between both protocol paths:

* **Legacy `MOVE` forward (`forward_direction = 0`)**:
  * Drives physical DIR pin **LOW (`GPIO_PIN_RESET`)**.
  * Direction of positive displacement ($+X, +Y$ away from Home towards slots).
* **Legacy Home / Reverse (`home_direction = 1`)**:
  * Drives physical DIR pin **HIGH (`GPIO_PIN_SET`)**.
  * Direction of negative displacement ($-X, -Y$ back towards Home limit switches).

* **Dynamic absolute target**: the firmware planner uses `direction = 1` for a
  positive target delta and maps it to physical LOW; `direction = 0` means a
  negative target delta and maps to physical HIGH. This positional semantic is
  intentionally different from the legacy configuration enum.

Do not copy one path's direction number into the other. Preserve the physical
mapping already characterized by the firmware tests:
```c
HAL_GPIO_WritePin(port, pin, (direction != 0U) ? GPIO_PIN_RESET : GPIO_PIN_SET);
```

---

## 4. HBS860H Closed-Loop Driver Diagnostics

The HBS860H drive indicates faults via a flashing red LED:

| Red LED Flashes | Fault Name | Root Cause | Corrective Action |
| :---: | :--- | :--- | :--- |
| **1 Flash** | Over-current | Short circuit or coil overload | Inspect motor phase wiring and driver terminals |
| **2 Flashes** | Over-voltage | Regenerative deceleration surge | Add bleeder/braking resistor or reduce deceleration rate |
| **7 Flashes** | **Position Following Error (Rotor Stall)** | Motor lagged commanded pulses by $>4,000$ encoder counts | 1. Reduce commanded speed ($\le 80 \text{ mm/s}$)<br>2. Reduce acceleration ($\le 150 \text{ mm/s}^2$)<br>3. Check for mechanical binding or DIR inverted |

### Fault Recovery:
Once the drive trips any alarm, it disconnects motor coil power. The drive **cannot self-recover**. It must be power-cycled via the KM1 60V power contactor:
- Command: `POST /api/system/drives/reset-power`
- UI: Click **"QUICK RESET DRIVES (KM1)"** on the System Control page.

---

## 5. Motion Routing Invariant

* X/Y currently use `scurve_enabled: true`, but dynamic routing is allowed only
  after the USB handshake reports protocol v4 and the complete capability set,
  including `dynamic_motion`.
* Coordinated X/Y moves configure the planner with each axis's planned speed;
  do not replace these with one scalar maximum.
* Z and host-supervised Home/limit seeking remain on the legacy motion path.
* Protocol v3 or an incomplete capability handshake must not be treated as
  dynamic-profile support; use the characterized fallback or reject the command
  according to the owning routing policy.
