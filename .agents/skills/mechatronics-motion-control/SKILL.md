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

* **Recommended Operating Speed**:
  * **Homing Search**: $50.0 \text{ mm/s}$ ($\sim 121 \text{ RPM}$, $3,235 \text{ Hz}$) — Proven rock-solid.
  * **Homing Latch / Crawl**: $5.0 \text{ mm/s}$ ($\sim 12 \text{ RPM}$, $324 \text{ Hz}$).
  * **Normal Dispense / Goto Slot**: $50.0 - 80.0 \text{ mm/s}$ ($121 - 194 \text{ RPM}$, $3,235 - 5,176 \text{ Hz}$).
  * **Absolute Upper Bound**: $100.0 \text{ mm/s}$ ($242 \text{ RPM}$, $6,470 \text{ Hz}$).
  * **DO NOT USE**: $>120 \text{ mm/s}$ ($>300 \text{ RPM}$). Config values of 250 mm/s (>600 RPM) will stall!

* **Acceleration & Deceleration**:
  * Keep `acceleration` and `deceleration` between $100.0 - 150.0 \text{ mm/s}^2$ ($6,470 - 9,705 \text{ Hz/s}$).
  * Never configure $>200 \text{ mm/s}^2$ without load verification.

* **Jerk**:
  * Keep between $100.0 - 500.0 \text{ mm/s}^3$. Never set $1,500+ \text{ mm/s}^3$.

---

## 3. Direction Polarity Standards

The machine hardware wiring enforces:

* **Forward Direction (`forward_direction = 0`)**:
  * Drives physical DIR pin **LOW (`GPIO_PIN_RESET`)**.
  * Direction of positive displacement ($+X, +Y$ away from Home towards slots).
* **Home / Reverse Direction (`home_direction = 1`)**:
  * Drives physical DIR pin **HIGH (`GPIO_PIN_SET`)**.
  * Direction of negative displacement ($-X, -Y$ back towards Home limit switches).

Every firmware HAL hook (`NucleoG491ProfileHal_PrepareDirectionHook`) and controller driver (`Stepper_Move`) must preserve:
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

* **Multi-Axis Coordinated Moves (`move_to_slot`, multi-axis `move`)**:
  * Keep `scurve_enabled: false` in `machine_config.iriv.json` so motion routes to `backend.move_parallel()`.
  * `move_parallel()` executes standard `MOVE` protocol v3 frames at the exact operator-commanded speed matching `duration_s`.
* **Single-Axis Moves (`move_mm`, `move_to_mm`)**:
  * Routes to `AxisController._execute_plan()`, which executes `backend.move()` directly.
