#ifndef NUCLEO_PROFILE_TELEMETRY_H
#define NUCLEO_PROFILE_TELEMETRY_H

#include "nucleo_profile_runtime.h"

#include <stddef.h>
#include <stdint.h>

#ifndef NUCLEO_XY_PROFILE_TELEMETRY_ENABLED
#define NUCLEO_XY_PROFILE_TELEMETRY_ENABLED 0
#endif

/* Candidate read-only command. It is deliberately not wired into protocol v3. */
uint8_t NucleoProfileTelemetry_HandleLine(
    const NucleoProfileRuntime *runtime, const char *line,
    char *response, size_t response_size);

#endif
