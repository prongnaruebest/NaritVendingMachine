# Incremental Refactor Roadmap

## Governing rules

- Preserve a single Controller hardware owner.
- One behavioral concern per commit.
- Every fixed defect keeps a regression test.
- No automated motion during development, CI or deployment.
- Compatibility adapters are removed only after callers and contract tests migrate.

## Phase 0 — Baseline and recovery (complete)

- [x] Confirm clean source baseline.
- [x] Create annotated Git baseline tag.
- [x] Back up machine and hardware configuration.
- [x] Back up Demo SQLite database.
- [x] Capture deployed systemd unit definitions.
- [x] Capture firmware artifacts and SHA-256 manifest.
- [x] Record current architecture, dependencies and risks.

Exit criterion: baseline can be identified and recovery inputs exist without touching machine motion.

## Phase 1 — Characterization and domain vocabulary

- [x] Inventory every REST and IPC contract.
- [x] Add architecture dependency tests.
- [x] Move shared motion/config/transport errors into a dependency-neutral domain module.
- [x] Add canonical enums for axis, direction, command outcome and axis state.
- [x] Characterize limit recovery, zero-distance moves, stale stop flags, speed invalidation and PEND semantics.
- [x] Define structured error response while preserving legacy fields.

Exit criterion: existing behavior is protected, domain package has no infrastructure imports, and the full suite remains green.

## Phase 2 — Canonical safety and command state

- [x] Extend `CommandEnvelope` with validated versioned metadata compatibly.
- [x] Define typed SafetySnapshot and reason codes.
- [x] Reconcile Motion state strings, Controller state machine and snapshot normalization.
- [x] Add transition-table and concurrency tests.
- [x] Add bounded idempotency storage.

Exit criterion: all HTTP/MQTT/system motion requests traverse one tested decision path.

## Phase 3 — Hardware adapter boundaries

- [x] Introduce interfaces for clock, NUCLEO transport, IRIV I/O and PiControl I/O.
- [x] Move I/O metadata to a Controller-provided registry.
- [x] Remove frontend hard-coded channel semantics.
- [x] Add PEND commissioning fields and transition diagnostics.
- [x] Add fault-injection tests for transport loss and stale inputs.

Exit criterion: hardware adapters can be replaced by deterministic fakes and PEND remains advisory until commissioned.

## Phase 4 — Motion and homing services

- [x] Extract pure conversion and planning modules.
- [x] Extract limit policy and completion policy.
- [x] Extract homing orchestration from axis pulse execution.
- [x] Add PEND completion verification behind a commissioned capability flag.
- [x] Preserve protocol v2 fallback and v3 parallel behavior.

Exit criterion: plans are pure/testable and hardware execution consumes validated immutable plans.

## Phase 5 — Persistence and observability

- [x] Add SQLite migration/version framework.
- [x] Add repositories for slots, demo sessions/samples, audit and idempotency.
- [x] Introduce structured event codes and correlation IDs.
- [x] Add retention, backup and restore tests.

Exit criterion: a command/session can be reconstructed from persistent records without parsing free-form text.

## Phase 6 — Frontend modularization

- [x] Extract API client, machine store and selectors.
- [x] Extract router and lifecycle-safe page controllers. (Motion Jog directional, keyboard and fail-safe lifecycle included)
- [x] Generate I/O views from registry metadata.
- [ ] Split component/page CSS under one token layer. (token/reset, shared speed controls and final responsive/page authority layers extracted; remaining components incremental)
- [x] Preserve all responsive and accessibility acceptance tests.

Exit criterion: pages share one state source, polling does not overlap, and no module contains hardware authority.

## Phase 7 — Release engineering and documentation

- [ ] Add formatting, lint, typing and dependency-direction gates. (`ruff` lint and `mypy` checks now protect the dependency-neutral domain/shared core; expand typing coverage to Controller, persistence and web modules incrementally)
- [x] Build staged atomic release and rollback verification. (artifact, verification, staging, activation, rollback and interruption recovery are automated with non-hardware tests; production execution remains operator-controlled)
- [x] Complete operator, configuration, PEND, testing and troubleshooting manuals. (release/rollback, Operator HMI, configuration/calibration/PEND and testing/troubleshooting guides complete)
- [ ] Run read-only production smoke tests.
- [ ] Prepare operator-controlled mechanical acceptance checklist.

Exit criterion: failed health checks roll back safely and no deploy performs motion automatically.

## Phase 8 — X/Y jerk-limited motion

- [x] Add a hardware-neutral S-curve reference model and characterization tests for X/Y only.
- [x] Add a firmware-ready seven-segment profile representation with stable seven-phase serialization.
- [x] Define the capability-gated buffered profile contract (protocol v4 candidate; transport remains disabled).
- [x] Add a disabled-by-default buffered transport adapter with fake-exchange failure tests.
- [x] Add a HAL-independent firmware profile parser/buffer state machine with host-compiled tests; keep it outside the CubeIDE build.
- [x] Add a timer-independent X/Y profile executor with synchronized start, phase transitions and fail-safe heartbeat handling.
- [x] Convert every wire phase to fixed-point pulse-domain kinematics so firmware never needs an implicit steps/mm value.
- [x] Add a host-tested pulse scheduler that updates rates without phase-boundary disable and stops at exact X/Y pulse counts.
- [x] Add a HAL-independent timer adapter with bounded PSC/ARR/pulse-width calculation and atomic rate updates.
- [x] Select a fixed-timebase output-compare adapter for shared TIM1 CH1/CH2 after verifying the X/Y mapping; do not use per-axis PSC/ARR.
- [ ] Integrate X/Y Move, Jog, Home and Limit Seek without changing Z behavior.
- [ ] Add Machine Setup fields, validation, effective configuration and profile preview.
- [ ] Build firmware artifact and complete operator-controlled mechanical commissioning.

Exit criterion: X/Y start and stop without segment gaps, all configured kinematic limits are enforced,
and E-Stop/Stop/ALM/watchdog behavior remains fail-safe. Z remains on its existing motion path.

Run the current non-hardware quality baseline from the repository root:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/quality_gate.py
```

Use `--quick` while developing to omit the complete test suite. Both modes avoid
starting Flask, Controller, GPIO, serial communication and motion commands.
GitHub Actions runs the complete gate on every push and pull request using only
read access to repository contents; the workflow contains no deployment or machine-control step.

Prepare a deterministic release bundle without including or changing live configuration:

```powershell
python scripts/build_release.py
```

The ZIP embeds `release-manifest.json`; a matching manifest is written beside it.
Both list every packaged file and SHA-256 checksum. Building an artifact does not connect
to the Pi, restart a service or issue a machine command.

Verify a received artifact before extracting it into a staging directory:

```powershell
python scripts/verify_release.py <release.zip> <release.manifest.json>
```

Verification rejects checksum/inventory differences, duplicate or unsafe paths and any bundled
machine/hardware configuration. It does not extract files, restart services or contact hardware.

To extract into a new immutable staging directory and verify every file again after writing:

```powershell
python scripts/verify_release.py <release.zip> <release.manifest.json> --stage-root <staging-root>
```

The destination is `<staging-root>/<release-id>`. Existing releases are never overwritten;
staging alone does not change the active release or restart a service.

On the target host, add both live configuration paths to run compatibility validation using
the code from the staged release:

```text
python scripts/verify_release.py <release.zip> <release.manifest.json> \
  --stage-root <staging-root> \
  --machine-config <machine-config.json> \
  --hardware-config <hardware-config.json>
```

This compiles staged Python source in memory and reads configuration without modifying it.

The release lifecycle validates a candidate before stopping the current runtime. A failed
candidate health check restores the previous release and verifies its health. If rollback
also fails, the persistent state is explicitly `FAILED`; it is never reported as healthy.
Current automated tests use a fake runtime and do not invoke systemd or hardware.

`scripts/activate_release.py` defaults to read-only validation and plan output. Live activation
is restricted to POSIX, requires both `--execute` and the explicit confirmation token, and uses
the lifecycle rollback path. The current production service layout must be migrated before live
activation is enabled; do not point this command at the legacy application directory.

`scripts/plan_release_migration.py` prints the one-time layout plan without changing the host.
The release-layout unit templates live under `deploy/release-layout/`; legacy unit files remain
untouched so the existing deploy script cannot enable the new layout prematurely. Persistent
configuration, SQLite history, backups and `.venv` are placed under `shared/`, while `current`
points only to immutable release code.

Run the non-hardware migration rehearsal locally with:

```powershell
python scripts/rehearse_release_migration.py
```

The migration coordinator journals every phase. Validation or backup failure aborts before
service shutdown; a normal failure rolls back immediately; a hard interruption leaves a
recoverable phase which must be explicitly recovered before another migration can start.

## Commit strategy

Use small commits such as:

1. `docs: capture refactor baseline and risks`
2. `test: enforce architecture dependency boundaries`
3. `refactor: extract domain errors with compatibility imports`
4. `refactor: extract pure motion conversions`
5. `refactor: define canonical safety reason codes`

Do not combine frontend redesign, motion behavior change, configuration migration and deployment changes in one commit.
