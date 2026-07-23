# Claude Handoff: NARIT VENDING MQTT Monitor

## Role

You are a Senior Industrial IoT/MQTT Engineer, Python Backend Engineer, and HMI/SCADA Engineer.

## Project

- Local workspace: `C:\Users\Naruebest\OneDrive\Documents\NaritVending`
- Raspberry Pi SSH target: `narit-pi`
- Remote project: `/home/admin/NaritVending`
- Web service: `narit-vending-web.service`
- HMI URL: `http://naritvendingmachine/`
- MQTT workspace URL: `http://naritvendingmachine/#mqtt`

## Current Implementation

- `narit_vending/mqtt_service.py`
  - MQTT client and cabinet topic adapter.
  - Reads normal settings from `hardware_config.json`.
  - Explicit `NARIT_MQTT_*` environment variables override file settings.
  - Sanitizes passwords, tokens, and secrets before sending telemetry to the HMI.
  - Records connection state, counters, timestamps, errors, topics, and recent messages.
- `narit_vending/webapp.py`
  - Provides `GET /api/mqtt/status`.
- `narit_vending/templates/index.html`
  - Contains a dedicated MQTT Monitor workspace.
- `narit_vending/static/app.js`
  - Polls MQTT telemetry every second and renders the monitor.
- `narit_vending/static/style.css`
  - Contains the responsive dark-blue MQTT monitor layout.
- `deploy/narit-vending-web.service`
  - Loads `EnvironmentFile=-/etc/narit-vending.env`.
- `/etc/narit-vending.env` on the Pi
  - Stores MQTT connection settings outside source control.
  - File permissions must remain `600 root:root`.
  - Never print or expose its password in logs, API responses, commits, or chat.

## MQTT Topic Contract

For cabinet ID `CAB-001`:

- `cabinet/CAB-001/scan`
- `cabinet/CAB-001/command`
- `cabinet/CAB-001/status`
- `cabinet/CAB-001/presence`

Do not change this contract without checking the external MQTT server implementation.

## Current Runtime State

- Deployment completed successfully.
- `narit-vending-web.service` is active.
- HMI and `/api/mqtt/status` return HTTP 200.
- MQTT is enabled and authentication is configured.
- Current MQTT state: `CONNECTION_LOST`.
- Broker response: `Unexpected disconnect (rc=5)`.
- MQTT return code 5 means the broker rejected authorization/authentication.
- Do not brute-force credentials.
- Obtain the current broker hostname, port, username, password, TLS requirements, and ACL/topic permissions from the broker administrator.

## Required Work

1. Inspect the current implementation and tests before editing.
2. Verify the external broker settings without exposing credentials.
3. Determine whether the broker requires MQTT over TLS, a CA certificate, client certificate, WebSocket transport, or a non-default port.
4. Add optional TLS configuration if required:
   - `NARIT_MQTT_TLS_ENABLED`
   - `NARIT_MQTT_CA_CERT`
   - `NARIT_MQTT_CLIENT_CERT`
   - `NARIT_MQTT_CLIENT_KEY`
   - `NARIT_MQTT_TLS_INSECURE` must default to false.
5. Keep environment variables higher priority than `hardware_config.json`.
6. Improve connection reason text so rc=4/5 clearly shows authentication/authorization failure.
7. Confirm subscriptions and publish permissions for all four cabinet topics.
8. Confirm retained presence behavior and Last Will message.
9. Confirm reconnect backoff does not create a rapid reconnect loop.
10. Keep all MQTT status data sanitized in `/api/mqtt/status`.
11. Add or update unit tests for configuration precedence, TLS, callbacks, sanitization, and reconnect telemetry.
12. Run Ruff, unit tests, and JavaScript syntax validation.
13. Back up the Pi project before deployment.
14. Deploy with `scripts/deploy_to_pi.ps1`.
15. Verify systemd, health endpoints, MQTT status, subscriptions, and recent messages after deployment.

## Safety Constraints

- MQTT commands must pass through the existing motion safety checks.
- Never bypass E-Stop, homing, limit switches, interlocks, alarm state, or motion validation.
- Never allow an MQTT command to drive GPIO directly.
- Never execute a movement command solely because a message was received.
- Validate cabinet ID, command schema, command ID, slot, coordinates, timeout, and duplicate command IDs.
- Reject malformed, stale, unauthorized, or duplicate commands and publish a clear status response.
- Do not modify motor pin assignments, polarity, pulse parameters, or saved slot coordinates unless explicitly requested.

## Validation Commands

```powershell
cd C:\Users\Naruebest\OneDrive\Documents\NaritVending
.\.venv\Scripts\python.exe -m ruff check narit_vending tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node --check narit_vending\static\app.js
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_to_pi.ps1
ssh narit-pi "systemctl is-active narit-vending-web.service"
ssh narit-pi "journalctl -u narit-vending-web.service -n 80 --no-pager"
```

## Acceptance Criteria

- HMI MQTT page reports `CONNECTED` from live API data.
- Broker, cabinet ID, topics, connection timestamps, counters, and recent messages display correctly.
- No password, token, certificate private key, or full sensitive payload appears in UI/API/logs.
- Publish and subscribe tests succeed for the expected cabinet topics.
- Service reconnects safely after broker interruption.
- Navigation and all existing HMI workspaces continue to function.
- `narit-vending-web.service` remains active without tracebacks.

