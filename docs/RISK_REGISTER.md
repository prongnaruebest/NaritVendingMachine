# Refactor Risk Register

| ID | Risk | Evidence | Severity | Treatment / exit criterion |
|---|---|---|---|---|
| R-01 | Legacy and deployed API implementations diverge | Duplicate routes in `webapp.py` and `web/routes/` | High | Route inventory and contract tests must pass before legacy route removal |
| R-02 | Motion module mixes pure planning with hardware effects | `motion.py` contains conversion, planning, homing loops and GPIO/Nucleo execution | Critical | Extract only pure behavior first; preserve adapter tests and command traces |
| R-03 | Multiple overlapping state models disagree | Motion controller strings, `MachineState`, snapshot normalization and UI-derived state coexist | Critical | Define canonical states and a tested compatibility translator before replacement |
| R-04 | Broad exception handling hides actionable causes | Broad catches exist in transports, routes and controller composition | High | Introduce typed error codes at boundaries; retain exception chaining and structured logs |
| R-05 | Thread cancellation and ownership are implicit | Pollers, demo worker, MQTT worker, safety monitor and restart worker use independent flags/locks | High | Document owner/cancellation contract and add shutdown/race tests before consolidation |
| R-06 | Frontend regression blast radius is large | Single 5k-line JS file and 8k-line CSS cascade | High | Characterize navigation, commands and responsive behavior; extract without visual redesign |
| R-07 | I/O semantics can be confused | ALM is blocking while PEND is positive non-blocking feedback | Critical | Typed signal metadata; PEND cannot enter alarm list; commission polarity before completion gating |
| R-08 | Config values can differ across machine/hardware/effective views | Multiple JSON files and runtime restart requirement | High | Versioned schema, atomic save, diff preview, backup and effective-config verification |
| R-09 | Endpoint events can incorrectly destroy reference | Historical Max-limit bug cleared Home and latched Stop | Critical | Directional limit regression tests remain mandatory through every extraction |
| R-10 | Deployment can reset volatile machine state | Controller restart clears Home | Medium | Every deploy report states whether Controller restarted; never run automatic Home afterward |
| R-11 | Persistent DB schema has no migration framework | Demo tables are created inline | Medium | Add schema-version table and transactional migrations before changing columns |
| R-12 | Refactor could accidentally actuate hardware | Production host is reachable during development | Critical | Tests use mock hardware; deploy smoke tests are read-only; motion requires operator action |
| R-13 | PEND polarity and driver parameters are unverified | DI2/DI3 currently read raw LOW while idle | High | Keep advisory/non-blocking until controlled transition test confirms OFF-moving/ON-settled |
| R-14 | Backup may become incomplete or unusable | Source/config/database/systemd/firmware have different lifecycles | High | Baseline tag, file checksums, DB copy, unit definitions and firmware artifacts are captured together |

## Immediate no-go conditions

Stop the refactor/deploy when any of these occurs:

- dirty files overlap the planned change and ownership is unclear;
- configuration validation fails;
- safety/motion characterization tests fail;
- Controller, NUCLEO, IRIV or PiControl health regresses;
- a proposed boundary would allow Web to touch hardware;
- rollback inputs or checksums are missing.
