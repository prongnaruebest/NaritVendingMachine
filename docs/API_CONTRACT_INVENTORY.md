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

## NUCLEO motion-protocol boundary

The deployed Controller contract currently targets G491RE USB protocol v3:
`PING`, `STATUS`, `ARM SAFE`, `HEARTBEAT`, `MOVE`, `STOP`, and `DISARM`.
Although the G491RE build now compiles the hardware-neutral profile core and an
X/Y TIM1 HAL adapter, neither is registered with the runtime dispatcher. The
firmware does not advertise profile capabilities and does not accept profile or
configuration commands. Web and Controller code must continue to treat the
profile path as unsupported until a later protocol capability handshake
explicitly reports it.

The next integration gate must define configuration revision ACK/NACK,
idempotent command IDs, emitted-pulse telemetry, bounded parser behavior, and
priority handling for `STOP`/`DISARM` before any new command is routed from the
Controller. Compiled presence alone is never a capability signal.

The internal candidate now provides a transport-neutral telemetry snapshot with
`state`, `terminal_fault`, `command_id`, per-axis `target_steps`,
`emitted_steps`, `axis_active`, `trajectory_elapsed`, and `safety_permissive`.
Stable state names are `EMPTY`, `BUFFERED`, `RUNNING`, `COMPLETE`,
`SAFETY_STOP`, and `FAILED`; the first terminal fault is `PULSE_UNDERRUN`.
This is not yet a serial/API response. Starting a candidate command resets its
previous terminal fault. A completed, failed, or safety-stopped command requires
an explicit reset while safety is permissive; reset clears buffers/counters but
does not arm or start motion. Reset is rejected while running or unsafe.

The G491RE tree also compiles a bounded read-only `PROFILE_STATUS` candidate.
Its independent `NUCLEO_XY_PROFILE_TELEMETRY_ENABLED` compile-time gate defaults
to `0`, and it is intentionally not registered in `nucleo_serial_link.c`.
Consequently deployed protocol-v3 `PING`/`STATUS` responses and accepted
commands remain byte-for-byte unchanged. With the candidate enabled in host
tests, the response exposes the transport-neutral snapshot as bounded JSON;
unknown/trailing commands and undersized response buffers are rejected.

## Structured command errors

Rejected or failed Controller commands retain the legacy `ok`, `accepted`,
`state` and `reason` fields and additionally expose an `error` object:

```json
{
  "code": "SAFETY_INTERLOCK",
  "message": "Emergency stop is active",
  "details": {},
  "retryable": false
}
```

Initial stable codes are `COMMAND_REJECTED`, `SAFETY_INTERLOCK`,
`UNKNOWN_COMMAND`, `MACHINE_BUSY` and `INTERNAL_HANDLER_ERROR`. Consumers must
use `code` for branching and treat `message` as operator-facing text.
Idempotent retries may also return `COMMAND_IN_PROGRESS` or
`IDEMPOTENCY_CONFLICT`; completed results are cached in a bounded in-memory
least-recently-used store.

## Command metadata

`CommandEnvelope.metadata` is an optional, versioned object containing
`schema_version`, `correlation_id`, `actor` and `client_revision`. Missing
metadata is interpreted as schema version 1 with empty context, so commands
from older Web/MQTT clients remain valid. Unknown schema versions are rejected
at the transport boundary before command dispatch.
