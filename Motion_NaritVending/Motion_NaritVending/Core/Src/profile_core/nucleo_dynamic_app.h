#ifndef NUCLEO_DYNAMIC_APP_H
#define NUCLEO_DYNAMIC_APP_H

#include "nucleo_dynamic_dispatcher.h"

#include <stddef.h>
#include <stdint.h>

typedef void (*NucleoDynamicEmergencyInhibitFn)(void *context);

typedef struct {
  NucleoDynamicFacade facade;
  NucleoDynamicDispatcher dispatcher;
  NucleoDynamicEmergencyInhibitFn emergency_inhibit;
  void *emergency_context;
  uint8_t initialized;
} NucleoDynamicApp;

uint8_t NucleoDynamicApp_Init(NucleoDynamicApp *app,
                              NucleoDynamicRuntimeHooks runtime_hooks,
                              NucleoDynamicEmergencyInhibitFn emergency_inhibit,
                              void *emergency_context);
uint8_t NucleoDynamicApp_HandleLine(
    NucleoDynamicApp *app, const char *line, uint64_t now_us,
    uint8_t safety_permissive, uint8_t armed, char *response,
    size_t response_size);
void NucleoDynamicApp_Heartbeat(NucleoDynamicApp *app, uint64_t now_us,
                                uint8_t safety_permissive);
void NucleoDynamicApp_ControlTick(NucleoDynamicApp *app, uint64_t now_us);
uint8_t NucleoDynamicApp_OnEmittedPulse(void *context, uint8_t axis);
void NucleoDynamicApp_EmergencyStop(NucleoDynamicApp *app);

#endif
