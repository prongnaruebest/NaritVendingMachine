#ifndef NUCLEO_COMPARE_ADAPTER_H
#define NUCLEO_COMPARE_ADAPTER_H

#include <stdint.h>

#define NUCLEO_COMPARE_AXIS_COUNT 2U
#define NUCLEO_COMPARE_MAX_RATE_MILLIHZ 50000000U

typedef uint8_t (*NucleoCompareApplyFn)(void *context, uint8_t axis,
                                       uint32_t half_period_ticks);
typedef void (*NucleoCompareEnableFn)(void *context, uint8_t axis);
typedef void (*NucleoCompareDisableFn)(void *context, uint8_t axis);

typedef struct {
  NucleoCompareApplyFn apply_half_period_atomic;
  NucleoCompareEnableFn enable_channel;
  NucleoCompareDisableFn disable_channel;
  void *context;
} NucleoComparePort;

typedef struct {
  uint32_t timer_tick_hz;
  NucleoComparePort port;
  uint32_t half_period_ticks[NUCLEO_COMPARE_AXIS_COUNT];
  uint8_t enabled[NUCLEO_COMPARE_AXIS_COUNT];
  uint8_t faulted;
} NucleoCompareAdapter;

uint8_t NucleoCompareAdapter_Init(NucleoCompareAdapter *adapter,
                                  uint32_t timer_tick_hz,
                                  NucleoComparePort port);
uint8_t NucleoCompareAdapter_SetRate(NucleoCompareAdapter *adapter,
                                     uint8_t axis,
                                     uint32_t rate_millihz);
void NucleoCompareAdapter_DisableAxis(NucleoCompareAdapter *adapter,
                                      uint8_t axis);
void NucleoCompareAdapter_DisableAll(NucleoCompareAdapter *adapter);

#endif
