#ifndef STEPPER_CTRL_H
#define STEPPER_CTRL_H

#include <stdint.h>
#include "stm32f4xx_hal.h"

#define AXIS_X 0
#define AXIS_Y 1
#define AXIS_Z 2

#define DIR_CW 1
#define DIR_CCW 0

void Stepper_Init(void);
void Stepper_Move(uint8_t axis, uint8_t dir, uint32_t steps, uint32_t speed_hz);
uint8_t Stepper_IsMoving(uint8_t axis);

#endif

