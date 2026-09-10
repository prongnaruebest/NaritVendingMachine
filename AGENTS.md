# NaritVendingMachine Agent Working Agreement

This repository controls a real machine. Every human or AI agent must read this file before changing code. Detailed rationale and handoff rules live in `docs/ENGINEERING_WORKFLOW_AND_HANDOFF_TH.md`.

## Non-negotiable safety boundaries

- The Controller process is the sole owner of motion, GPIO, IRIV I/O writes, and safety decisions.
- The Web UI may send Controller API commands only. It must never generate STEP pulses or write GPIO directly.
- Never bypass E-Stop, physical Stop, driver alarm, USB watchdog, or communication-fault interlocks.
- Home/limit bypass is allowed only inside explicitly armed Manual Commissioning.
- Automated tests must use mock hardware and must never cause real motion.
- Deploy must not automatically Home, Jog, GOTO, dispense, reset drive power, or start Demo Sampling.
- Before any real motion, obtain an explicit operator statement that the area is safe and state the exact axis, direction, and test speed.

## Required workflow for every change

1. Read `git status`; preserve unrelated and live-machine changes.
2. Identify the owning module and API contract before editing.
3. Keep machine authority in the Controller and UI state derived from Controller data.
4. Add or update tests for the changed behavior.
5. Update relevant documentation when behavior, configuration, wiring, protocol, deployment, or UI workflow changes.
6. Run proportionate validation: configuration, Python compile/lint/type checks, JavaScript syntax, automated tests, and browser console/layout checks when applicable.
7. Deploy only the requested/in-scope layer and verify health afterward.
8. Commit and push every completed logical change. Never include unrelated dirty files.
9. Report the commit hash, tests executed, deploy status, untested hardware behavior, and remaining risks.

## Code comments and documentation

- Comments must explain **why**, safety invariants, ownership boundaries, protocol assumptions, units, state transitions, or non-obvious recovery behavior.
- Do not comment obvious syntax or duplicate the implementation in prose.
- Public Python modules/classes/functions with non-obvious contracts should have concise docstrings.
- JavaScript controllers and safety-sensitive handlers should document inputs, Controller authority, invalidation rules, and stop behavior.
- Use explicit engineering units in names (`_mm`, `_mm_s`, `_hz`, `_ms`, `_us`).
- Document configuration precedence and whether a value is candidate, saved, effective, or reported by hardware.
- When fixing a bug, add a regression test and a short comment only where the underlying constraint is not self-evident.

## Architecture and UI conventions

- Prefer small modules with one responsibility and dependency injection at hardware boundaries.
- Maintain one shared frontend state for positions, speeds, selected slot, connections, alarms, capabilities, and configuration revision.
- Changing motion parameters invalidates pending Validate/Arm state.
- Never display a capability the backend/firmware handshake does not support.
- Industrial HMI styling: 4/8 px spacing, 44x44 px minimum controls, visible focus, ARIA labels, no document-level horizontal overflow, red only for danger/alarm/stop.
- Responsive checks target 1920x1080, 1366x768, 1024x768, 768x1024, and 390x844.

## Commit convention

Use a focused conventional subject:

- `feat: ...` new behavior
- `fix: ...` bug or safety correction
- `refactor: ...` structure without behavior change
- `test: ...` test-only work
- `docs: ...` documentation-only work
- `firmware: ...` NUCLEO firmware work
- `deploy: ...` deployment tooling/configuration

One commit should represent one reviewable logical outcome. Do not use `git add .` in a dirty worktree. Do not commit secrets, generated backups, live credentials, or unrelated machine configuration.

## Source-of-truth documents

- `docs/CURRENT_ARCHITECTURE.md`
- `docs/API_CONTRACT_INVENTORY.md`
- `docs/PROJECT_STRUCTURE_TH.md`
- `docs/SAFETY_AND_RECOVERY_TH.md`
- `docs/TESTING_AND_TROUBLESHOOTING_TH.md`
- `docs/ENGINEERING_WORKFLOW_AND_HANDOFF_TH.md`

