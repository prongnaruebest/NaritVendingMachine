#ifndef NUCLEO_PROFILE_DISPATCHER_H
#define NUCLEO_PROFILE_DISPATCHER_H

#include "nucleo_profile_facade.h"

#include <stddef.h>
#include <stdint.h>

#define NUCLEO_PROFILE_COMMAND_LINE_MAX 1023U

typedef struct {
  NucleoProfileFacade *facade;
} NucleoProfileDispatcher;

void NucleoProfileDispatcher_Init(NucleoProfileDispatcher *dispatcher,
                                  NucleoProfileFacade *facade);
uint8_t NucleoProfileDispatcher_HandleLine(
    NucleoProfileDispatcher *dispatcher, const char *line,
    uint64_t now_us, uint8_t safety_permissive,
    uint8_t x_sensor_active, uint8_t y_sensor_active,
    char *response, size_t response_size);

#endif
