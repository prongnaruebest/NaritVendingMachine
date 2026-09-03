#ifndef NUCLEO_MOTION_H
#define NUCLEO_MOTION_H

#include <stdint.h>
#include "stm32f4xx_hal.h"

#define AXIS_X 0U
#define AXIS_Y 1U
#define AXIS_Z 2U

#define DIR_CW 1U
#define DIR_CCW 0U

#define NUCLEO_MOTION_MIN_SPEED_HZ 10U
#define NUCLEO_MOTION_MAX_SPEED_HZ 1000U
#define NUCLEO_MOTION_MAX_STEPS 10000U
#define NUCLEO_MOTION_WATCHDOG_MS 500U

typedef enum {
    NUCLEO_MOTION_OK = 0,
    NUCLEO_MOTION_ERR_NOT_ARMED,
    NUCLEO_MOTION_ERR_WATCHDOG,
    NUCLEO_MOTION_ERR_ARGUMENT,
    NUCLEO_MOTION_ERR_BUSY
} NucleoMotionResult;

#ifdef __cplusplus
extern "C" {
#endif

void NucleoMotion_Init(void);
uint8_t NucleoMotion_Arm(uint8_t safety_permissive);
void NucleoMotion_Heartbeat(uint8_t safety_permissive);
void NucleoMotion_Disarm(void);
void NucleoMotion_StopAll(void);
void NucleoMotion_Poll(void);
uint8_t NucleoMotion_IsArmed(void);
uint8_t NucleoMotion_WatchdogHealthy(void);
NucleoMotionResult Stepper_Move(uint8_t axis, uint8_t dir,
                               uint32_t steps, uint32_t speed_hz);
uint8_t Stepper_IsMoving(uint8_t axis);

#ifdef __cplusplus
}
#endif

#endif /* NUCLEO_MOTION_H */

