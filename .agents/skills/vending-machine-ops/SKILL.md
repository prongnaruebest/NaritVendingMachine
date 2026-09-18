---
name: vending-machine-ops
description: >-
  Use this skill whenever running commands on the Raspberry Pi, deploying software or firmware,
  restarting vending services, checking machine status, diagnosing hardware issues, or executing tests
  on the Narit Vending Machine.
---

# Narit Vending Machine Operations & Safety Runbook

Procedures, resource boundaries, and recovery runbooks for operating the physical Narit Vending Machine.

---

## 1. Raspberry Pi Resource & Testing Protection Rules

The controller runs on a Raspberry Pi CM4 with constrained memory and micro-SD/eMMC storage:

> [!CAUTION]
> **NEVER RUN `unittest discover` OR FULL TEST SUITES ON THE RASPBERRY PI!**
> Full test sweeps spawn numerous background services, threads, and databases that exceed RAM.
> This triggers aggressive swap thrashing on the SD card and causes `sshd` and user space to freeze
> (symptom: ping replies in 0ms, port 22 connects, but SSH hangs on banner exchange).

### How to Test Safely:
1. **Host-Side (Preferred)**: Run full unit test suites on the developer PC with mock hardware factories.
2. **Targeted Tests on Pi**: Run ONLY the single specific test file relevant to your change:
   ```bash
   .venv/bin/python3 -m unittest tests/test_specific_feature.py
   ```
3. **Always use explicit timeouts**:
   ```bash
   ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 pi@192.168.70.80 "command"
   ```

---

## 2. Safe Deployment & Service Management

### Service Units:
* `narit-vending-controller-iriv.service`: Owns hardware communication, NUCLEO serial, PiControl I/O, IPC socket (`/run/narit-vending/ctrl.sock`).
* `narit-vending-web-iriv.service`: Web interface & REST API listening on port 80.

### Standard Update Procedure:
```bash
# 1. Copy changed files to Pi
scp path/to/file pi@192.168.70.80:/home/admin/NaritVendingV1/path/to/file

# 2. Restart services
ssh pi@192.168.70.80 "sudo systemctl restart narit-vending-controller-iriv.service narit-vending-web-iriv.service"

# 3. Verify health
ssh pi@192.168.70.80 "systemctl is-active narit-vending-controller-iriv.service narit-vending-web-iriv.service; curl -s http://127.0.0.1/api/status | grep -o '\"machine_state\":\"[^\"]*\"'"
```

---

## 3. Hardware Diagnostic & Recovery Runbook

### Case A: Drive Error (Red LED flashing on HBS860H)
* **Diagnosis**: Closed-loop drive tripped position error or stall.
* **Resolution**:
  1. Trigger KM1 60V power cycle: Click **"QUICK RESET DRIVES (KM1)"** on System Control page or POST `/api/system/drives/reset-power`.
  2. Verify LED turns solid GREEN.
  3. Perform `HOME_ALL`.

### Case B: SSH Hangs on Banner Exchange (User Space Frozen)
* **Diagnosis**: RAM exhaustion or thrashing process holding I/O.
* **Resolution**:
  1. Have operator perform physical power cycle: **Power OFF machine $\rightarrow$ wait 5 seconds $\rightarrow$ Power ON**.
  2. The system will cleanly reboot and automatically restart all vending services.

### Case C: NUCLEO Communication Loss
* **Diagnosis**: USB serial disconnected or STM32 watchdog triggered.
* **Resolution**:
  1. Check `ls -la /dev/serial/by-id/`.
  2. Check ST-LINK mount `/media/pi/NOD_G491RE1`.
  3. Restart controller service: `sudo systemctl restart narit-vending-controller-iriv.service`.

---

## 4. Live Machine Safety Protocol (AGENTS.md)

* **NEVER automatically initiate real physical motion during deploy or testing.**
* Before issuing any live motion command (`move_to_slot`, `home`, `move`):
  1. State the exact axis, direction, and speed to the operator.
  2. Obtain explicit operator confirmation that the machine envelope is clear and safe.
