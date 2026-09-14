# Controller deployment and firmware gate record — 2026-09-14

This record captures a no-motion deployment performed at Git commit `7fc3a65`.
It is evidence for handoff and rollback; it is not approval to move the machine.

## Safety state before deployment

- Controller reported no active command and `busy=false`.
- Motion authority was disabled.
- IRIV DI10 reported the E-Stop/KM1 circuit active.
- NUCLEO communication was unavailable.
- No Home, Jog, GOTO, Dispense, drive-power reset, Demo Sampling, ARM, or motion command was issued.

## Backup

Verified backup on the IRIV Pi:

`/home/admin/NaritVendingV1/backups/pre-controller-deploy-20260914-095508`

The backup contains the previous `narit_vending` package, both live IRIV
configuration files, installed systemd units, and an SQLite online backup of
`demo_results.sqlite3`. `SHA256SUMS.txt` verifies 201 files.

## Controller deployment

- Deployed only the `narit_vending` Python package.
- Preserved `machine_config.iriv.json`, `hardware_config.iriv.json`, SQLite
  files, the virtual environment, and systemd unit files.
- Validated the staged source against the live configuration before switching.
- Live configuration revision:
  `2e6fd60e0b4ee79c4e274c6f6602b5c722edb6a9f382557996d56388b5779a71`
- Controller and Web services returned `active` after restart.
- `/health/live` returned `UP`.
- `/health/ready` remained `DOWN`, which is expected while E-Stop is active
  and the NUCLEO link is unavailable.
- Deployed `motion.py` and `nucleo.py` SHA-256 values match the local source.

## Automated verification

The quality gate was run in a clean detached worktree so live-machine dirty
configuration files were neither modified nor used as source fixtures.

- Quality checks: 26 passed
- Python tests: 452 passed
- Subtests: 22 passed
- No Controller, GPIO, serial transport, or motion command was started by the tests.

## Firmware build

STM32CubeIDE 1.19.0 headless Release build completed with 0 errors and 3
warnings. The warnings are two intentionally unused Ethernet/USB-OTG init
functions and an ELF RWX load-segment linker warning. These warnings require
review before a production firmware release but did not prevent artifact
generation.

Generated local artifact directory:

`output/firmware-7fc3a65-20260914`

Artifact checksums:

```text
165bd332886d0cfe5618e8c5f862bcaf482cd9382116d64cf4131c4bfd55ef74  stm32_firmware_vending.bin
e6fd9df95fcb10c067b897f79f7ffb357dd6d0d9a30b836d0edb7a3b0ebd5d59  stm32_firmware_vending.elf
2f06a903f37b3958e09d164095c6ae3c09a55b1049e24a79e5ebb5db03b04739  stm32_firmware_vending.list
8f20eaa022ccbc9eb8cf260c6ba8d9affa8fc7f3f2f453695b842764771814fd  stm32_firmware_vending.map
```

## Blocked firmware gates

The firmware was **not flashed** for the following evidence-based reasons:

1. The configured ST-Link VCP path does not exist:
   `/dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_0666FF485753667187113533-if02`.
2. Linux currently exposes two QinHeng USB Dual Serial ports. Safe `PING`
   probes to both ports returned no response.
3. The built CubeIDE image is the current protocol-v3 firmware. It is not an
   implementation of the proposed Virtual Position Error / protocol-v4 planner.
4. Bench verification with STEP outputs disconnected has not been performed.
5. No explicit safe-area authorization for a specific axis, direction, and
   low test speed has been recorded.

## Required next actions

1. Confirm NUCLEO USB/ST-Link physical connection and identify the correct VCP.
2. Restore a successful `PING`/`STATUS` handshake without arming motion.
3. Verify STEP outputs are disconnected and complete the bench no-motion gate.
4. Implement and verify the new planner/protocol before labeling an artifact as
   Virtual-KP or protocol v4.
5. Flash only with a known-good rollback image available.
6. Obtain explicit operator safe-area authorization before any real motion test.

