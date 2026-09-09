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
- [ ] Extract router and lifecycle-safe page controllers. (router/registry, I/O, Events and Flow complete; migration incremental)
- [ ] Generate I/O views from registry metadata.
- [ ] Split component/page CSS under one token layer.
- [ ] Preserve all responsive and accessibility acceptance tests.

Exit criterion: pages share one state source, polling does not overlap, and no module contains hardware authority.

## Phase 7 — Release engineering and documentation

- [ ] Add formatting, lint, typing and dependency-direction gates.
- [ ] Build staged atomic release and rollback verification.
- [ ] Complete operator, configuration, PEND, testing and troubleshooting manuals.
- [ ] Run read-only production smoke tests.
- [ ] Prepare operator-controlled mechanical acceptance checklist.

Exit criterion: failed health checks roll back safely and no deploy performs motion automatically.

## Commit strategy

Use small commits such as:

1. `docs: capture refactor baseline and risks`
2. `test: enforce architecture dependency boundaries`
3. `refactor: extract domain errors with compatibility imports`
4. `refactor: extract pure motion conversions`
5. `refactor: define canonical safety reason codes`

Do not combine frontend redesign, motion behavior change, configuration migration and deployment changes in one commit.
