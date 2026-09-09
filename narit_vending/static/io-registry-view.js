/* Pure view selectors for the Controller-owned I/O registry. */
(() => {
  "use strict";

  const KIND_LABELS = Object.freeze({
    safety_interlock: "Safety Interlock",
    drive_alarm: "Drive Alarm Feedback",
    position_feedback: "Position Feedback",
    position_switch: "Position / Limit Switch",
    process_sensor: "Process Sensor",
    command_output: "Controller Output",
  });

  function channels(registry, filters = {}) {
    const source = Array.isArray(registry) ? registry : [];
    return source.filter((item) => Object.entries(filters).every(([key, value]) => item?.[key] === value));
  }

  function first(registry, filters = {}) {
    return channels(registry, filters)[0] || null;
  }

  function definition(channel) {
    const category = channel.safety_class === "safety" ? "safety"
      : channel.kind === "position_switch" ? "limits"
      : channel.kind === "process_sensor" ? "sensors"
      : channel.kind === "drive_alarm" ? "drive-alarms"
      : channel.direction === "output" ? "outputs" : "inputs";
    return Object.freeze({
      ...channel,
      role: KIND_LABELS[channel.kind] || "Digital I/O",
      category,
      terminal: channel.address || "--",
      coil: channel.protocol_address || channel.address || "--",
      desc: `${channel.source === "iriv_modbus" ? "IRIV Modbus" : "PiControl local"} · ${channel.stale ? "stale data" : "live Controller data"}`,
      highlight: channel.kind === "position_switch" && String(channel.key).endsWith("_home"),
      isSafety: channel.safety_class === "safety",
      isAlarm: channel.kind === "drive_alarm" || channel.key === "alarm",
    });
  }

  function definitions(registry, filters = {}) {
    return channels(registry, filters).map(definition);
  }

  Object.defineProperty(window, "NaritIORegistryView", {
    value: Object.freeze({ channels, first, definition, definitions }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
