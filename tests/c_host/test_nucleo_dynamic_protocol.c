#include "nucleo_dynamic_protocol.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
  NucleoDynamicProtocolState state;
  NucleoDynamicTarget target;
  const char *config_x =
      "DYN_CONFIG X 0 117000 68824 1 2500 2064720 6882400 6882400 68824000 cfg-42";

  NucleoDynamicProtocol_Init(&state);
  assert(NucleoDynamicProtocol_ApplyConfig(&state, config_x, 1U) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE);
  assert(NucleoDynamicProtocol_ApplyConfig(&state, config_x, 0U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(state.config[0].valid == 1U);
  assert(state.position_valid[0] == 0U);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-1 X 100000 cfg-42", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_POSITION);
  assert(NucleoDynamicProtocol_SetPosition(&state, 0U, 500U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-1 X 100000 stale", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_REVISION);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-1 X 117001 cfg-42", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-1 X 100000 cfg-42", 1U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-1 X 100000 cfg-42", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(target.axis == 0U && target.direction == 1U &&
         target.distance_pulses == 99500U);
  NucleoDynamicProtocol_CommitTarget(&state, &target);
  assert(state.estimated_position_pulses[0] == 100000U);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-1 X 100000 cfg-42", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_DUPLICATE);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-1 X 90000 cfg-42", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_CONFLICT);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET move-2 X 90000 cfg-42", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(target.direction == 0U && target.distance_pulses == 10000U);

  assert(NucleoDynamicProtocol_ApplyConfig(
             &state,
             "DYN_CONFIG Z 0 100 1000 0 0 1000 1000 1000 1000 cfg-42",
             0U) == NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS);
  assert(NucleoDynamicProtocol_ApplyConfig(
             &state,
             "DYN_CONFIG X 0 0 1000 0 0 1000 1000 1000 1000 cfg-42",
             0U) == NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE);
  assert(NucleoDynamicProtocol_ApplyConfig(
             &state,
             "DYN_CONFIG X 0 100 1000 0 0 1000 1000 1000 1000 bad revision",
             0U) == NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT);
  assert(NucleoDynamicProtocol_ApplyConfig(
             &state,
             "DYN_CONFIG X 0 100 1000 1 1000 50000001 1000 1000 1000 cfg-43",
             0U) == NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE);
  assert(NucleoDynamicProtocol_ParseTarget(
             &state, "DYN_TARGET", 0U, &target) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT);
  puts("dynamic protocol host tests passed");
  return 0;
}
