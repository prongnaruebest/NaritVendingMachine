#ifndef NUCLEO_DYNAMIC_FACADE_H
#define NUCLEO_DYNAMIC_FACADE_H

#include "nucleo_dynamic_coordinator.h"
#include "nucleo_dynamic_protocol.h"

#include <stdint.h>

typedef struct {
  NucleoDynamicProtocolState protocol;
  NucleoDynamicCoordinator coordinator;
  NucleoDynamicRuntimeHooks hooks;
  NucleoDynamicTarget staged[NUCLEO_DYNAMIC_AXIS_COUNT];
  uint8_t staged_mask;
  uint8_t initialized;
  uint8_t runtime_ready;
} NucleoDynamicFacade;

uint8_t NucleoDynamicFacade_Init(NucleoDynamicFacade *facade,
                                 NucleoDynamicRuntimeHooks hooks);
NucleoDynamicProtocolResult NucleoDynamicFacade_ApplyConfig(
    NucleoDynamicFacade *facade, const char *line, uint8_t armed);
NucleoDynamicProtocolResult NucleoDynamicFacade_SetPosition(
    NucleoDynamicFacade *facade, uint8_t axis,
    uint32_t estimated_position_pulses);
NucleoDynamicProtocolResult NucleoDynamicFacade_StageTarget(
    NucleoDynamicFacade *facade, const char *line);
NucleoDynamicProtocolResult NucleoDynamicFacade_Start(
    NucleoDynamicFacade *facade, const char *command_id, uint8_t axis_mask,
    uint64_t now_us, uint8_t safety_permissive);
void NucleoDynamicFacade_Heartbeat(NucleoDynamicFacade *facade,
                                   uint64_t now_us,
                                   uint8_t safety_permissive);
void NucleoDynamicFacade_ControlTick(NucleoDynamicFacade *facade,
                                     uint64_t now_us);
uint8_t NucleoDynamicFacade_OnEmittedPulse(void *context, uint8_t axis);
void NucleoDynamicFacade_Stop(NucleoDynamicFacade *facade);
void NucleoDynamicFacade_ControlledStop(NucleoDynamicFacade *facade);
void NucleoDynamicFacade_Disarm(NucleoDynamicFacade *facade);

#endif
