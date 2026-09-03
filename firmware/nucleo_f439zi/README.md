# NUCLEO-F439ZI safe communication link

This module adds a USB virtual-COM health channel to the existing ST
`LwIP_HTTP_Server_Netconn_RTOS` firmware without enabling motion outputs.

- USART3 on PD8/PD9 (the ST-LINK/V2.1 virtual COM connection)
- 115200 baud, 8-N-1
- line commands: `PING` and `STATUS`
- JSON-line responses identify the board and protocol version
- all unknown commands are rejected
- Ethernet uses static `192.168.70.81/24` with gateway `192.168.70.1`; DHCP is disabled
- the Ethernet HTTP endpoint is retained for link-level commissioning only

Call `NucleoSerialLink_Start()` after `BSP_Config()` and before the RTOS
scheduler starts. The vending controller treats this heartbeat as a readiness
gate only; it does not use this firmware to energize motor signals.

## Motion candidate v2 (not flashed)

`nucleo_f439zi_motion_candidate_v2.bin` is a bench-test candidate built from
`NaritVendingV1/stm32`. It uses PA8/PB0 for X, PA9/PB1 for Y, and PA5/PB2 for
Z. It boots disarmed with STEP/DIR low, rejects MOVE while disarmed, permits
only 10-1000 Hz and at most 10000 steps, and disarms after 500 ms without a
valid safety heartbeat. The PB0-conflicting LED/HTTP demo is not started.

SHA-256: `7d0575a0a32cf320cd30547a1f8bd8044735db32dd6bf32114a41fa116270944`

Do not flash this candidate until DI10 E-stop polarity is commissioned and the
Z driver power is included in the hardwired safety removal path. The currently
deployed safe-link firmware remains the approved communication-only image.
