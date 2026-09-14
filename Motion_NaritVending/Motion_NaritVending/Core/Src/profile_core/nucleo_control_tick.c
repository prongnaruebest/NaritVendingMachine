#include "nucleo_control_tick.h"

#include <stddef.h>
#include <string.h>

static void latch_safety_stop(NucleoControlTick *control)
{
  control->armed = 0U;
  control->faulted = 1U;
  if (control->hooks.safety_stop != NULL) {
    control->hooks.safety_stop(control->hooks.context);
  }
}

uint8_t NucleoControlTick_Init(NucleoControlTick *control,
                               NucleoControlTickHooks hooks)
{
  if ((control == NULL) || (hooks.control_tick == NULL) ||
      (hooks.safety_stop == NULL)) return 0U;
  memset(control, 0, sizeof(*control));
  control->hooks = hooks;
  return 1U;
}

uint8_t NucleoControlTick_Arm(NucleoControlTick *control, uint64_t now_us,
                              uint8_t safety_permissive)
{
  if ((control == NULL) || (safety_permissive == 0U) ||
      (control->faulted != 0U)) return 0U;
  control->last_tick_us = now_us;
  control->last_heartbeat_us = now_us;
  control->armed = 1U;
  return 1U;
}

void NucleoControlTick_Heartbeat(NucleoControlTick *control, uint64_t now_us,
                                uint8_t safety_permissive)
{
  if ((control == NULL) || (control->armed == 0U)) return;
  if ((safety_permissive == 0U) || (now_us < control->last_heartbeat_us)) {
    latch_safety_stop(control);
    return;
  }
  control->last_heartbeat_us = now_us;
}

void NucleoControlTick_OnTimer(NucleoControlTick *control, uint64_t now_us,
                               uint8_t safety_permissive)
{
  uint64_t tick_gap_us;
  if ((control == NULL) || (control->armed == 0U)) return;
  if ((safety_permissive == 0U) || (now_us < control->last_tick_us) ||
      (now_us < control->last_heartbeat_us)) {
    latch_safety_stop(control);
    return;
  }
  tick_gap_us = now_us - control->last_tick_us;
  if ((tick_gap_us > NUCLEO_CONTROL_MAX_TICK_GAP_US) ||
      ((now_us - control->last_heartbeat_us) >
       NUCLEO_CONTROL_WATCHDOG_US)) {
    /* Missing a bounded control deadline is unsafe for a planned trajectory. */
    latch_safety_stop(control);
    return;
  }
  control->last_tick_us = now_us;
  control->tick_count++;
  control->hooks.control_tick(control->hooks.context, now_us);
}

void NucleoControlTick_Disarm(NucleoControlTick *control)
{
  if (control == NULL) return;
  control->armed = 0U;
  if (control->hooks.safety_stop != NULL) {
    control->hooks.safety_stop(control->hooks.context);
  }
}
