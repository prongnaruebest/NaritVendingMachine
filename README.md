# Narit Vending Motion Control

Motion control base for a Raspberry Pi vending machine with `X/Y/Z` axes, head/tail limit switches on every axis, and a hardware emergency stop input.

## Files

- `narit_vending/motion.py`: motor, homing, limit, travel, and slot-position logic
- `narit_vending/cli.py`: CLI for `status`, `home`, `jog`, `move`, and `goto-slot`
- `narit_vending/webapp.py`: Flask web server and JSON API
- `main.py`: CLI entry point
- `machine_config.json`: per-axis travel, `steps_per_mm`, jog sizes, and slot positions
- `deploy/narit-vending-controller.service`: systemd service for motion controller process
- `deploy/narit-vending-web.service`: systemd service for web monitor process
- `scripts/deploy_to_pi.ps1`: deploy this project from Windows to Raspberry Pi over SSH
- `scripts/setup_pi.sh`: install runtime dependencies on the Pi
- `docs/`: architecture specifications, proposals, and API documentation

## Features

- 3-axis step/dir control using `gpiozero`
- 6 limit switch inputs plus 1 external E-stop input
- Per-axis `steps_per_mm`, `max_travel_mm`, and `jog_step_mm`
- `home_all()` using configurable axis order
- Absolute movement in millimeters after homing
- Configured slot map for `1-30`
- Manual jog mode with keyboard control
- Web UI with realtime axis status and slot editing

## Default Keyboard Jog

- `a` / `d`: X minus / plus
- `s` / `w`: Y minus / plus
- `f` / `r`: Z minus / plus
- `h`: home all axes
- `p`: print status
- `q`: quit jog mode

## Install On Raspberry Pi

```bash
cd /home/admin/NaritVending
chmod +x scripts/setup_pi.sh
./scripts/setup_pi.sh
```

## Run

```bash
python3 main.py status
python3 main.py home
python3 main.py jog
python3 main.py move --x 10 --y 25 --z -2
python3 main.py goto-slot 1
```

## Deploy From Windows Through SSH

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_to_pi.ps1
```

The deploy script copies the project to `/home/admin/NaritVending` on host `narit-pi`, then runs the Pi setup script remotely.

## Web UI

After setup, the Raspberry Pi runs a web server automatically at boot.

- Preferred URL: `http://NaritVendingMachine.local/`
- On networks with hostname resolution: `http://NaritVendingMachine/`

The web page provides:

- realtime X/Y/Z positions
- per-axis `Home X`, `Home Y`, `Home Z`, plus `Home All`
- manual jog buttons
- slot buttons `1-30`
- save current position into any slot
- edit slot X/Y/Z values manually and save them

## Configuration Notes

Edit `machine_config.json` to tune:

- `steps_per_mm` for each axis
- `max_travel_mm` for software travel limits
- `jog_step_mm` for manual movement
- `slots` for positions `1-30`
- `safe_z_mm` for the height used before XY travel

Before every configuration save, the service writes a timestamped copy of both JSON files under
`backups/config/`. The active merged values and override warnings are available from:

```text
GET /api/config/effective
```

## Health Checks

- `GET /health/live`: confirms that the Flask process is responding
- `GET /health/ready`: confirms that configuration is valid and the service can accept requests

`service_ready` is intentionally separate from `machine_ready`. A machine that has not been homed
can still pass the deployment readiness check without being reported as ready for motion.

Validate configuration without opening GPIO devices:

```bash
python scripts/validate_config.py
```

## MQTT Monitor

Open `/#mqtt` or select **MQTT Monitor** under System Views. The monitor refreshes every second and shows:

- broker connection state, address, keepalive and session timestamps
- cabinet client ID and subscribed/published topics
- RX/TX/command/rejected-message counters
- the latest 100 MQTT messages with password and token fields redacted
- the latest connection or payload error

The same sanitized telemetry is available from `GET /api/mqtt/status`. MQTT credentials are never
returned by this endpoint.

## Important Hardware Notes

- If an axis moves in the wrong direction, swap `home_direction` and `forward_direction`
- If a limit switch reads inverted, update the input handling or wiring
- Tune `pulse_delay` to match your driver and reliable motor speed
