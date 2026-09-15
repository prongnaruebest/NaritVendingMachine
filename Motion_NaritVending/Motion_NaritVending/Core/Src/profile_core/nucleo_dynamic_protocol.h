#ifndef NUCLEO_DYNAMIC_PROTOCOL_H
#define NUCLEO_DYNAMIC_PROTOCOL_H

#include <stdint.h>

#define NUCLEO_DYNAMIC_AXIS_COUNT 2U
#define NUCLEO_DYNAMIC_IDENTIFIER_MAX 64U

typedef enum {
  NUCLEO_DYNAMIC_PROTOCOL_OK = 0,
  NUCLEO_DYNAMIC_PROTOCOL_DUPLICATE,
  NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT,
  NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS,
  NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE,
  NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE,
  NUCLEO_DYNAMIC_PROTOCOL_ERR_REVISION,
  NUCLEO_DYNAMIC_PROTOCOL_ERR_POSITION,
  NUCLEO_DYNAMIC_PROTOCOL_ERR_CONFLICT
} NucleoDynamicProtocolResult;

typedef struct {
  uint32_t travel_min_pulses;
  uint32_t travel_max_pulses;
  uint32_t pulses_per_mm_milli;
  uint32_t kp_approach_milliper_s;
  uint32_t max_velocity_millihz;
  uint32_t max_acceleration_millihz_s;
  uint32_t max_deceleration_millihz_s;
  uint32_t max_jerk_millihz_s2;
  char configuration_revision[NUCLEO_DYNAMIC_IDENTIFIER_MAX + 1U];
  uint8_t kp_enabled;
  uint8_t valid;
} NucleoDynamicAxisProtocolConfig;

typedef struct {
  uint8_t axis;
  uint8_t direction;
  uint32_t target_position_pulses;
  uint32_t distance_pulses;
  char command_id[NUCLEO_DYNAMIC_IDENTIFIER_MAX + 1U];
  char configuration_revision[NUCLEO_DYNAMIC_IDENTIFIER_MAX + 1U];
} NucleoDynamicTarget;

typedef struct {
  char command_id[NUCLEO_DYNAMIC_IDENTIFIER_MAX + 1U];
  uint8_t axis_mask;
} NucleoDynamicStart;

typedef struct {
  NucleoDynamicAxisProtocolConfig config[NUCLEO_DYNAMIC_AXIS_COUNT];
  uint32_t estimated_position_pulses[NUCLEO_DYNAMIC_AXIS_COUNT];
  uint32_t last_target_position_pulses[NUCLEO_DYNAMIC_AXIS_COUNT];
  char last_command_id[NUCLEO_DYNAMIC_AXIS_COUNT][NUCLEO_DYNAMIC_IDENTIFIER_MAX + 1U];
  char last_command_revision[NUCLEO_DYNAMIC_AXIS_COUNT][NUCLEO_DYNAMIC_IDENTIFIER_MAX + 1U];
  uint8_t position_valid[NUCLEO_DYNAMIC_AXIS_COUNT];
} NucleoDynamicProtocolState;

void NucleoDynamicProtocol_Init(NucleoDynamicProtocolState *state);
NucleoDynamicProtocolResult NucleoDynamicProtocol_ApplyConfig(
    NucleoDynamicProtocolState *state, const char *line, uint8_t armed);
NucleoDynamicProtocolResult NucleoDynamicProtocol_SetPosition(
    NucleoDynamicProtocolState *state, uint8_t axis,
    uint32_t estimated_position_pulses);
NucleoDynamicProtocolResult NucleoDynamicProtocol_ApplyPosition(
    NucleoDynamicProtocolState *state, const char *line, uint8_t armed);
NucleoDynamicProtocolResult NucleoDynamicProtocol_ParseTarget(
    NucleoDynamicProtocolState *state, const char *line, uint8_t busy,
    NucleoDynamicTarget *target);
NucleoDynamicProtocolResult NucleoDynamicProtocol_ParseStart(
    const char *line, NucleoDynamicStart *start);
void NucleoDynamicProtocol_CommitTarget(
    NucleoDynamicProtocolState *state, const NucleoDynamicTarget *target);

#endif
