#ifndef NUCLEO_DYNAMIC_TELEMETRY_H
#define NUCLEO_DYNAMIC_TELEMETRY_H

#include "nucleo_dynamic_facade.h"

#include <stddef.h>
#include <stdint.h>

uint8_t NucleoDynamicTelemetry_Write(const NucleoDynamicFacade *facade,
                                     char *response, size_t response_size);

#endif
