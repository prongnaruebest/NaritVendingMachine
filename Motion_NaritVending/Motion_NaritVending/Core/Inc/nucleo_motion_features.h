#ifndef NUCLEO_MOTION_FEATURES_H
#define NUCLEO_MOTION_FEATURES_H

/* One gate owns the complete v4 runtime boundary. A partial enable could
 * advertise commands without a 1 kHz executor, so mismatched overrides fail
 * at compile time. Legacy macro overrides remain accepted by host tests. */
#ifndef NUCLEO_G491_DYNAMIC_MOTION_ENABLED
#if defined(NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED)
#define NUCLEO_G491_DYNAMIC_MOTION_ENABLED NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED
#elif defined(NUCLEO_G491_PROFILE_RUNTIME_ENABLED)
#define NUCLEO_G491_DYNAMIC_MOTION_ENABLED NUCLEO_G491_PROFILE_RUNTIME_ENABLED
#else
#define NUCLEO_G491_DYNAMIC_MOTION_ENABLED 1
#endif
#endif

#ifndef NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED
#define NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED NUCLEO_G491_DYNAMIC_MOTION_ENABLED
#endif

#ifndef NUCLEO_G491_PROFILE_RUNTIME_ENABLED
#define NUCLEO_G491_PROFILE_RUNTIME_ENABLED NUCLEO_G491_DYNAMIC_MOTION_ENABLED
#endif

#if (NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED != NUCLEO_G491_DYNAMIC_MOTION_ENABLED)
#error "Dynamic serial protocol and G491 motion runtime must share one gate"
#endif

#if (NUCLEO_G491_PROFILE_RUNTIME_ENABLED != NUCLEO_G491_DYNAMIC_MOTION_ENABLED)
#error "G491 control timer and dynamic motion runtime must share one gate"
#endif

#endif /* NUCLEO_MOTION_FEATURES_H */
