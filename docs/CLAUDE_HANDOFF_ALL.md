# Claude Handoff — NARIT VENDING Remaining Work

## 1. Mission

รับช่วงพัฒนาโปรเจกต์ **NARIT VENDING Industrial Gantry HMI** ทั้งหมดต่อจากสถานะปัจจุบัน โดยเน้นความปลอดภัยของ Motion Control, ความถูกต้องของ configuration, ความเสถียรของ Raspberry Pi และ MQTT monitoring/control boundary

อย่าเริ่มจากการ redesign ใหม่ทั้งหมด ให้ตรวจและต่อยอดโค้ดปัจจุบันแบบ incremental พร้อมรักษา API และหน้า HMI ที่มีอยู่

## 2. Project Access

- Windows workspace: `C:\Users\Naruebest\OneDrive\Documents\NaritVending`
- Git branch: `main`
- Raspberry Pi SSH alias: `narit-pi`
- Pi project: `/home/admin/NaritVending`
- HMI: `http://naritvendingmachine/`
- systemd: `narit-vending-web.service`
- Pi MQTT secrets: `/etc/narit-vending.env`

ห้ามแสดง คัดลอก commit หรือบันทึก password/token/private key ลง repository, log, API หรือเอกสาร handoff

## 3. Current Git State

Latest committed revision at handoff time:

```text
6bf0407 feat(mqtt): add TLS config, improve rc error messages, add exponential backoff
```

`origin/main` อยู่ที่ revision เดียวกัน แต่ยังมีงาน Phase 1 และ MQTT HMI ที่ **ยังไม่ commit**:

```text
M  README.md
M  deploy/narit-vending-web.service
M  narit_vending/static/app.js
M  narit_vending/static/style.css
M  narit_vending/templates/index.html
M  narit_vending/webapp.py
?? ARCHITECTURE_PROPOSAL_TH.md
?? CLAUDE_MQTT_HANDOFF.md
?? narit_vending/config_foundation.py
?? scripts/validate_config.py
?? tests/__init__.py
?? tests/test_config_foundation.py
?? tests/test_health_api.py
?? tests/test_motion_characterization.py
?? tests/test_startup_smoke.py
```

`.vscode/` เป็น local editor settings ให้ตรวจ `.gitignore` ก่อนตัดสินใจ commit

### Mandatory first action

1. ห้ามใช้ `git reset --hard`, `git clean`, checkout ทับ หรือ discard งานข้างต้น
2. สร้าง ZIP backup ของ worktree ปัจจุบันก่อนแก้
3. อ่าน diff ทั้งหมดและรัน tests ก่อน refactor
4. แยก commit ตามหัวข้อ ห้ามรวม hardware tuning, architecture refactor และ UI redesign ไว้ commit เดียว

## 4. Hardware Baseline

### X axis

- Motor: `60BYG250C`
- Driver: `DM542`
- Supply: `24 V`
- DIP SW1–SW8 reported by user: `11000111`
- Enable polarity: Active Low
- Pulse/Direction/Enable GPIO: `16 / 23 / 12`
- Effective travel/speed: `220 mm / 20 mm/s`

### Y axis

- Motor: `23KM-K041BN02CA`
- Driver: `DM542`
- Supply: `24 V`
- DIP SW1–SW8 reported by user: `10100111`
- Enable polarity: Active Low
- Pulse/Direction/Enable GPIO: `26 / 24 / 13`
- Effective travel/speed: `260 mm / 15 mm/s`

### Z axis

- Motor: NEMA 11 `CTM28`, rated `0.5 A`
- Driver: `DM442`
- Supply: `24 V`
- DIP SW1–SW8 reported by user: `11100111`
- Enable polarity: Active Low
- Pulse/Direction/Enable GPIO: `18 / 25 / 19`
- Effective travel/speed: `200 mm / 20 mm/s`

### Mechanics and pulse baseline

- X/Y lead screw reported: `MTSRL25-1800`, diameter 25 mm, pitch `5 mm`, length about 2 m
- Current configured motor full steps: `200 steps/rev`
- Current configured microsteps: `2`
- Current configured pulse calculation: `400 pulses/rev`, `80 pulses/mm`
- User accepted motor-test speed: `2000 Hz` for X/Y/Z
- Motor Test Mode is hold-to-run and intended for unloaded/maintenance testing only

Do not assume DIP switch interpretation is correct without checking the exact DM442/DM542 label/manual and measuring actual travel. Verify commanded 10 mm against physical displacement before production movement.

## 5. Effective Configuration Warning

Current configuration validates with zero errors but four warnings. `hardware_config.json` overrides `machine_config.json` for Y:

- Y head limit: machine `GPIO 9`, effective `GPIO 22`
- Y tail limit: machine `GPIO 22`, effective `GPIO 9`
- Y home direction: machine `1`, effective `0`
- Y forward direction: machine `0`, effective `1`

Do not silently normalize these values. Confirm physical sensor locations and motion direction with the user, then make one file the authoritative owner and migrate safely with backup/checksum.

## 6. Current Application Features

- Dashboard overview and shared header status
- Motion Control with homing, target validate/preview/arm/execute, stop/abort, feed override and jog
- Visualization with 6×5 slot map and selected-slot workflow
- Slot Manager with save/edit/reset positions
- Diagnostics, Alarms, Event Logs and System Flow workspaces
- Configuration page for motor, pulse, GPIO and sensors
- Dedicated Motor Test Mode
- MQTT Monitor workspace with one-second API polling
- Health endpoints and effective configuration reporting
- Config backup/restore foundation and startup validation
- Deploy script preserving Pi machine/hardware config

## 7. Current Raspberry Pi Runtime

At handoff time:

- `narit-vending-web.service`: active
- `/health/live`: UP
- `/health/ready`: service ready, config valid, machine not ready because axes are not homed
- HMI and API return HTTP 200
- MQTT enabled, client available, authentication configured
- MQTT broker currently configured as `192.168.70.30:1883`
- Cabinet ID: `CAB-001`
- MQTT state: `CONNECTION_LOST`
- Broker return code: `rc=5`
- No received/published MQTT messages yet

The latest MQTT TLS/error/backoff commit may not yet be deployed. Compare local revision and remote source before deployment.

## 8. MQTT Contract

Topics for `CAB-001`:

- Publish: `cabinet/CAB-001/scan`
- Subscribe: `cabinet/CAB-001/command`
- Publish: `cabinet/CAB-001/status`
- Publish retained presence/LWT: `cabinet/CAB-001/presence`

Current `rc=5` means authorization was rejected. Do not brute-force. Confirm with broker administrator:

- current hostname/IP and port
- MQTT TCP versus MQTT over TLS/WebSocket
- username/password or certificate authentication
- CA/client certificate paths
- ACL permissions for all four topics
- whether client ID `CAB-001` is allowed and unique

Read `CLAUDE_MQTT_HANDOFF.md` for the detailed MQTT checklist.

## 9. Safety Invariants

Every HTTP, MQTT, HMI or internal motion command must pass the same central safety path.

- Never bypass physical E-Stop
- Never move when controller/API data is stale or unknown
- Never show READY when E-Stop is active, an alarm/limit fault exists, config is invalid, or required axes are not homed
- Never allow MQTT to drive GPIO directly
- STOP/E-STOP must not wait behind a normal command queue
- Validate soft limits, direction, position, pulse count, speed, timeout and command state before movement
- Motor Test Mode must remain isolated from normal automatic operation
- Require explicit hold-to-run behavior, timeout/watchdog, audit event and immediate release stop
- CI/tests must use mock GPIO only and must never move real hardware automatically
- Do not change pins, polarity, DIP settings, steps/mm, acceleration or slot coordinates without explicit user approval and backup

## 10. Remaining Work — Priority Order

### P0 — Protect the current baseline

1. Back up the full worktree and Pi project/config.
2. Review and commit the current uncommitted Phase 1 + MQTT HMI changes in focused commits.
3. Run config validation and resolve only confirmed Y-axis ownership conflicts.
4. Add explicit safety invariant tests for E-Stop, stale API, limits, homing, alarm and config-invalid states.
5. Verify all navigation workspaces and shared header status still update once per second.
6. Verify Motor Test Mode cannot overlap normal motion, homing or MQTT command execution.

### P0 — Phase 2 state and command foundation

1. Implement an explicit machine state model and guarded transitions:
   - BOOTING
   - CONFIG_REQUIRED
   - NOT_READY
   - READY
   - HOMING
   - MOVING
   - DISPENSING
   - MOTOR_TEST
   - CONTROLLED_STOP
   - ALARM
   - E_STOP
2. Add `CommandEnvelope` with command ID, source, type, payload, requested time, timeout and idempotency key.
3. Add an in-memory Command Bus and command audit repository.
4. Translate legacy HTTP routes into the Command Bus while preserving responses.
5. Route MQTT through the same Command Bus and SafetyInterlock.
6. Add immediate priority paths for STOP and E-STOP.
7. Add duplicate/stale command rejection and command-result correlation.

### P1 — Motion decomposition

1. Split `motion.py` responsibilities into axis model, pulse generator, trajectory planner, homing, coordinated motion and motor-test service.
2. Keep current gpiozero behavior behind a `PulseGenerator` interface.
3. Add cancellation, watchdog and timing metrics.
4. Characterize Python pulse jitter under Raspberry Pi CPU load.
5. Evaluate pigpio or another hardware-timed backend behind a feature flag only after bench tests.
6. Verify acceleration/deceleration produces smooth movement at 2000 Hz without losing steps.
7. Calibrate real steps/mm and direction for all axes with load disconnected first, then low-speed loaded tests.

### P1 — MQTT completion

1. Resolve the broker `rc=5` using current authorized credentials/ACL.
2. Verify TLS mode and certificates if required.
3. Deploy the latest TLS/reason-code/backoff implementation.
4. Verify presence/LWT, reconnect behavior and topic permissions.
5. Define and validate JSON schemas for command/status payloads.
6. Add command ID, timestamp expiry, cabinet validation, idempotency and audit.
7. Keep Cloud/MQTT motion control disabled until the Command Bus and safety path pass acceptance tests.

### P1 — Durable operational data

The HMI still displays `NO DATA` for values without backend repositories. Implement real persistence instead of random/mock data:

- completed/failed cycles and success rate
- latest/average cycle time
- operating time and motor runtime X/Y/Z
- movement cycle count
- maintenance dates and inspection status
- drive feedback/following error if hardware supports it
- durable alarms and event history
- command history and result

SQLite is acceptable initially. Add schema migration, retention and backup.

### P2 — API and repository architecture

1. Add versioned `/api/v1` endpoints while keeping legacy routes temporarily.
2. Separate slots, commands, alarms, events, maintenance and config repositories.
3. Split Flask route registration from parsing/application logic.
4. Reduce `/api/status` payload and expose focused resources.
5. Add consistent error codes, timestamps, request IDs and API schemas.
6. Restrict CORS and plan authentication/roles for engineering/config pages.

### P2 — Frontend modularization and HMI QA

1. Split the monolithic `app.js` by workspace, API client, state store and shared render utilities.
2. Keep header status identical on every page.
3. Ensure offline API changes all live values to UNKNOWN/OFFLINE.
4. Do not use color alone; retain labels/icons.
5. Keep Dashboard observational; no direct motion command.
6. Slot click on Visualization selects only; movement requires explicit GOTO/arm workflow.
7. Confirm all panels have internal scrolling where intended and no horizontal page overflow.
8. Browser-test 1280×720, 1600×900 and 1920×1080.
9. Preserve the dark-blue industrial engineering theme and readable font sizes.

### P1/P2 — Deployment hardening

1. Replace in-place copy deployment with versioned release directories.
2. Use atomic `current`/`previous` symlinks and automatic health rollback.
3. Keep machine/hardware config and data outside release directories.
4. Retain at least three releases and rotate backups.
5. Move systemd away from root only after GPIO permissions are proven.
6. Add startup timeout, failure health gate and sanitized logs.
7. Perform cold boot, service restart, network loss, MQTT loss, E-Stop and rollback drills.

## 11. Testing Required Before Every Pi Deployment

```powershell
cd C:\Users\Naruebest\OneDrive\Documents\NaritVending
.\.venv\Scripts\python.exe -m ruff check narit_vending scripts\validate_config.py tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node --check narit_vending\static\app.js
.\.venv\Scripts\python.exe scripts\validate_config.py --output tmp\config-report.json
```

Do not treat `machine_ready=false` as a service deployment failure when axes are intentionally not homed. `/health/live`, `service_ready`, config validity and systemd state are the software health gate.

## 12. Backup and Deployment

Create a backup first:

```powershell
$timestamp = Get-Date -Format yyyyMMdd_HHmmss
ssh narit-pi "mkdir -p /home/admin/NaritVending_backups && tar -czf /home/admin/NaritVending_backups/pre_deploy_$timestamp.tar.gz -C /home/admin NaritVending"
```

Deploy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_to_pi.ps1
```

Verify:

```powershell
ssh narit-pi "systemctl is-active narit-vending-web.service"
ssh narit-pi "journalctl -u narit-vending-web.service -n 100 --no-pager"
Invoke-RestMethod http://naritvendingmachine/health/live
Invoke-RestMethod http://naritvendingmachine/health/ready
Invoke-RestMethod http://naritvendingmachine/api/mqtt/status
```

Never print `/etc/narit-vending.env` during verification.

## 13. Acceptance Gates

### Software

- Ruff, unit tests, JS syntax and config validation pass
- No frontend console errors or navigation regressions
- No horizontal overflow at supported resolutions
- API disconnect produces UNKNOWN/OFFLINE, not stale READY
- systemd remains active without traceback

### Motion bench

- Correct enable polarity and direction on X/Y/Z
- Exact pulse count and measured travel calibration
- Home sensors and min/max limits stop movement correctly
- E-Stop interrupts every motion source immediately
- Smooth acceleration/deceleration at accepted operating frequency
- No simultaneous normal motion and Motor Test Mode

### MQTT

- HMI reports CONNECTED from live data
- ACL permits only expected cabinet topics
- Presence/LWT and reconnect behavior verified
- Duplicate, stale, malformed and unsafe commands are rejected
- No secret appears in API, UI, repository or logs

## 14. Key Documents

- `ARCHITECTURE_PROPOSAL_TH.md` — target architecture and migration phases
- `ARCHITECTURE_TH.md` — current architecture/manual
- `ARCHITECTURE.html` — operator manual presentation
- `API_DOCS.md` and `API_DOCS.html` — existing API documentation
- `CLAUDE_MQTT_HANDOFF.md` — MQTT-specific handoff
- `README.md` — install, run, deploy and current features

## 15. Starting Instruction for Claude

```text
Read CLAUDE_HANDOFF_ALL.md, CLAUDE_MQTT_HANDOFF.md, ARCHITECTURE_PROPOSAL_TH.md and git diff before editing.
Preserve every uncommitted file and create a backup first.
Run the current tests to establish a baseline.
Start with P0 only: protect/commit the existing Phase 1 and MQTT HMI work, verify configuration and safety invariants, then present the proposed Phase 2 file changes before modifying runtime motion behavior.
Never expose MQTT secrets and never move real motors automatically during tests.
```

