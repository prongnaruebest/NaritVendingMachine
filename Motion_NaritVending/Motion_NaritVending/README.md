# NARIT motion firmware — NUCLEO-G491RE

This STM32CubeIDE project targets the STM32G491RE on the NUCLEO-G491RE board.
It preserves the Controller-facing serial protocol v3 while moving the board
identity and HAL target from the former NUCLEO-F439ZI.

## Runtime interfaces

- ST-LINK virtual COM: LPUART1 on PA2/PA3, 115200 baud, 8-N-1.
- X STEP/DIR: PA8 (TIM1_CH1, AF6) / PB0.
- Y STEP/DIR: PA9 (TIM1_CH2, AF6) / PB1.
- Z STEP/DIR: PA5 (TIM2_CH1, AF1) / PB2.
- Protocol identity: `NUCLEO-G491RE`, protocol `3`.
- Accepted pulse rate: 10-50,000 Hz; maximum command: 1,000,000 steps.

PA5 is shared with the on-board LD2 connection. The application never toggles
LD2 as an indicator because PA5 is the Z STEP output.

## Safety invariants

- Boot state is disarmed; STEP and DIR are driven low during initialization.
- `MOVE` is rejected until `ARM SAFE` is received.
- A missing valid heartbeat for more than 500 ms disarms motion and forces all
  STEP/DIR outputs low.
- `STOP`, `DISARM`, and `HEARTBEAT UNSAFE` stop every axis and disarm.
- The firmware watchdog is an operational stop, not a safety-rated E-Stop.
  Hardwired E-Stop, drive-power removal, alarms, and Controller interlocks must
  remain in service.

## Profile-planner migration state

The hardware-neutral profile buffer, executor, pulse scheduler, compare/timer
adapters, sensor-stop supervisor, and SHA-256 helper are staged under
`Core/Src/profile_core`. The G491RE-specific TIM1 adapter for X/Y is staged
under `Core/Src/profile_hal`. STM32CubeIDE compiles these sources for the G491RE
so compiler regressions are visible early, and host tests exercise the same
source files.

The HAL adapter is deliberately not connected to the serial dispatcher or
runtime command path yet. Protocol v3 therefore continues to advertise and
execute only the existing fixed-frequency `MOVE` behavior. The adapter maps X
to TIM1 CH1/PA8 and Y to TIM1 CH2/PA9, counts emitted pulses on falling edges,
keeps channel stop operations independent, and latches a fail-closed fault if
an output-compare channel cannot start. This boundary prevents partially
integrated trajectory code from becoming a Web or Controller capability before
watchdog latency, configuration revision, and stop semantics pass together.

The candidate control path now also contains a hardware-neutral 1 kHz tick
supervisor, a profile-runtime coordinator, and a TIM6 adapter. The supervisor
latches a safety stop on a missing deadline, non-monotonic clock, lost safety
permissive, or heartbeat age over 500 ms. The compile-time gate
`NUCLEO_G491_PROFILE_RUNTIME_ENABLED` defaults to `0`; TIM6 is not initialized,
its IRQ is not registered, and the candidate still cannot start at runtime.

## Build

Import this directory into STM32CubeIDE and build the `Release`
configuration. The project was generated with STM32Cube FW_G4 V1.5.1. The
profile-core staging build was validated with STM32CubeIDE 1.19.0; this is a
compile result only and does not authorize flashing or motion.

Do not flash or test with connected drivers until the operator explicitly
confirms the area is safe and the exact axis, direction, and low test speed.
First verify the image hash, boot identity, watchdog shutdown, and STEP/DIR
waveforms with the drivers disconnected or with a dummy optocoupler load.
