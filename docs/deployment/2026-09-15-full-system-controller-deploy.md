# Full-system Controller/Web deployment — 2026-09-15

This record documents a no-motion deployment of the Python Controller and Web
application from Git commit `d1bb0b7` to the IRIV Pi runtime at
`/home/admin/NaritVendingV1`. The NUCLEO firmware was deliberately not flashed.

## Backup and preserved state

- Backup: `/home/admin/NaritVendingV1/backups/pre-full-system-deploy-20260915-130813`
- The backup contains 178 files including the previous `narit_vending` package,
  live IRIV machine/hardware configuration, installed systemd units, and online
  SQLite backups.
- `SHA256SUMS.txt` is stored inside the backup.
- Live configuration, SQLite files, virtual environment, and firmware were not
  replaced.

## Validation and deployment

- The staged package was validated against the live configuration before the
  services were stopped.
- Configuration validation returned zero errors and zero warnings; revision:
  `e5d7af30124708c8b498c92fcd647b99d2f61737fea949f98778ac9d0731724b`.
- Python bytecode compilation passed on the Pi.
- The deployed hashes of `motion.py`, `nucleo.py`, `webapp.py`, `app.js`, and
  `index.html` match the local source.
- `narit-vending-controller-iriv.service` and
  `narit-vending-web-iriv.service` returned `active` after restart.
- `/health/live` returned `UP` and the post-deploy service journal contained no
  warning/error entries.

## No-motion hardware and browser verification

- IRIV I/O and PiControl I/O report online.
- NUCLEO-G491RE reports online over USB using protocol v3 with
  `max_move_steps=1000000`; protocol-v4 dynamic capabilities are not advertised.
- Browser navigation opened Motion Control, Slot Position Setup, Machine
  Visualization, Demo Slot Sampling, and Manual Commissioning successfully.
- No browser console warning/error was observed during those checks.
- No Home, Jog, GOTO, Min/Max seek, slot move, dispense, drive-power reset, or
  Demo Sampling command was issued.

## Remaining motion inhibit

The machine remains intentionally inhibited because IRIV DI10 is raw LOW and
the configured active-low `KM1_FEEDBACK / E-Stop` channel therefore reports
E-Stop active. Controller state is `E_STOP`, motion authority is disabled,
`stop_requested` is latched, and all axes are not homed. X Max also reports
active. These interlocks were not bypassed. Normal Jog, GOTO, slot motion, and
Demo Sampling become eligible only after the physical safety chain reports
clear, the stop/alarm latch is reset, motion authority is enabled, and the
required axes complete Home.

The protocol-v4 Virtual-KP/S-curve path remains a compiled, feature-gated
candidate. It was not enabled or flashed by this deployment.
