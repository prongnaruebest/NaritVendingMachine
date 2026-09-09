/* NARIT HMI shared state — browser view state only; Controller remains machine authority. */
(() => {
  "use strict";

  const AXES = Object.freeze(["x", "y", "z"]);

  function createInitialState() {
    return {
      online: false,
      pending: false,
      motorTestJog: { active: false, token: 0, button: null },
      manualJog: { active: false, token: 0, button: null, isHolding: false, holdTimer: null },
      payload: null,
      config: null,
      slots: {},
      mqtt: null,
      mqttPollPending: false,
      mqttControlPending: false,
      events: [],
      lastError: "",
      validation: { valid: false, stage: "idle", message: "Target not validated.", plan: null, axes: {}, armToken: null },
      feedOverridePct: 100,
      selectedJogStep: 1.0,
      selectedJogSpeed: 5.0,
      axisSpeeds: { x: 5.0, y: 5.0, z: 5.0 },
      keyboardJogEnabled: false,
      selectedSlotCode: "",
      slotSequenceMode: false,
      visualTargetSlot: "",
      slotEditorDirty: false,
      visualEditorDirty: false,
      ioFilter: "all",
      ioSearch: "",
      visualEditMode: false,
      visualPreview: null,
      visualOriginalSlot: null,
      visualGotoPending: false,
      axisVelocity: Object.fromEntries(AXES.map((axis) => [axis, {
        positionMm: null,
        sampledAt: 0,
        mmS: 0,
        direction: "IDLE",
      }])),
      lastStatusAt: 0,
      configDirty: false,
      configSaving: false,
      slotDrafts: {},
      dashboardSelectedSlot: "1",
      dashboardOperationStartedAt: null,
      dashboardTrackedCommand: "",
      dashboardWasBusy: false,
      silentErrorUntil: 0,
      logFilter: "all",
      eventFilters: { search: "", severity: "all", category: "all", outcome: "all" },
      selectedEventId: "",
      currentView: "motion",
      currentSetupTab: "motor",
      demoArmToken: "",
      demoHistory: [],
      demoHistoryPending: false,
      demoHistoryFetchedAt: 0,
    };
  }

  const state = createInitialState();
  const selectors = Object.freeze({
    status: () => state.payload?.status || {},
    operation: () => state.payload?.operation || {},
    axis: (axis) => state.payload?.status?.[axis] || {},
    allAxesHomed: () => AXES.every((axis) => Boolean(state.payload?.status?.[axis]?.is_homed)),
    motorTest: () => state.payload?.safety?.motor_test || { armed: false, expires_in_s: 0 },
  });

  Object.defineProperty(window, "NaritMachineStore", {
    value: Object.freeze({ axes: AXES, state, selectors, createInitialState }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
