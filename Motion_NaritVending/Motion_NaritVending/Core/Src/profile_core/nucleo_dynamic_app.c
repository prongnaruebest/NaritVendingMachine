#include "nucleo_dynamic_app.h"

#include <string.h>

uint8_t NucleoDynamicApp_Init(NucleoDynamicApp *app,
                              NucleoDynamicRuntimeHooks runtime_hooks,
                              NucleoDynamicEmergencyInhibitFn emergency_inhibit,
                              void *emergency_context)
{
  if (app == NULL) return 0U;
  memset(app, 0, sizeof(*app));
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if ((emergency_inhibit == NULL) ||
      (NucleoDynamicFacade_Init(&app->facade, runtime_hooks) == 0U)) {
    return 0U;
  }
  app->emergency_inhibit = emergency_inhibit;
  app->emergency_context = emergency_context;
  NucleoDynamicDispatcher_Init(&app->dispatcher, &app->facade);
  app->initialized = 1U;
  return 1U;
#else
  (void)runtime_hooks;
  (void)emergency_inhibit;
  (void)emergency_context;
  return 0U;
#endif
}

uint8_t NucleoDynamicApp_HandleLine(
    NucleoDynamicApp *app, const char *line, uint64_t now_us,
    uint8_t safety_permissive, uint8_t armed, char *response,
    size_t response_size)
{
  if ((app == NULL) || (app->initialized == 0U) || (line == NULL)) return 0U;
  /* STOP/DISARM inhibit the established motion path before parsing or ACK.
   * This keeps emergency priority above all candidate protocol state. */
  if ((strcmp(line, "STOP") == 0) || (strcmp(line, "DISARM") == 0)) {
    app->emergency_inhibit(app->emergency_context);
  }
  return NucleoDynamicDispatcher_HandleLine(
      &app->dispatcher, line, now_us, safety_permissive, armed,
      response, response_size);
}

void NucleoDynamicApp_Heartbeat(NucleoDynamicApp *app, uint64_t now_us,
                                uint8_t safety_permissive)
{
  if ((app != NULL) && (app->initialized != 0U)) {
    NucleoDynamicFacade_Heartbeat(&app->facade, now_us, safety_permissive);
  }
}

void NucleoDynamicApp_ControlTick(NucleoDynamicApp *app, uint64_t now_us)
{
  if ((app != NULL) && (app->initialized != 0U)) {
    NucleoDynamicFacade_ControlTick(&app->facade, now_us);
  }
}

uint8_t NucleoDynamicApp_OnEmittedPulse(void *context, uint8_t axis)
{
  NucleoDynamicApp *app = (NucleoDynamicApp *)context;
  if ((app == NULL) || (app->initialized == 0U)) return 0U;
  return NucleoDynamicFacade_OnEmittedPulse(&app->facade, axis);
}

void NucleoDynamicApp_EmergencyStop(NucleoDynamicApp *app)
{
  if ((app == NULL) || (app->initialized == 0U)) return;
  app->emergency_inhibit(app->emergency_context);
  NucleoDynamicFacade_Stop(&app->facade);
}
