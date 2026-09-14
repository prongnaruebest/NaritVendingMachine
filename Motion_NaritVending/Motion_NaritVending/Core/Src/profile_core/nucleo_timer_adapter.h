#ifndef NUCLEO_TIMER_ADAPTER_H
#define NUCLEO_TIMER_ADAPTER_H

#include <stdint.h>

#define NUCLEO_TIMER_AXIS_COUNT 2U
#define NUCLEO_TIMER_MAX_RATE_MILLIHZ 50000000U

typedef uint8_t (*NucleoTimerApplyFn)(void *context, uint8_t axis,
                                     uint16_t prescaler, uint16_t period,
                                     uint16_t pulse_width);
typedef void (*NucleoTimerEnableFn)(void *context, uint8_t axis);
typedef void (*NucleoTimerDisableFn)(void *context, uint8_t axis);

typedef struct {
  NucleoTimerApplyFn apply_atomic;
  NucleoTimerEnableFn enable;
  NucleoTimerDisableFn disable;
  void *context;
} NucleoTimerPort;

typedef struct {
  uint32_t timer_clock_hz;
  uint32_t pulse_width_us;
  NucleoTimerPort port;
  uint32_t rate_millihz[NUCLEO_TIMER_AXIS_COUNT];
  uint8_t enabled[NUCLEO_TIMER_AXIS_COUNT];
  uint8_t faulted;
} NucleoTimerAdapter;

uint8_t NucleoTimerAdapter_Init(NucleoTimerAdapter *adapter,
                                uint32_t timer_clock_hz,
                                uint32_t pulse_width_us,
                                NucleoTimerPort port);
uint8_t NucleoTimerAdapter_SetRate(NucleoTimerAdapter *adapter, uint8_t axis,
                                   uint32_t rate_millihz);
void NucleoTimerAdapter_DisableAxis(NucleoTimerAdapter *adapter, uint8_t axis);
void NucleoTimerAdapter_DisableAll(NucleoTimerAdapter *adapter);
void NucleoTimerAdapter_SetRateHook(void *context, uint8_t axis,
                                    uint32_t rate_millihz);
void NucleoTimerAdapter_DisableAxisHook(void *context, uint8_t axis);

#endif
