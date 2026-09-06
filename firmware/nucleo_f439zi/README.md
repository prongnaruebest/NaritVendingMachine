# NUCLEO-F439ZI safe communication link

The current motion-candidate source provides a USB virtual-COM health and
control channel. USB serial is the only NUCLEO communication transport;
Ethernet is not initialized.

- USART3 on PD8/PD9 (the ST-LINK/V2.1 virtual COM connection)
- 115200 baud, 8-N-1
- line commands: `PING` and `STATUS`
- JSON-line responses identify the board and protocol version
- all unknown commands are rejected
- Ethernet/LwIP/HTTP are disabled and the RJ45 connector is not part of the system wiring

Call `NucleoSerialLink_Start()` after `BSP_Config()` and before the RTOS
scheduler starts. The vending controller treats this heartbeat as a readiness
gate only; it does not use this firmware to energize motor signals.

## Motion candidate v2 (not flashed)

`nucleo_f439zi_motion_candidate_v2.bin` is a bench-test candidate built from
`NaritVendingV1/stm32`. It uses PA8/PB0 for X, PA9/PB1 for Y, and PA5/PB2 for
Z. It boots disarmed with STEP/DIR low, rejects MOVE while disarmed, permits
only 10-1000 Hz and at most 10000 steps, and disarms after 500 ms without a
valid safety heartbeat. Ethernet and the PB0-conflicting LED/HTTP demo are not started.

SHA-256: `7d0575a0a32cf320cd30547a1f8bd8044735db32dd6bf32114a41fa116270944`

The checked-in `.bin` files predate the USB-only source change. Rebuild and
bench-verify a new image before flashing; the SHA-256 above identifies the old
candidate and must not be used to identify a USB-only build.

Do not flash this candidate until DI10 E-stop polarity is commissioned and the
Z driver power is included in the hardwired safety removal path. The currently
deployed safe-link firmware remains the approved communication-only image.
