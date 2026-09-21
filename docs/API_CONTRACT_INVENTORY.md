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

### Slot sequence result contract

`RUN_SLOT_SEQUENCE` is a Controller-owned, serialized command. It rejects an
unknown slot, disabled effective sequence configuration, unhomed axes,
non-finite/non-positive speed, and a per-slot Y-lift target beyond configured
travel before emitting motion. The execution result retains the existing
`ok`/`error` fields and adds `failed_phase` plus `completed_phases` on failure
so the HMI and audit log can identify the last bounded stage. A failure never
starts an automatic recovery move. The operator must resolve the fault, clear
the safety latch, re-Home as required, and issue a new command.

Sequence dwell values are bounded to 0–60 seconds. During dwell the Controller
polls E-Stop, software Stop, active IRIV/PiControl fault channels, and explicit
NUCLEO communication loss at intervals no longer than 100 ms. Home completion
is compared with each axis `home_position_mm`, not an assumed zero coordinate.

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

### Current audited contract — 2026-09-20

The current G491RE source advertises protocol v4 and the capabilities
`continuous_profile`, `seven_segment_s_curve`, `buffered_segments`,
`profile_sequence`, `profile_telemetry`, `dynamic_motion`, and
`terminal_rate_config`. Controller code
must require the complete set before using the dynamic X/Y path; protocol number
alone is insufficient. `DYN_CONFIG` is applied while disarmed, configuration
errors abort the move before targets are staged, and each coordinated axis uses
its own planned velocity limit. TIM6 supplies the deterministic 1 kHz planner
clock; TIM1 falling-edge callbacks remain the only authority for emitted X/Y
pulse counts.

Firmware still supports legacy MOVE for compatibility and Z. It rejects a
dynamic start while legacy X/Y owns TIM1. STOP, DISARM, watchdog and safety loss
remain global priority actions. This contract describes repository source and
tests; a USB handshake is still required to prove which firmware is flashed.

In protocol heartbeat telemetry, `watchdog=true` means the armed 500 ms
heartbeat watchdog is healthy; it is not a timeout alarm. After an acknowledged
`STOP` or `DISARM`, the Controller immediately publishes `armed=false`,
`safe=true`, `watchdog=false`, and zero moving axes so clients do not observe a
stale armed heartbeat while waiting for the next background poll.

The candidate/protocol-v3 narrative below is retained as historical design
context and is superseded where it conflicts with this current-status section.

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

The candidate contract now reserves these integer-only protocol-v4 frames:

```text
DYN_CONFIG <axis> <travel_min_pulses> <travel_max_pulses> <pulses_per_mm_milli> <kp_enabled> <kp_approach_milliper_s> <max_velocity_millihz> <max_acceleration_millihz_s> <max_deceleration_millihz_s> <max_jerk_millihz_s2> <terminal_rate_millihz> <configuration_revision>
DYN_POSITION <axis> <estimated_position_pulses> <configuration_revision>
DYN_TARGET <command_id> <axis> <target_position_pulses> <configuration_revision>
DYN_START <command_id> <axis_mask>
DYN_STATUS
```

Only X/Y are valid. Configuration is disarmed-only and invalidates the
firmware's estimated pulse coordinate. A target is rejected until a successful
Home has established that coordinate, when its revision is stale, while the
axis is busy, or when it is outside the configured travel envelope. Identical
command-ID retries are idempotent; reuse with different content is a conflict.
These frames are compiled candidate code only: protocol v3 does not advertise
or dispatch them and the Controller must not send them yet.

`terminal_rate_millihz` is the maximum output rate permitted when emitting the
final target pulse. It must be nonzero and no greater than
`max_velocity_millihz`; invalid values fail closed. The Controller derives it
from the effective per-axis terminal speed and `pulses_per_mm`. Dynamic routing
requires `terminal_rate_config`, preventing a new Controller from silently
using firmware that still contains the former fixed 1,000 Hz terminal gate.

`DYN_POSITION` is disarmed-only and may be sent only after the Controller has
completed a successful Home/reference operation under the same acknowledged
configuration revision. `DYN_TARGET` stages data but does not begin pulse
output. `DYN_START` accepts `X`, `Y`, or canonical `XY` and is the sole atomic
start boundary; every requested axis must already have a staged target with the
same command ID.

The candidate facade requires valid `DYN_CONFIG` frames for both X and Y before
it reports runtime-ready. It stages one or both `DYN_TARGET` frames under the
same command ID and starts the participating axes atomically. The wire velocity
is bounded to 50,000,000 milliHz (50 kHz); values above that are rejected rather
than truncated. STOP, DISARM, heartbeat/safety loss clear both position-valid
flags because drive motion can no longer be inferred safely. `CONTROLLED_STOP`
retains the coordinate from falling STEP edges but does not commit the target.
This behavior is host-only until the explicit production feature gate is
enabled in a later reviewed change.

Candidate dispatcher responses are bounded JSON ACK/error objects. Successful
states are `configured`, `position_set`, `staged`, `duplicate`, `running`,
`stopping`, `stopped`, and `disarmed`; stable rejection codes are `FORMAT`,
`AXIS`, `RANGE`, `STATE`, `REVISION`, `POSITION`, and `CONFLICT`. `STOP` and
`DISARM` are checked before feature-gated dynamic frames. This dispatcher is
compiled but remains unregistered in the production v3 serial loop.

When the v4 gate is enabled, `DYN_STATUS` returns bounded JSON containing
`runtime_ready`, `active_mask`, and per-axis `position_valid`,
`position_pulses`, `target_pulses`, `emitted_pulses`, `rate_millihz`, `state`,
`fault`, `remaining_pulses`, `acceleration_millihz_s`, and `braking`.
`position_pulses` is an open-loop coordinate derived only from
confirmed falling STEP edges; it is not encoder-measured mechanical position.
The response is rejected rather than truncated when the caller's output buffer
is too small. With the feature gate off, `DYN_STATUS` returns `STATE`.

For the candidate runtime, `emitted_steps` changes only after the HAL confirms
the falling STEP edge. A 1 kHz planner tick changes the requested timer rate but
does not change position. Completion therefore means the exact target edge was
emitted at or below the terminal-rate gate; a predicted/queued edge is never
reported as completed.

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
