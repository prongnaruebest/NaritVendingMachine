#ifndef NUCLEO_SERIAL_LINK_H
#define NUCLEO_SERIAL_LINK_H

#include "stm32f4xx_hal.h"

/* ST-LINK exposes USART3 as the board's USB virtual COM port. */
void NucleoSerialLink_Start(UART_HandleTypeDef *uart);
void NucleoSerialLink_Poll(void);

#endif
