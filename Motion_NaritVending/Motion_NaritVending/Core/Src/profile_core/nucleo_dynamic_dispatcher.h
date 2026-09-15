#ifndef NUCLEO_DYNAMIC_DISPATCHER_H
#define NUCLEO_DYNAMIC_DISPATCHER_H

#include "nucleo_dynamic_facade.h"

#include <stddef.h>
#include <stdint.h>

#ifndef NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED
#define NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED 0
#endif

#define NUCLEO_DYNAMIC_COMMAND_LINE_MAX 319U

typedef struct {
  NucleoDynamicFacade *facade;
} NucleoDynamicDispatcher;

void NucleoDynamicDispatcher_Init(NucleoDynamicDispatcher *dispatcher,
                                  NucleoDynamicFacade *facade);
uint8_t NucleoDynamicDispatcher_HandleLine(
    NucleoDynamicDispatcher *dispatcher, const char *line, uint64_t now_us,
    uint8_t safety_permissive, uint8_t armed, char *response,
    size_t response_size);

#endif
