# Current Architecture Baseline

Baseline commit: `6909d5d`  
Baseline tag: `refactor-baseline-20260908-203016`

## Runtime topology

```text
Browser (Flask HTML/CSS/JS)
        |
        | HTTP/JSON
        v
narit-vending-web-iriv.service
  narit_vending.web
        |
        | Unix-domain IPC / CommandEnvelope
        v
narit-vending-controller-iriv.service
  CommandBus -> SafetyInterlock -> command handler -> MotionService
        |                    |             |
        |                    |             +-> SQLite demo history
        |                    +-> MachineSnapshot / StateMachine
        +-> NUCLEO USB v3, IRIV Modbus TCP, PiControl local I/O
```

The deployed production path already separates the web process from the Controller. The web process uses `ControllerClient`; the Controller owns the instantiated hardware adapters and motion objects.

## Hardware ownership

| Resource | Current owner | Transport |
|---|---|---|
| STEP/DIR X/Y/Z | Controller through `NucleoLink` | USB serial protocol v3 |
| Travel and Home sensors | Controller through `IRIVIOBackend` | Modbus TCP |
| X/Y ALM and PEND | Controller through `PiControlIOBackend` | Local isolated DI |
| X/Y drive power KM1 | Controller through `PiControlIOBackend` | Local DO0 |
| Demo results | Controller `DemoSamplingService` | SQLite |
| HMI rendering | Web process | Read-only snapshot plus command submission |

## Existing boundaries

- `narit_vending/shared/commands.py` defines immutable `CommandEnvelope` and `CommandResult`.
- `narit_vending/controller/command_bus.py` serializes motion commands and invokes the central safety gate.
- `narit_vending/controller/safety.py` contains a mostly pure safety decision function.
- `narit_vending/shared/snapshot.py` is the web/controller state contract.
- `narit_vending/web/routes/` is the deployed HTTP boundary.
- `narit_vending/webapp.py` remains a 1,970-line legacy composition root and business-service implementation used inside the Controller.
- `narit_vending/motion.py` remains a 1,771-line mixed domain/planning/execution/hardware-construction module.
- Frontend implementation is concentrated in `static/app.js` (about 5,010 lines), `static/style.css` (about 8,440 lines), and one HTML template (about 1,697 lines).

## Current state sources

Machine authority is held by Controller memory and hardware feedback. Browser state is presentation state only. Configuration has machine and hardware files plus an effective configuration report. Demo history is persistent; axis Home state is intentionally volatile and clears after Controller restart or drive-power loss.

## Compatibility boundary

`narit_vending/webapp.py:create_app()` exposes a legacy monolithic Flask route set in addition to the deployed `narit_vending.web` route set. Tests still exercise both paths. It must remain behind characterization tests while functionality is extracted; deleting it before consumers are migrated would create silent API regressions.

## Baseline quality status

- Automated suite before structural extraction: 190 tests passed and 18 subtests passed.
- Production health before refactor: Web, Controller, NUCLEO USB, IRIV I/O and PiControl I/O online.
- Automated tests do not issue real motion.
- Mechanical motion, PEND polarity and maximum-speed behavior remain operator acceptance items.
