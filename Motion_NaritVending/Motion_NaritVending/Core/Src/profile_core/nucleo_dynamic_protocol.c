#include "nucleo_dynamic_protocol.h"

#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define DYNAMIC_LINE_MAX 320U
#define DYNAMIC_CONFIG_TOKEN_COUNT 12U
#define DYNAMIC_TARGET_TOKEN_COUNT 5U
#define DYNAMIC_POSITION_TOKEN_COUNT 4U
#define DYNAMIC_START_TOKEN_COUNT 3U

static uint8_t valid_identifier(const char *value)
{
  size_t index;
  size_t length;
  if (value == NULL) return 0U;
  length = strlen(value);
  if ((length == 0U) || (length > NUCLEO_DYNAMIC_IDENTIFIER_MAX)) return 0U;
  for (index = 0U; index < length; ++index) {
    char c = value[index];
    uint8_t valid = ((c >= 'A') && (c <= 'Z')) ||
                    ((c >= 'a') && (c <= 'z')) ||
                    ((c >= '0') && (c <= '9')) || (c == '_') ||
                    (c == '.') || (c == ':') || (c == '-');
    if ((index == 0U) && !(((c >= 'A') && (c <= 'Z')) ||
                           ((c >= 'a') && (c <= 'z')) ||
                           ((c >= '0') && (c <= '9')))) return 0U;
    if (valid == 0U) return 0U;
  }
  return 1U;
}

static uint8_t parse_u32(const char *value, uint32_t *parsed)
{
  char *end = NULL;
  unsigned long result;
  if ((value == NULL) || (parsed == NULL) || (*value == '\0') || (*value == '-')) return 0U;
  result = strtoul(value, &end, 10);
  if ((*end != '\0') || (result > 0xffffffffUL)) return 0U;
  *parsed = (uint32_t)result;
  return 1U;
}

static uint8_t parse_axis(const char *value, uint8_t *axis)
{
  if ((value == NULL) || (axis == NULL) || (value[1] != '\0')) return 0U;
  if ((value[0] == 'X') || (value[0] == 'x')) *axis = 0U;
  else if ((value[0] == 'Y') || (value[0] == 'y')) *axis = 1U;
  else return 0U;
  return 1U;
}

static uint8_t tokenize(const char *line, char *copy, char **tokens,
                        uint8_t capacity, uint8_t *count)
{
  char *token;
  size_t length;
  if ((line == NULL) || (copy == NULL) || (tokens == NULL) || (count == NULL)) return 0U;
  length = strlen(line);
  if ((length == 0U) || (length >= DYNAMIC_LINE_MAX)) return 0U;
  memcpy(copy, line, length + 1U);
  *count = 0U;
  token = strtok(copy, " ");
  while (token != NULL) {
    if (*count >= capacity) return 0U;
    tokens[(*count)++] = token;
    token = strtok(NULL, " ");
  }
  return 1U;
}

void NucleoDynamicProtocol_Init(NucleoDynamicProtocolState *state)
{
  if (state != NULL) memset(state, 0, sizeof(*state));
}

NucleoDynamicProtocolResult NucleoDynamicProtocol_ApplyConfig(
    NucleoDynamicProtocolState *state, const char *line, uint8_t armed)
{
  char copy[DYNAMIC_LINE_MAX];
  char *tokens[DYNAMIC_CONFIG_TOKEN_COUNT];
  uint8_t count = 0U;
  uint8_t axis;
  uint32_t values[9];
  uint8_t index;
  NucleoDynamicAxisProtocolConfig next;
  if ((state == NULL) || (line == NULL)) return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  if (armed != 0U) return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  if ((tokenize(line, copy, tokens, DYNAMIC_CONFIG_TOKEN_COUNT, &count) == 0U) ||
      (count != DYNAMIC_CONFIG_TOKEN_COUNT) ||
      (strcmp(tokens[0], "DYN_CONFIG") != 0)) return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  if (parse_axis(tokens[1], &axis) == 0U) return NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS;
  for (index = 0U; index < 9U; ++index) {
    if (parse_u32(tokens[index + 2U], &values[index]) == 0U) {
      return NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE;
    }
  }
  if ((values[1] <= values[0]) || (values[2] == 0U) || (values[3] > 1U) ||
      ((values[3] != 0U) && (values[4] == 0U)) || (values[5] == 0U) ||
      (values[5] > 50000000U) ||
      (values[6] == 0U) || (values[7] == 0U) || (values[8] == 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE;
  }
  if (valid_identifier(tokens[11]) == 0U) return NUCLEO_DYNAMIC_PROTOCOL_ERR_REVISION;
  memset(&next, 0, sizeof(next));
  next.travel_min_pulses = values[0];
  next.travel_max_pulses = values[1];
  next.pulses_per_mm_milli = values[2];
  next.kp_enabled = (uint8_t)values[3];
  next.kp_approach_milliper_s = values[4];
  next.max_velocity_millihz = values[5];
  next.max_acceleration_millihz_s = values[6];
  next.max_deceleration_millihz_s = values[7];
  next.max_jerk_millihz_s2 = values[8];
  strcpy(next.configuration_revision, tokens[11]);
  next.valid = 1U;
  state->config[axis] = next;
  /* Scale/travel changes make the old open-loop pulse coordinate unsafe. */
  state->position_valid[axis] = 0U;
  state->last_command_id[axis][0] = '\0';
  return NUCLEO_DYNAMIC_PROTOCOL_OK;
}

NucleoDynamicProtocolResult NucleoDynamicProtocol_SetPosition(
    NucleoDynamicProtocolState *state, uint8_t axis,
    uint32_t estimated_position_pulses)
{
  if ((state == NULL) || (axis >= NUCLEO_DYNAMIC_AXIS_COUNT)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS;
  }
  if ((state->config[axis].valid == 0U) ||
      (estimated_position_pulses < state->config[axis].travel_min_pulses) ||
      (estimated_position_pulses > state->config[axis].travel_max_pulses)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE;
  }
  state->estimated_position_pulses[axis] = estimated_position_pulses;
  state->position_valid[axis] = 1U;
  return NUCLEO_DYNAMIC_PROTOCOL_OK;
}

NucleoDynamicProtocolResult NucleoDynamicProtocol_ApplyPosition(
    NucleoDynamicProtocolState *state, const char *line, uint8_t armed)
{
  char copy[DYNAMIC_LINE_MAX];
  char *tokens[DYNAMIC_POSITION_TOKEN_COUNT];
  uint8_t count = 0U;
  uint8_t axis;
  uint32_t estimated_position_pulses;
  if ((state == NULL) || (line == NULL)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  }
  if (armed != 0U) return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  if ((tokenize(line, copy, tokens, DYNAMIC_POSITION_TOKEN_COUNT, &count) == 0U) ||
      (count != DYNAMIC_POSITION_TOKEN_COUNT) ||
      (strcmp(tokens[0], "DYN_POSITION") != 0)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  }
  if (parse_axis(tokens[1], &axis) == 0U) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS;
  }
  if (parse_u32(tokens[2], &estimated_position_pulses) == 0U) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE;
  }
  if ((state->config[axis].valid == 0U) ||
      (strcmp(tokens[3], state->config[axis].configuration_revision) != 0)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_REVISION;
  }
  return NucleoDynamicProtocol_SetPosition(state, axis,
                                           estimated_position_pulses);
}

NucleoDynamicProtocolResult NucleoDynamicProtocol_ParseTarget(
    NucleoDynamicProtocolState *state, const char *line, uint8_t busy,
    NucleoDynamicTarget *target)
{
  char copy[DYNAMIC_LINE_MAX];
  char *tokens[DYNAMIC_TARGET_TOKEN_COUNT];
  uint8_t count = 0U;
  uint8_t axis;
  uint32_t target_position_pulses;
  NucleoDynamicAxisProtocolConfig *config;
  if ((state == NULL) || (line == NULL) || (target == NULL)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  }
  if ((tokenize(line, copy, tokens, DYNAMIC_TARGET_TOKEN_COUNT, &count) == 0U) ||
      (count != DYNAMIC_TARGET_TOKEN_COUNT) ||
      (strcmp(tokens[0], "DYN_TARGET") != 0) ||
      (valid_identifier(tokens[1]) == 0U)) return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  if (parse_axis(tokens[2], &axis) == 0U) return NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS;
  if (parse_u32(tokens[3], &target_position_pulses) == 0U) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE;
  }
  config = &state->config[axis];
  if ((config->valid == 0U) || (strcmp(tokens[4], config->configuration_revision) != 0)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_REVISION;
  }
  if (state->position_valid[axis] == 0U) return NUCLEO_DYNAMIC_PROTOCOL_ERR_POSITION;
  if ((target_position_pulses < config->travel_min_pulses) ||
      (target_position_pulses > config->travel_max_pulses)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE;
  }
  if (strcmp(tokens[1], state->last_command_id[axis]) == 0) {
    if ((target_position_pulses == state->last_target_position_pulses[axis]) &&
        (strcmp(tokens[4], state->last_command_revision[axis]) == 0)) {
      return NUCLEO_DYNAMIC_PROTOCOL_DUPLICATE;
    }
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_CONFLICT;
  }
  if (busy != 0U) return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  memset(target, 0, sizeof(*target));
  target->axis = axis;
  target->target_position_pulses = target_position_pulses;
  target->direction = target_position_pulses >= state->estimated_position_pulses[axis] ? 1U : 0U;
  target->distance_pulses = target_position_pulses >= state->estimated_position_pulses[axis]
      ? target_position_pulses - state->estimated_position_pulses[axis]
      : state->estimated_position_pulses[axis] - target_position_pulses;
  strcpy(target->command_id, tokens[1]);
  strcpy(target->configuration_revision, tokens[4]);
  return NUCLEO_DYNAMIC_PROTOCOL_OK;
}

void NucleoDynamicProtocol_CommitTarget(
    NucleoDynamicProtocolState *state, const NucleoDynamicTarget *target)
{
  uint8_t axis;
  if ((state == NULL) || (target == NULL) ||
      (target->axis >= NUCLEO_DYNAMIC_AXIS_COUNT)) return;
  axis = target->axis;
  state->estimated_position_pulses[axis] = target->target_position_pulses;
  state->last_target_position_pulses[axis] = target->target_position_pulses;
  strcpy(state->last_command_id[axis], target->command_id);
  strcpy(state->last_command_revision[axis], target->configuration_revision);
}

NucleoDynamicProtocolResult NucleoDynamicProtocol_ParseStart(
    const char *line, NucleoDynamicStart *start)
{
  char copy[DYNAMIC_LINE_MAX];
  char *tokens[DYNAMIC_START_TOKEN_COUNT];
  uint8_t count = 0U;
  if ((line == NULL) || (start == NULL)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  }
  if ((tokenize(line, copy, tokens, DYNAMIC_START_TOKEN_COUNT, &count) == 0U) ||
      (count != DYNAMIC_START_TOKEN_COUNT) ||
      (strcmp(tokens[0], "DYN_START") != 0) ||
      (valid_identifier(tokens[1]) == 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT;
  }
  if (strcmp(tokens[2], "X") == 0) start->axis_mask = 1U;
  else if (strcmp(tokens[2], "Y") == 0) start->axis_mask = 2U;
  else if (strcmp(tokens[2], "XY") == 0) start->axis_mask = 3U;
  else return NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS;
  strcpy(start->command_id, tokens[1]);
  return NUCLEO_DYNAMIC_PROTOCOL_OK;
}
