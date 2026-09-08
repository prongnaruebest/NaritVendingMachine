# REST and IPC Contract Inventory

Baseline: Phase 1 inventory after commit `fef66c5`.

## Transport boundaries

| Boundary | Contract | Owner |
|---|---|---|
| Browser → Web | HTTP/JSON and CSV download | Flask routes |
| Web → Controller | newline-delimited JSON-RPC 2.0 | `ControllerClient` / `IPCServer` |
| Command dispatch | immutable `CommandEnvelope` / `CommandResult` | `CommandBus` |
| Controller → Web status | `MachineSnapshot` | snapshot publisher/IPC |

## IPC methods

| Method | Purpose | Mutates machine |
|---|---|---|
| `health.ping` | Controller reachability | No |
| `status.snapshot` | Authoritative machine snapshot | No |
| `command.submit` | Submit a Controller command | Depends on command |
| `command.status` | Read command state | No |
| `config.get_effective` | Read effective configuration | No |
| `config.save` | Validate/save configuration | Configuration only |
| `mqtt.status` | Read MQTT status | No |
| `mqtt.control` | Change MQTT runtime state | Service state only |
| `demo.history` | Read persistent Demo sessions/samples | No |
| `demo.export_csv` | Export persistent Demo samples | No |

## Command route groups

| REST group | Controller commands |
|---|---|
| Home | `HOME_AXIS`, `HOME_ALL` |
| Jog and positioning | `JOG`, `MOVE_TO`, `MOVE_TO_LIMIT`, `MOVE_TO_SLOT` |
| Validated positioning | `PLAN_MOVE`, `VALIDATE_TARGET`, `ARM_MOVE`, `EXECUTE_ARMED_MOVE` |
| Slot operation | `RUN_SLOT_SEQUENCE`, `DISPENSE` |
| Stop/recovery | `STOP`, `CONTROLLED_STOP`, `CLEAR_ALARM` |
| Machine authority | `DISABLE_MOTION`, `ENABLE_MOTION` |
| Hardware recovery | `RESET_NUCLEO_LINK`, `RESET_XY_DRIVE_POWER`, `CUT_XY_DRIVE_POWER`, `RESTORE_XY_DRIVE_POWER` |
| Demo | `CONFIGURE_DEMO`, `VALIDATE_DEMO`, `ARM_DEMO`, `START_DEMO`, `PAUSE_DEMO`, `RESUME_DEMO`, `STOP_DEMO` |
| Manual commissioning | `ARM_MOTOR_TEST`, `DISARM_MOTOR_TEST`, `RUN_MOTOR_TEST` |
| Runtime settings | `SET_SPEED`, `SET_TIMER` |
| Slot persistence | `SAVE_SLOT`, `SAVE_SLOT_FROM_CURRENT` |

## Read/query routes

- `/api/status`, `/api/io/status`, `/api/mqtt/status`
- `/health/live`, `/health/ready`
- `/api/config`, `/api/config/effective`
- `/api/slots`, `/api/slots/<slot>`
- `/api/home/<axis>/check`
- `/api/demo/status`, `/api/demo/history`, `/api/demo/export.csv`

## Contract defects found during inventory

1. `/api/speed` submitted `SET_SPEED` without a registered Controller handler.
2. `/api/timer` incorrectly submitted `SET_SPEED` with a `timer_seconds` parameter.
3. `SET_TIMER` was absent from the shared command contract.

These are corrected in Phase 1 with distinct Controller-owned handlers and regression tests. No Web route directly mutates Controller state.

## Compatibility requirements

- Keep current `ok`, `accepted`, `command_id`, `state`, `reason`, `result`, `started_at` and `completed_at` fields while adding structured error data.
- Existing HTTP status behavior remains characterized until a versioned API is introduced.
- Command names cannot be removed until route, MQTT and IPC consumers have migrated.
- STOP and E-STOP must remain dispatchable without waiting for a normal motion command.
