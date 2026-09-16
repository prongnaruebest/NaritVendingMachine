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

## G491RE motion-firmware migration

The active CubeIDE target is `Motion_NaritVending/Motion_NaritVending` for the
NUCLEO-G491RE. Its current runtime contract remains USB protocol v3 with
fixed-frequency `MOVE`; no trajectory-profile capability is advertised.

Repository Home execution sizes its search frame from the NUCLEO
`max_move_steps` handshake instead of forcing a 10,000-pulse boundary. On the
G491RE a normal full X/Y search therefore remains one continuous timer command;
legacy firmware retains its smaller advertised frame size. The Controller
continues polling E-Stop, software Stop and the IRIV Home input during that
frame, and the Home deadline is part of the stop callback so a missing sensor
cannot turn the larger pulse budget into an unbounded search. Parallel Home All
remains protocol-v3-gated and stops an individual axis when its Min sensor is
observed while a global safety failure stops all axes.

The hardware-neutral profile core is compiled from `Core/Src/profile_core`.
The staged `Core/Src/profile_hal/nucleo_g491_profile_hal.*` adapter binds the
candidate X/Y path to TIM1 CH1/CH2 without changing timer base state when one
axis stops. Host tests verify exact falling-edge pulse accounting, independent
channel completion, global disable, and fail-closed handling of a HAL channel
start failure. Dynamic start also has an explicit direction-preparation
contract: every participating X/Y DIR output must be written successfully and
the HAL must wait at least the driver setup interval before either shared TIM1
channel can emit STEP. The G491RE adapter currently uses one bounded 1 ms delay
on the command path, safely exceeding the HBS860H 5 us requirement; this delay
is not used to generate pulses. A direction-preparation failure inhibits both
channels and leaves the staged command unstarted.

This remains unreachable staging code: there is no serial dispatch, Controller
routing, runtime callback ownership, or advertised feature flag connected to
it. Z remains on the established TIM2 runtime. Keeping this boundary closed is
intentional until the 1 kHz planner tick, watchdog latency, configuration
revision checks, and STOP/DISARM semantics are verified together. The former
F439ZI tree is retained only as a migration reference.

`Core/Inc/nucleo_motion_features.h` is the single compile-time authority for
that boundary. `NUCLEO_G491_DYNAMIC_MOTION_ENABLED` defaults to zero and drives
both protocol-v4 dispatch and the TIM6 runtime; a mismatched partial enable is
a compile error. This prevents a build from advertising dynamic commands while
its deterministic control timer is absent, or starting that timer while the
Controller can only negotiate protocol v3.

The hardware-neutral `nucleo_dynamic_app.*` bridge now owns the candidate
facade and serial dispatcher lifecycle. When the shared gate is enabled it
routes configuration/position/target/start commands and makes legacy pulse
inhibition occur before any STOP or DISARM acknowledgement. It exposes the
heartbeat, 1 kHz control-tick and emitted-pulse boundaries needed by the G491RE
HAL. With the default gate disabled, initialization returns unavailable and the
production protocol-v3 serial/motion path remains the only reachable runtime.

The candidate includes a 1 kHz control-tick supervisor and TIM6 adapter. The
hardware-neutral coordinator connects each accepted tick to the profile
executor and pulse scheduler and propagates safety loss to an immediate profile
stop. Host tests cover 1 ms cadence, missed-deadline latching, clock regression,
500 ms heartbeat timeout, explicit disarm, and safety loss. The TIM6 control
timer (`TIM6_DAC_IRQHandler`) and dynamic runtime (`NucleoG491ProfileHal` on TIM1)
are now integrated into `nucleo_motion.c` and `stm32g4xx_it.c` behind the
`NUCLEO_G491_DYNAMIC_MOTION_ENABLED` gate, while remaining completely inert in the
default configuration.

An X/Y-only pulse-domain seven-segment S-curve planner is now compiled in the
G491RE project as another unreachable candidate. It accepts explicit limits in
Hz, Hz/s and Hz/s², uses the lower of acceleration/deceleration for its initial
symmetric implementation, reduces peak rate for short moves, and records the
integer target pulse in the final phase. Zero-distance is reported as no-motion
and Z is rejected. This does not yet change the runtime completion contract:
the executor still reaches its time boundary independently of the emitted-pulse
counter. Therefore the profile feature remains disabled until completion is
owned by exact emitted pulses and underrun/quantization behavior is verified.

The candidate runtime now makes that terminal distinction explicitly. Elapsed
profile time only marks the trajectory envelope as elapsed; bounded moves enter
`COMPLETE` only when every non-sensor frame's falling-edge counter equals its
integer target. A missing pulse at the time boundary disables both candidate
channels, enters `FAILED`, and records `PULSE_UNDERRUN`. Sensor-terminated frames
remain complete only after their own axis has been stopped by the sensor
supervisor. This behavior is host-tested but remains behind the disabled runtime
gate and is not yet exposed through the serial protocol.

The next candidate layer is an X/Y-only Virtual Kp velocity request. It uses
fixed-point `kp_approach_milliper_s` and remaining emitted-pulse error to produce
`requested_rate_millihz`, clamps at 50,000 Hz, and returns zero for zero remaining
pulses. With Kp disabled it requests the configured maximum rate. This output is
not a timer command or a safety constraint: it remains disconnected until the
S-curve/stopping-feasibility layer can enforce acceleration, deceleration, jerk,
travel and terminal-pulse requirements. Z is explicitly rejected.

A separate 1 kHz constraint-envelope candidate now consumes that request. Its
stopping estimate includes the jerk ramp from current commanded acceleration to
maximum deceleration, the following constant-deceleration distance, one control
period of latency. Discrete final-edge quantization is handled by the pulse
phase accumulator rather than added as a full-pulse braking margin, because a
full-pulse margin prevents a stationary one-pulse move from ever starting.
Acceleration changes by at most the
configured jerk per tick. A falling Kp request is never applied as an immediate
velocity clamp; the commanded velocity follows the bounded deceleration state.
The module is host-tested but is not connected to the timer/runtime. Exact
finite completion still belongs to the emitted-pulse scheduler, so the runtime
feature gate remains disabled pending integrated simulation.

The hardware-neutral dynamic-planner simulation now composes Virtual Kp,
the jerk-aware constraint envelope and a 64-bit fractional pulse-phase
accumulator. Pulse phase is integrated in milliHz·µs, emitted counts are clamped
to the integer target, and the final edge is held until the commanded rate is at
or below the configured terminal threshold. Host scenarios cover zero, one,
short and 170,000-pulse moves on both X/Y directions with monotonic counts and
no overshoot. This is evidence for the algorithm only; the module remains
disconnected from interrupts, timers and serial dispatch until runtime timing
and safety-priority integration are tested.

The production-facing dynamic runtime no longer advances position from its
1 kHz calculation tick. Only the TIM1 HAL falling-edge callback may record an
emitted X/Y STEP pulse. Reaching the integer target stops that channel; reaching
it above the configured terminal rate fails closed instead of silently claiming
a smooth completion. The original phase-accumulator path remains isolated as a
host-only deterministic trajectory simulation. The HAL callback is still not
registered in the production protocol-v3 runtime.

An X/Y coordinator now composes two independent dynamic runtimes. A coordinated
start is atomic at the software boundary: if either axis cannot arm/start, both
are disarmed and no partial command remains active. Each axis completes from its
own emitted STEP count, so one axis may finish while the other continues. STOP,
DISARM, safety loss, watchdog failure, or control-tick failure remain global and
disable both TIM1 channels. Host tests cover independent completion and global
safety shutdown; the coordinator is still behind the disabled production gate.

The candidate also separates controlled and safety stopping. A controlled stop
changes the planner request to zero and continues applying the configured jerk
and deceleration envelope until commanded velocity and acceleration are both
zero, ending in `STOPPED` without claiming the original target was reached.
Immediate `STOP`, `DISARM`, watchdog expiry and safety loss still bypass that
ramp and disable both pulse channels at once. No stopped command auto-resumes.

A HAL-independent dynamic runtime now wraps that simulation behind explicit
Arm/Start/Reset transitions and fake rate/disable hooks. STOP, DISARM, safety
loss, the independent 500 ms heartbeat watchdog, and a missed 1 kHz control
deadline all latch a terminal reason, clear Arm, set output rate to zero, and
call global disable. No fault path auto-resumes; a safe explicit Reset is
required and Reset never arms or starts motion. Host tests exercise every stop
source after motion has begun. The runtime remains unregistered and therefore
cannot affect the deployed protocol-v3 firmware.

The next protocol-v4 boundary is now defined and host-tested without being
registered in the production UART dispatcher. `DYN_CONFIG` carries X/Y travel,
scale, Virtual-Kp, velocity, acceleration, deceleration and jerk values as
explicit integer pulse-domain units plus a configuration revision. It is
accepted only while disarmed and invalidates the open-loop position reference.
`DYN_TARGET` carries an idempotent command ID, absolute pulse target and the
same acknowledged revision. The candidate rejects stale revisions, unknown
positions, out-of-travel targets, commands while busy, malformed identifiers,
and reuse of an ID with different content. A duplicate with identical content
is reported separately. This contract remains unreachable until position is
set from a successful Controller-owned Home and the dynamic runtime/HAL path is
verified together.

The transport-neutral dynamic facade now joins that revision-bound protocol to
the X/Y coordinator. Both axis configurations must be valid before the runtime
is ready; one or two targets sharing a command ID are staged and then started
atomically. Absolute estimated position changes only from emitted falling STEP
edges, and each axis commits its target independently at exact completion.
Immediate STOP/DISARM/safety loss invalidate the open-loop reference, while a
controlled stop preserves the emitted coordinate without claiming the original
target. The facade and its 50 kHz input ceiling are host-tested with fake timer
hooks and remain outside the production UART dispatcher and CubeIDE feature
gate.

A bounded transport-neutral dispatcher now defines the candidate UART routing
for `DYN_CONFIG`, `DYN_POSITION`, `DYN_TARGET`, and `DYN_START`. Its independent
`NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED` gate defaults to `0`; with the gate off,
dynamic commands cannot reach the facade. Exact `STOP` and `DISARM` remain
recognized with higher priority even when the dynamic feature is disabled.
Host builds exercise both gate states, unsafe-start rejection, malformed and
oversized frames, and global disarm. The production serial link still advertises
protocol v3 and does not call this dispatcher.

The same gated dispatcher exposes a bounded `DYN_STATUS` snapshot for X/Y.
It reports runtime readiness, active-axis mask, position-reference validity,
absolute pulse coordinate, command-relative emitted pulses, target, requested
timer rate, planner state, and latched fault. This telemetry is authoritative
for firmware execution state but remains open-loop; it must never be presented
as encoder-measured carriage position. Undersized response buffers fail closed
without emitting partial JSON.

## Baseline quality status

- Automated suite before structural extraction: 190 tests passed and 18 subtests passed.
- Production health before refactor: Web, Controller, NUCLEO USB, IRIV I/O and PiControl I/O online.
- Automated tests do not issue real motion.
- Mechanical motion, PEND polarity and maximum-speed behavior remain operator acceptance items.
