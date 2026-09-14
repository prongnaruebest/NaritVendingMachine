#ifndef NUCLEO_CONTROL_TICK_H
#define NUCLEO_CONTROL_TICK_H

#include <stdint.h>

#define NUCLEO_CONTROL_PERIOD_US 1000ULL
#define NUCLEO_CONTROL_WATCHDOG_US 500000ULL
#define NUCLEO_CONTROL_MAX_TICK_GAP_US 2000ULL

typedef void (*NucleoControlTickFn)(void *context, uint64_t now_us);
typedef void (*NucleoControlStopFn)(void *context);

typedef struct {
  NucleoControlTickFn control_tick;
  NucleoControlStopFn safety_stop;
  void *context;
} NucleoControlTickHooks;

typedef struct {
  NucleoControlTickHooks hooks;
  uint64_t last_tick_us;
  uint64_t last_heartbeat_us;
  uint32_t tick_count;
  uint8_t armed;
  uint8_t faulted;
} NucleoControlTick;

uint8_t NucleoControlTick_Init(NucleoControlTick *control,
                               NucleoControlTickHooks hooks);
uint8_t NucleoControlTick_Arm(NucleoControlTick *control, uint64_t now_us,
                              uint8_t safety_permissive);
void NucleoControlTick_Heartbeat(NucleoControlTick *control, uint64_t now_us,
                                uint8_t safety_permissive);
void NucleoControlTick_OnTimer(NucleoControlTick *control, uint64_t now_us,
                               uint8_t safety_permissive);
void NucleoControlTick_Disarm(NucleoControlTick *control);

#endif
