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

The hardware-neutral profile core is compiled from `Core/Src/profile_core`.
The staged `Core/Src/profile_hal/nucleo_g491_profile_hal.*` adapter binds the
candidate X/Y path to TIM1 CH1/CH2 without changing timer base state when one
axis stops. Host tests verify exact falling-edge pulse accounting, independent
channel completion, global disable, and fail-closed handling of a HAL channel
start failure.

This remains unreachable staging code: there is no serial dispatch, Controller
routing, runtime callback ownership, or advertised feature flag connected to
it. Z remains on the established TIM2 runtime. Keeping this boundary closed is
intentional until the 1 kHz planner tick, watchdog latency, configuration
revision checks, and STOP/DISARM semantics are verified together. The former
F439ZI tree is retained only as a migration reference.

The candidate includes a 1 kHz control-tick supervisor and TIM6 adapter. The
hardware-neutral coordinator connects each accepted tick to the profile
executor and pulse scheduler and propagates safety loss to an immediate profile
stop. Host tests cover 1 ms cadence, missed-deadline latching, clock regression,
500 ms heartbeat timeout, explicit disarm, and safety loss. The TIM6 runtime
gate defaults to disabled and no interrupt handler or initialization call is
installed in the production path yet.

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

## Baseline quality status

- Automated suite before structural extraction: 190 tests passed and 18 subtests passed.
- Production health before refactor: Web, Controller, NUCLEO USB, IRIV I/O and PiControl I/O online.
- Automated tests do not issue real motion.
- Mechanical motion, PEND polarity and maximum-speed behavior remain operator acceptance items.
