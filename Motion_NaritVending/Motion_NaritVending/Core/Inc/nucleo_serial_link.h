#ifndef NUCLEO_SERIAL_LINK_H
#define NUCLEO_SERIAL_LINK_H

#include "stm32g4xx_hal.h"

/* ST-LINK exposes LPUART1 on PA2/PA3 as the board USB virtual COM port. */
void NucleoSerialLink_Start(UART_HandleTypeDef *uart);
void NucleoSerialLink_Poll(void);

#endif /* NUCLEO_SERIAL_LINK_H */
