/* =============================================================
   NARIT VENDING MACHINE — Industrial HMI JavaScript
   All existing backend API endpoints preserved exactly.
   State-machine-first design: one authoritative state object,
   all UI derived from it.
   ============================================================= */
(() => {
  "use strict";

  /* ── CONSTANTS ──────────────────────────────────────────────── */
  const AXES = ["x", "y", "z"];
  const POLL_INTERVAL_MS = 1000;

  /* ── CENTRALIZED MACHINE STATE ──────────────────────────────── */
  if (!window.NaritMachineStore) throw new Error("HMI machine store failed to load");
  const MS = window.NaritMachineStore.state;
  const machineSelectors = window.NaritMachineStore.selectors;

  /* ── DOM HELPERS ────────────────────────────────────────────── */
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  function el(id) {
    const node = document.getElementById(id);
    if (!node) console.warn(`[HMI] Missing element #${id}`);
    return node;
  }

  function setText(id, value) {
    const node = el(id);
    if (node) node.textContent = String(value ?? "");
  }

  function setAttr(id, attr, value) {
    const node = el(id);
    if (node) node.setAttribute(attr, value);
  }

  function setClass(id, cls) {
    const node = el(id);
    if (node) node.className = cls;
  }

  /* ── SAFETY: escape to prevent XSS in dynamic HTML ─────────── */
  function esc(value) {
    return String(value ?? "").replace(/[&<>'"\u0000-\u001f]/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;",
      "'": "&#39;", '"': "&quot;",
    }[c] ?? ""));
  }

  /* ── NUMBER FORMATTING ──────────────────────────────────────── */
  function fmt(value, digits = 3) {
    const n = Number(value);
    return isNaN(n) ? "---" : n.toFixed(digits);
  }
  function fmtPos(value) { return fmt(value, 3); }
  function fmtSpd(value) { return fmt(value, 1); }
  function fmtSteps(value) { return Number(value || 0).toLocaleString(); }
  function fmtDelta(value) {
    const n = Number(value);
    if (isNaN(n)) return { text: "---", cls: "zero" };
    if (Math.abs(n) < 0.001) return { text: "+0.000", cls: "zero" };
    return { text: (n >= 0 ? "+" : "") + n.toFixed(3), cls: n >= 0 ? "pos" : "neg" };
  }
  function fmtTime(value) {
    const n = Number(value);
    return isNaN(n) ? "---" : n.toFixed(2);
  }

  function fmtDuration(milliseconds) {
    if (!Number.isFinite(milliseconds) || milliseconds < 0) return "--";
    const totalSeconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function fmtTimestamp(value) {
    if (!value) return "--";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }

  /* ── STATE ACCESSORS ────────────────────────────────────────── */
  function getStatus() { return machineSelectors.status(); }
  function getOperation() { return machineSelectors.operation(); }
  function getAxis(axis) { return machineSelectors.axis(axis); }

  function updateAxisVelocity(payload) {
    const sampledAt = Date.now();
    AXES.forEach((axis) => {
      const sample = MS.axisVelocity[axis];
      const positionMm = Number(payload?.status?.[axis]?.position_mm);
      if (!Number.isFinite(positionMm)) {
        sample.mmS = 0;
        sample.direction = "UNKNOWN";
        sample.positionMm = null;
        sample.sampledAt = sampledAt;
        return;
      }
      const elapsedS = sample.sampledAt ? (sampledAt - sample.sampledAt) / 1000 : 0;
      const deltaMm = sample.positionMm == null ? 0 : positionMm - sample.positionMm;
      if (elapsedS >= 0.1 && elapsedS <= 5 && Math.abs(deltaMm) >= 0.0005) {
        sample.mmS = Math.abs(deltaMm / elapsedS);
        sample.direction = deltaMm > 0 ? "+" : "−";
      } else {
        sample.mmS = 0;
        sample.direction = "IDLE";
      }
      sample.positionMm = positionMm;
      sample.sampledAt = sampledAt;
    });
  }

  function realtimeSpeedText(axis) {
    const velocity = MS.axisVelocity[axis];
    if (!velocity || velocity.direction === "UNKNOWN") return "UNKNOWN";
    const direction = velocity.direction === "IDLE" ? "IDLE" : velocity.direction;
    return `${velocity.mmS.toFixed(3)} mm/s · ${direction}`;
  }

  function allAxesHomed() {
    return machineSelectors.allAxesHomed();
  }

  function motorTestState() {
    return machineSelectors.motorTest();
  }

  function activeAlarmCount() {
    return alarmChannels().filter((channel) => channel.active && channel.level === "fault").length;
  }

  function alarmChannels() {
    const status = getStatus();
    const backendChannels = Array.isArray(MS.payload?.alarm_channels) ? MS.payload.alarm_channels : [];
    const channels = [
      { code: "CTRL", label: "Controller Communication", active: !MS.online, level: "fault", detail: MS.online ? "API polling online" : "No response from Raspberry Pi controller" },
      { code: "ESTOP", label: "Emergency Stop", active: Boolean(status.estop), level: "fault", detail: status.estop ? "Physical E-Stop input is active" : "Safety input clear" },
      { code: "STOP", label: "Software Stop Latch", active: Boolean(MS.payload?.safety?.stop_requested), level: "fault", detail: MS.payload?.safety?.stop_requested ? "Reset alarms before motion" : "Software stop clear" },
    ];
    AXES.forEach((axis) => {
      const data = getAxis(axis);
      channels.push(
        { code: `${axis.toUpperCase()}-MIN`, label: `${axis.toUpperCase()} Minimum Limit`, active: Boolean(data.head_limit), level: "fault", detail: data.head_limit ? "Minimum travel sensor active" : "Sensor clear" },
        { code: `${axis.toUpperCase()}-MAX`, label: `${axis.toUpperCase()} Maximum Limit`, active: Boolean(data.tail_limit), level: "fault", detail: data.tail_limit ? "Maximum travel sensor active" : "Sensor clear" },
        { code: `${axis.toUpperCase()}-HOME`, label: `${axis.toUpperCase()} Homing Reference`, active: !data.is_homed, level: "warn", detail: data.is_homed ? "Axis referenced" : "Axis requires homing" },
      );
    });
    channels.push({
      code: "CTRL-ERR",
      label: "Controller Fault",
      active: Boolean(MS.payload?.last_error),
      level: "fault",
      detail: MS.payload?.last_error || "No controller fault message",
    });
    backendChannels.forEach((channel) => {
      if (!channels.some((existing) => existing.code === channel.code)) channels.push(channel);
    });
    return channels;
  }

  /* ── DERIVED MOTION PERMISSION ──────────────────────────────── */
  function motionInhibitReason(requireHome = false) {
    const status = getStatus();
    if (MS.payload?.io?.communication_ok === false) return "MOTION LOCKED - IRIV IO communication lost";
    const ioFault = (MS.payload?.alarm_channels || []).find((channel) => channel.active && ["DOOR", "DRV-X", "DRV-Y", "DRV-Z"].includes(channel.code));
    if (ioFault) return `MOTION LOCKED - ${ioFault.label}`;
    if (!MS.online)                           return "Controller offline — reconnecting...";
    if (status.estop)                         return "MOTION LOCKED — Emergency stop active";
    if (MS.payload?.safety?.stop_requested)   return "MOTION LOCKED — reset alarms before continuing";
    if (MS.payload?.safety?.motion_enabled === false) {
      return "MOTION LOCKED — open System Control & Health and press ENABLE MOTION";
    }
    if (MS.payload?.safety?.configuration_restart_required || MS.config?.restart_required) {
      return "MOTION LOCKED — apply configuration and restart controller";
    }
    if (motorTestState().armed)              return "MOTION LOCKED — Motor Test Mode is armed";
    if (MS.pending || MS.payload?.busy)       return "Another command is executing";
    if (requireHome && !allAxesHomed()) {
      const first = AXES.find((a) => !getAxis(a).is_homed);
      return `${first?.toUpperCase() ?? "Axis"} not homed — home all axes first`;
    }
    return "";
  }

  function canJogAxis(axis) {
    if (motionInhibitReason(false) !== "") return false;
    if ($("#jog-allow-unhomed")?.checked) return true;
    return Boolean(getAxis(axis).is_homed);
  }
  function motionInhibitReasonForAxes(axes) {
    const generalReason = motionInhibitReason(false);
    if (generalReason) return generalReason;
    const first = axes.find((axis) => !getAxis(axis).is_homed);
    return first ? `${first.toUpperCase()} not homed — home that axis first` : "";
  }
  function plannedMoveAxes() {
    return Object.keys(MS.validation.plan?.axes || {}).filter((axis) => AXES.includes(axis));
  }
  function canExecuteMove() {
    return MS.validation.valid
      && MS.validation.stage === "armed"
      && motionInhibitReasonForAxes(plannedMoveAxes()) === "";
  }
  function canHomeAxis() { return motionInhibitReason(false) === ""; }
  /* ── SLOT STATUS ────────────────────────────────────────────── */
  function slotStatus(slot) {
    const hasProduct = Boolean(slot.product_name);
    const hasCoords = [slot.x_mm, slot.y_mm, slot.z_mm].some((v) => Number(v) !== 0);
    if (!hasProduct && !hasCoords) return "empty";
    return "ready";
  }

  function slotManagerStatus(slot) {
    const values = AXES.map((axis) => Number(slot?.[`${axis}_mm`]));
    const hasProduct = Boolean(slot?.product_name);
    const hasPosition = values.some((value) => value !== 0);
    if (!hasProduct && !hasPosition) return "empty";
    if (!values.every(Number.isFinite) || !hasPosition) return "not-configured";
    const limitsLoaded = AXES.every((axis) => Number.isFinite(Number(MS.config?.axes?.[axis]?.max_travel_mm)));
    if (values.some((value) => value < 0) || (limitsLoaded && !visualSlotIsValid(slot))) return "invalid";
    if (activeAlarmCount() > 0) return "alarm";
    return "ready";
  }

  function slotAtCurrentPosition(slot) {
    return allAxesHomed() && AXES.every((axis) => {
      const target = Number(slot?.[`${axis}_mm`]);
      const actual = Number(getAxis(axis).position_mm);
      return Number.isFinite(target) && Number.isFinite(actual) && Math.abs(target - actual) <= 0.05;
    });
  }

  function selectSlotFromManager(code) {
    MS.selectedSlotCode = code;
    MS.visualTargetSlot = code;
    MS.slotEditorDirty = false;
    const picker = el("selected-slot-code");
    if (picker) picker.value = code;
    renderSlotTable();
    loadSelectedSlotEditor(true);
    updateButtonStates();
  }

  /* ── API LAYER ──────────────────────────────────────────────── */
  async function apiCall(path, method = "GET", body, timeoutMs = 8000) {
    if (!window.NaritApiClient) throw new Error("HMI API client failed to load");
    return window.NaritApiClient.request(path, method, body, timeoutMs);
  }

  /* ── ERROR HUMANIZER ────────────────────────────────────────── */
  function humanizeError(msg) {
    if (!msg) return "Unknown error";
    if (msg.includes("outside") || msg.includes("exceeds"))
      return `MOVE REJECTED — ${msg}`;
    if (msg.includes("not homed"))
      return `MOVE REJECTED — ${msg}`;
    if (msg.includes("Emergency") || msg.includes("emergency"))
      return `MOTION LOCKED — ${msg}`;
    if (msg.includes("busy"))
      return `BUSY — ${msg}`;
    return msg;
  }

  /* ── EVENT LOG ──────────────────────────────────────────────── */
  function log(message, level = "info", subsystem = "SYSTEM") {
    MS.events.unshift({ id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, at: new Date(), message: sanitizeEventText(message), level, subsystem });
    MS.events = MS.events.slice(0, 200);
    renderEventLog();
  }

  function sanitizeEventText(value) {
    return String(value ?? "")
      .replace(/((?:password|passwd|token|secret|authorization)\s*[=:]\s*)[^\s,;]+/gi, "$1***REDACTED***")
      .replace(/\bBearer\s+[A-Za-z0-9._~+\/-]+=*/gi, "Bearer ***REDACTED***");
  }

  function eventSeverity(event) {
    const level = String(event.level || "").toLowerCase();
    const message = String(event.message || "").toLowerCase();
    if (["error", "fault", "critical"].includes(level) || /failed|rejected|blocked|lost|alarm|e-stop/.test(message)) return "fault";
    if (["warn", "warning"].includes(level) || /not homed|warning|requires/.test(message)) return "warn";
    return "info";
  }

  function eventCategory(event) {
    const source = `${event.subsystem || ""} ${event.message || ""}`.toUpperCase();
    if (/MQTT/.test(source)) return "MQTT";
    if (/HOME/.test(source)) return "HOMING";
    if (/SLOT/.test(source)) return "SLOT";
    if (/CONFIG/.test(source)) return "CONFIG";
    if (/ESTOP|E-STOP|INTERLOCK|ALARM|LIMIT|SAFETY/.test(source)) return "SAFETY";
    if (/MOTION|MOVE|JOG|GOTO|DISPENSE|TARGET|COMMAND/.test(source)) return "MOTION";
    return "SYSTEM";
  }

  function eventOutcome(event) {
    const message = String(event.message || "").toLowerCase();
    if (/failed|rejected|blocked|lost|error/.test(message)) return "FAILED";
    if (/requested|connecting|armed/.test(message)) return "STARTED";
    return "SUCCESS";
  }

  function eventAt(event) { return event.at instanceof Date ? event.at : new Date(event.at); }
  function eventTime(event) {
    const at = eventAt(event);
    return Number.isNaN(at.getTime()) ? "--" : at.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  }
  function eventPriority(event) { return ({ fault: 0, warn: 1, info: 2 })[eventSeverity(event)] ?? 2; }
  function eventMatches(event) {
    const filter = MS.eventFilters;
    const searchable = `${event.message} ${event.subsystem} ${eventCategory(event)} ${eventOutcome(event)}`.toLowerCase();
    return (!filter.search || searchable.includes(filter.search.toLowerCase()))
      && (filter.severity === "all" || eventSeverity(event) === filter.severity)
      && (filter.category === "all" || eventCategory(event) === filter.category)
      && (filter.outcome === "all" || eventOutcome(event) === filter.outcome);
  }
  function sortedEvents() {
    return MS.events.filter(eventMatches).slice().sort((a, b) => eventPriority(a) - eventPriority(b) || eventAt(b) - eventAt(a));
  }

  function exportFilteredEventsCsv() {
    const quote = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const rows = [["timestamp_ict", "severity", "category", "outcome", "message"]];
    sortedEvents().forEach((event) => rows.push([
      eventTime(event), eventSeverity(event).toUpperCase(), eventCategory(event),
      eventOutcome(event), sanitizeEventText(event.message),
    ]));
    const blob = new Blob(["\ufeff" + rows.map((row) => row.map(quote).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `narit-events-${new Date().toISOString().replace(/[:.]/g, "-")}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function renderEventDetail(event) {
    const detail = el("event-detail-content");
    const state = el("event-detail-state");
    if (!detail || !state) return;
    if (!event) {
      state.textContent = "NONE";
      state.className = "page-status-chip";
      detail.innerHTML = "<p>Select an event to inspect its sanitized details. This page never sends a machine command.</p>";
      return;
    }
    const severity = eventSeverity(event);
    const status = getStatus();
    const axisSnapshot = AXES.map((axis) => `${axis.toUpperCase()} ${fmtPos(getAxis(axis).position_mm)} mm`).join(" · ");
    const active = alarmChannels().filter((channel) => channel.active).map((channel) => channel.code).join(", ") || "None";
    const message = sanitizeEventText(event.message);
    const slot = message.match(/slot\s*([A-Za-z0-9_-]+)/i)?.[1] || "--";
    const axis = message.match(/\b([XYZ])\b/i)?.[1]?.toUpperCase() || "--";
    state.textContent = severity.toUpperCase();
    state.className = `page-status-chip ${severity === "fault" ? "fault" : (severity === "warn" ? "warn" : "ok")}`;
    detail.innerHTML = `<dl>
      <div><dt>Event ID</dt><dd>${esc(event.id || "local event")}</dd></div><div><dt>Timestamp (ICT)</dt><dd>${esc(eventTime(event))}</dd></div>
      <div><dt>Severity / Outcome</dt><dd>${esc(severity.toUpperCase())} / ${esc(eventOutcome(event))}</dd></div><div><dt>Category</dt><dd>${esc(eventCategory(event))}</dd></div>
      <div><dt>Message</dt><dd>${esc(message)}</dd></div><div><dt>Slot / Axis</dt><dd>${esc(slot)} / ${esc(axis)}</dd></div>
      <div><dt>Live Machine State</dt><dd>${esc(MS.payload?.machine_state || "UNKNOWN")}</dd></div><div><dt>Active Command</dt><dd>${esc(MS.payload?.active_command || "None")}</dd></div>
      <div><dt>Homing (live)</dt><dd>${esc(AXES.map((axisName) => `${axisName.toUpperCase()}:${getAxis(axisName).is_homed ? "YES" : "NO"}`).join(" "))}</dd></div>
      <div><dt>Safety / Active Alarms (live)</dt><dd>${esc(status.estop ? "E-STOP ACTIVE" : `Clear · ${active}`)}</dd></div>
      <div><dt>Current XYZ (live)</dt><dd>${esc(axisSnapshot)}</dd></div>
    </dl><p class="event-detail-note">Event history stores a sanitized message and local timestamp. The machine values above are the current live snapshot, not a reconstructed historical state.</p>`;
  }

  function renderEventLog() {
    const filter = MS.logFilter;
    const entries = filter === "all"
      ? MS.events
      : MS.events.filter((e) => e.level === filter || (filter === "error" && e.level === "error"));

    const markup = entries.slice(0, 80).map((e) => `
      <li class="evt-item ${esc(e.level)}" role="listitem">
        <span class="evt-time">${e.at.toLocaleTimeString()}</span>
        <span class="evt-level">${esc(e.subsystem)}</span>
        <span class="evt-msg">${esc(e.message)}</span>
      </li>
    `).join("");
    const compactLog = document.getElementById("event-log");
    const pageLog = document.getElementById("event-log-page");
    if (compactLog) compactLog.innerHTML = markup;
    if (pageLog) {
      const entries = sortedEvents();
      const totals = MS.events.reduce((counts, event) => { counts[eventSeverity(event)] += 1; return counts; }, { fault: 0, warn: 0, info: 0 });
      setText("event-total-count", String(MS.events.length));
      setText("event-fault-count", String(totals.fault)); setText("event-warn-count", String(totals.warn)); setText("event-info-count", String(totals.info));
      setText("event-filtered-count", `${entries.length} shown`);
      setText("event-last-update", `Last update: ${MS.events[0] ? eventTime(MS.events[0]) : "--"}`);
      setText("event-controller-state", MS.online ? "ONLINE" : "OFFLINE");
      const activeAlarms = alarmChannels().filter((channel) => channel.active).sort((a, b) => (a.level === "fault" ? 0 : 1) - (b.level === "fault" ? 0 : 1));
      const activeList = el("event-active-alarm-list");
      const activeCount = el("event-active-alarm-count");
      if (activeCount) { activeCount.textContent = activeAlarms.length ? `${activeAlarms.length} ACTIVE` : "0 CLEAR"; activeCount.className = `page-status-chip ${activeAlarms.some((channel) => channel.level === "fault") ? "fault" : (activeAlarms.length ? "warn" : "ok")}`; }
      if (activeList) activeList.innerHTML = activeAlarms.length ? activeAlarms.map((channel) => `<div class="event-active-alarm ${channel.level}"><b>${channel.level === "fault" ? "! FAULT" : "! WARNING"}</b><span>${esc(channel.code)} · ${esc(channel.label)}</span><small>${esc(channel.detail)}</small></div>`).join("") : "<div class=\"event-active-clear\">✓ NO ACTIVE ALARMS — event history below is read-only.</div>";
      pageLog.innerHTML = entries.map((event) => `<li class="event-history-item ${eventSeverity(event)}" data-event-id="${esc(event.id)}"><div><b>${eventSeverity(event) === "fault" ? "! FAULT" : (eventSeverity(event) === "warn" ? "! WARNING" : "• INFO")}</b><time>${esc(eventTime(event))} ICT</time></div><span class="event-category">${esc(eventCategory(event))}</span><p>${esc(sanitizeEventText(event.message))}</p><span class="event-outcome">${esc(eventOutcome(event))}</span><button type="button" class="event-detail-button" data-event-detail="${esc(event.id)}">DETAIL</button></li>`).join("") || "<li class=\"event-history-empty\">NO EVENTS MATCH THE CURRENT FILTERS</li>";
      renderEventDetail(MS.events.find((event) => event.id === MS.selectedEventId));
    }
  }

  /* ── TOAST ──────────────────────────────────────────────────── */
  function toast(message, type = "") {
    const node = el("toast");
    node.textContent = message;
    node.className = `toast show${type ? " " + type : ""}`;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { node.className = "toast"; }, 3200);
  }

  /* ── COMMAND EXECUTOR ───────────────────────────────────────── */
  async function command(label, path, body, opts = {}) {
    const reason = opts.requiredAxes
      ? motionInhibitReasonForAxes(opts.requiredAxes)
      : motionInhibitReason(opts.requireHome ?? false);
    if (!opts.noCheck && reason) {
      if (!opts.silent) toast(reason, "error");
      log(`${label} blocked: ${reason}`, "error", "INTERLOCK");
      return null;
    }
    MS.pending = !opts.isStop;
    if (opts.silent) MS.silentErrorUntil = Date.now() + 5000;
    updateAllUI();
    log(`${label} requested`, "info", "COMMAND");

    try {
      const data = await apiCall(path, "POST", body, opts.timeoutMs || 8000);
      if (!opts.silent) toast(`${label} — accepted`, "ok");
      log(`${label} accepted`, "info", "COMMAND");
      if (data.plan) renderPlan(data.plan);
      await refresh();
      return data;
    } catch (err) {
      const msg = humanizeError(err.message);
      if (!opts.silent) toast(msg, "error");
      log(`${label} failed: ${msg}`, "error", "COMMAND");
      return null;
    } finally {
      MS.pending = false;
      updateAllUI();
    }
  }

  function motionAllowed(requireHome = false) {
    return motionInhibitReason(requireHome) === "";
  }

  /* ── BUILD PAYLOADS ─────────────────────────────────────────── */
  function buildMovePayload() {
    const body = {};
    const participatingAxes = [];
    AXES.forEach((a) => {
      const v = el(`move-${a}`)?.value;
      if (v !== "" && v !== null && v !== undefined) {
        body[`${a}_mm`] = Number(v);
        participatingAxes.push(a);
      }
    });
    body.speed_mm_s = effectiveMotionSpeed(participatingAxes);
    return body;
  }

  function slotSequenceEnabled() {
    return Boolean(MS.slotSequenceMode);
  }

  function slotMotionEndpoint(code) {
    return slotSequenceEnabled() ? `/api/slots/${encodeURIComponent(code)}/sequence` : `/api/slots/${encodeURIComponent(code)}/goto`;
  }

  function slotMotionLabel(code) {
    return slotSequenceEnabled() ? `Run slot ${code} sequence` : `Go to slot ${code}`;
  }

  function updateSlotSequenceMode() {
    const enabled = slotSequenceEnabled();
    const toggle = el("slot-sequence-toggle");
    if (toggle) toggle.checked = enabled;
    setText("slot-sequence-state", enabled ? "ON" : "OFF");
    setText("slot-sequence-description", enabled
      ? "ON — X → Y → Z target, 3 s hold, then Home Z → Y → X."
      : "OFF — GO TO uses the standard Controller motion.");
    const summary = el("slot-sequence-summary");
    if (summary) summary.classList.toggle("active", enabled);
  }

  function fillManualTarget(coordinates, message) {
    AXES.forEach((axis) => {
      const value = Number(coordinates[`${axis}_mm`]);
      el(`move-${axis}`).value = Number.isFinite(value) ? value.toFixed(3) : "";
    });
    invalidateMotionWorkflow(`${message} — edit the target if required, then press VALIDATE.`);
    updateFeedOverride();
    toast(`${message}. No movement has started.`, "ok");
  }

  function loadCurrentManualTarget() {
    fillManualTarget(
      Object.fromEntries(AXES.map((axis) => [`${axis}_mm`, getAxis(axis).position_mm])),
      "Current XYZ loaded"
    );
  }

  function loadSelectedSlotManualTarget() {
    const code = selectedSlotCode();
    const slot = MS.slots[code] || {};
    if (slotStatus(slot) !== "ready") {
      toast(`Slot ${code || "--"} has no saved position.`, "error");
      return;
    }
    fillManualTarget(slot, `Slot ${code} loaded`);
  }

  function buildJogPayload(axis, direction, continuous = false) {
    const spd = effectiveMotionSpeed([axis]);
    const current = Number(getAxis(axis).position_mm);
    const maximum = Number(MS.config?.axes?.[axis]?.max_travel_mm);
    // Hold-to-run uses one uninterrupted timer pulse train toward the software
    // boundary. Releasing the control sends a priority controlled-stop.
    const remaining = Number(direction) > 0 ? maximum - current : current;
    const distance = continuous ? Math.max(remaining, 0.001) : MS.selectedJogStep;
    const body = {
      axis,
      distance_mm: distance * Number(direction),
    };
    if (continuous) body.continuous = true;
    if (spd > 0) body.speed_mm_s = spd;
    if (!continuous) {
      const jogTime = el("jog-time")?.value;
      if (jogTime) body.time_s = Number(jogTime);
    }
    return body;
  }

  function targetSpeedPayload(axes = AXES) {
    return { speed_mm_s: effectiveMotionSpeed(axes) };
  }

  /* ── VALIDATE MOVE ──────────────────────────────────────────── */
  async function validateMove(showToast = true) {
    const payload = buildMovePayload();
    if (!Object.keys(payload).some((k) => k.endsWith("_mm"))) {
      setValidation(false, "invalid", "TARGET INVALID — enter at least one axis coordinate.");
      if (showToast) toast("Enter at least one target coordinate.", "error");
      return null;
    }
    try {
      const data = await apiCall("/api/motion/validate", "POST", payload);
      const plan = data.plan;
      setValidation(true, "validated", "TARGET VALID — generate preview before arming.", plan, data.axes || {});
      renderPreview(plan);
      renderPlan(plan);
      if (showToast) toast("Target validated — continue to PREVIEW.", "ok");
      log("Target validation passed", "info", "MOTION");
      return plan;
    } catch (err) {
      const msg = `TARGET INVALID — ${humanizeError(err.message)}`;
      setValidation(false, "invalid", msg);
      renderPreview(null);
      if (showToast) toast(msg, "error");
      log(msg, "error", "MOTION");
      return null;
    }
  }

  async function previewMove(showToast = true) {
    if (MS.validation.stage !== "validated") {
      const validated = await validateMove(showToast);
      if (!validated) return null;
    }
    try {
      const data = await apiCall("/api/motion/preview", "POST", buildMovePayload());
      setValidation(true, "previewed", "PREVIEW READY — verify trajectory and ARM MOVE.", data.plan, data.axes || {});
      renderPreview(data.plan);
      renderPlan(data.plan);
      if (showToast) toast("Trajectory preview ready.", "ok");
      return data.plan;
    } catch (err) {
      setValidation(false, "invalid", `PREVIEW FAILED — ${humanizeError(err.message)}`);
      if (showToast) toast(humanizeError(err.message), "error");
      return null;
    }
  }

  async function armMove(showToast = true) {
    if (MS.validation.stage !== "previewed") {
      const preview = await previewMove(showToast);
      if (!preview) return null;
    }
    try {
      const data = await apiCall("/api/motion/arm", "POST", buildMovePayload());
      setValidation(true, "armed", `MOVE ARMED — token expires in ${data.expires_in_s || 20} seconds.`, data.plan, data.axes || {}, data.arm_token);
      if (showToast) toast("Move armed — press EXECUTE when the travel area is clear.", "ok");
      log("Move armed after backend safety recheck", "info", "MOTION");
      return data;
    } catch (err) {
      setValidation(false, "invalid", `ARM REJECTED — ${humanizeError(err.message)}`);
      if (showToast) toast(humanizeError(err.message), "error");
      return null;
    }
  }

  async function executeArmedMotion(label = "Execute move") {
    if (MS.validation.stage !== "armed" || !MS.validation.armToken) {
      toast("Move is not armed — complete VALIDATE, PREVIEW and ARM first.", "error");
      return null;
    }
    const requestId = globalThis.crypto?.randomUUID?.() || `cmd-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const plannedDuration = Number(MS.validation.plan?.duration_s || MS.validation.plan?.estimated_duration_s || 0);
    const result = await command(label, "/api/motion/execute", {
      arm_token: MS.validation.armToken,
      request_id: requestId,
    }, { requiredAxes: plannedMoveAxes(), timeoutMs: Math.max(45000, (plannedDuration + 30) * 1000) });
    if (result) invalidateMotionWorkflow("Move completed — target must be validated again.");
    return result;
  }

  function invalidateMotionWorkflow(message = "Target changed — validate again.") {
    setValidation(false, "idle", message);
    renderPreview(null);
    renderPlan(null);
  }

  function setValidation(valid, stage, message, plan = null, axes = {}, armToken = null) {
    MS.validation = { valid, stage, message, plan, axes, armToken };
    const box = el("validation-box");
    if (box) {
      box.className = `validation-message ${valid ? "valid" : stage === "invalid" ? "invalid" : ""}`;
      box.textContent = message;
    }
    const axesNode = el("motion-validation-axes");
    if (axesNode) {
      const entries = Object.entries(axes);
      axesNode.innerHTML = entries.length
        ? entries.map(([axis, result]) => `<span><b>${esc(axis.toUpperCase())}</b> HOME ${result.homed ? "PASS" : "FAIL"} · LIMIT ${esc(result.soft_limit || "--")} · PULSE ${fmt(result.pulse_frequency_hz, 0)} Hz · DRIVE ${esc(result.drive_feedback || "NO DATA")}</span>`).join("")
        : "Per-axis safety validation pending.";
    }
    updateExecuteButton();
  }

  function updateExecuteButton() {
    const btn = el("absolute-move");
    if (!btn) return;
    btn.disabled = !canExecuteMove();
    btn.textContent = MS.payload?.busy ? "MOVING..." : "4 EXECUTE";
    btn.className = MS.payload?.busy ? "btn-execute btn-executing" : "btn-execute";
    const previewButton = el("plan-move");
    if (previewButton) previewButton.disabled = MS.validation.stage !== "validated";
    const armButton = el("arm-move");
    if (armButton) armButton.disabled = MS.validation.stage !== "previewed" || Boolean(MS.payload?.busy);
  }

  /* ── RENDER: MOVE PREVIEW ───────────────────────────────────── */
  function renderPreview(plan) {
    const cur = getStatus().current_position || {};

    // Current column
    AXES.forEach((a) => {
      setText(`prev-cur-${a}`, fmtPos(cur[`${a}_mm`]));
    });

    if (!plan) {
      AXES.forEach((a) => {
        setText(`prev-tgt-${a}`, "---");
        const d = el(`prev-delta-${a}`);
        if (d) { d.textContent = "---"; d.className = "pd zero"; }
      });
      setText("prev-dist", "--- mm");
      setText("prev-time", "--- s");
      setText("prev-master", "---");
      return;
    }

    AXES.forEach((a) => {
      const ap = plan.axes?.[a];
      if (ap) {
        setText(`prev-tgt-${a}`, fmtPos(ap.target_mm));
        const d = fmtDelta(ap.distance_mm);
        const node = el(`prev-delta-${a}`);
        if (node) { node.textContent = d.text; node.className = `pd ${d.cls}`; }
      } else {
        setText(`prev-tgt-${a}`, fmtPos(cur[`${a}_mm`]));
        const node = el(`prev-delta-${a}`);
        if (node) { node.textContent = "+0.000"; node.className = "pd zero"; }
      }
    });

    setText("prev-dist", `${fmtPos(plan.total_distance_mm)} mm`);
    setText("prev-time", `${fmtTime(plan.duration_s)} s`);
    setText("prev-master", plan.master_axis ? `${String(plan.master_axis).toUpperCase()} AXIS` : "---");
  }

  /* ── RENDER: PLAN READOUT ───────────────────────────────────── */
  function renderPlan(plan) {
    const node = el("move-plan");
    if (!node) return;
    if (!plan) { node.textContent = "Preview not generated."; return; }
    const mode = String(plan.mode || "speed").toUpperCase();
    const lines = Object.values(plan.axes || {}).map((item) =>
      `${item.axis.toUpperCase()}: ${fmtPos(item.distance_mm)} mm · ${fmtSteps(item.steps)} pulses · ${fmt(item.pulse_hz, 0)} Hz · ${fmtSpd(item.speed_mm_s)} mm/s`
    ).join("\n");
    node.innerHTML = `<strong>${esc(mode)} PLAN</strong>` +
      `<br>${esc(plan.profile || "TRAPEZOIDAL")} · Master ${esc(String(plan.master_axis || "--").toUpperCase())} · Dist ${fmtPos(plan.total_distance_mm)} mm · Time ${fmtTime(plan.duration_s)} s · Pulses ${fmtSteps(plan.master_steps)}`+
      (lines ? `<br><small style="color:var(--text-3)">${esc(lines)}</small>` : "");
  }

  /* ── RENDER: AXIS CARDS ─────────────────────────────────────── */
  function renderAxisCards() {
    const axisCfg = MS.config?.axes || {};
    AXES.forEach((a) => {
      const data = getAxis(a);
      const cfg  = axisCfg[a] || {};
      const pos  = Number(data.position_mm ?? 0);
      const axisPlan = MS.validation.plan?.axes?.[a];
      const tgt  = axisPlan?.target_mm ?? pos;
      const max  = cfg.max_travel_mm || 1;
      const pct  = Math.max(0, Math.min((pos / max) * 100, 100));

      // Position display
      const posNode = el(`axis-pos-${a}`);
      if (posNode) posNode.innerHTML = `<span class="monospace">${fmtPos(pos)}</span><span class="unit">mm</span>`;

      // Travel fill
      const fill = el(`axis-fill-${a}`);
      if (fill) {
        fill.style.width = `${pct}%`;
        fill.className = `axis-travel-fill ${data.is_homed && MS.payload?.busy ? "moving" : ""}`;
      }

      // Target / steps
      setText(`axis-tgt-${a}`, fmtPos(tgt));
      setText(`axis-steps-${a}`, fmtSteps(data.position_steps));
      const delta = Number(tgt) - pos;
      setText(`axis-delta-${a}`, fmtDelta(delta).text);
      setText(`axis-direction-${a}`, Math.abs(delta) < 0.001 ? "IDLE" : delta > 0 ? "+ FORWARD" : "− REVERSE");
      const programmedSpeed = axisSpeed(a);
      const effectiveSpeed = axisPlan?.speed_mm_s;
      setText(`axis-speed-${a}`, programmedSpeed > 0 ? `${fmtSpd(programmedSpeed)} / ${effectiveSpeed == null ? "--" : fmtSpd(effectiveSpeed)}` : "-- / --");
      setText(`axis-realtime-${a}`, realtimeSpeedText(a));
      setText(`axis-drive-${a}`, axisPlan?.drive_status ? `${axisPlan.drive_status} / ${axisPlan.following_error_mm == null ? "NO DATA" : fmtPos(axisPlan.following_error_mm)}` : "NO DATA");

      // Limits
      const limitMinNode = el(`axis-lim-min-${a}`);
      const limitMaxNode = el(`axis-lim-max-${a}`);
      if (limitMinNode) {
        limitMinNode.textContent = data.head_limit ? "ACTIVE" : "CLEAR";
        limitMinNode.className = data.head_limit ? "fault" : "ok";
      }
      if (limitMaxNode) {
        limitMaxNode.textContent = data.tail_limit ? "ACTIVE" : "CLEAR";
        limitMaxNode.className = data.tail_limit ? "fault" : "ok";
      }

      // State badge
      let badgeCls = "not-homed";
      let badgeTxt = "NOT HOMED";
      if (data.estop)            { badgeCls = "fault";    badgeTxt = "FAULT"; }
      else if (data.head_limit)  { badgeCls = "limit";    badgeTxt = "LIMIT MIN"; }
      else if (data.tail_limit)  { badgeCls = "limit";    badgeTxt = "LIMIT MAX"; }
      else if (MS.payload?.busy && MS.payload?.active_command?.startsWith(`home_${a}`)) {
                                   badgeCls = "homing";   badgeTxt = "HOMING"; }
      else if (MS.payload?.busy)  { badgeCls = "moving";  badgeTxt = "MOVING"; }
      else if (data.is_homed)     { badgeCls = "homed";   badgeTxt = "HOMED / IDLE"; }

      const badge = el(`axis-badge-${a}`);
      if (badge) { badge.className = `axis-state-badge ${badgeCls}`; badge.textContent = badgeTxt; }

      // Card border
      const card = el(`axis-card-${a}`);
      if (card) {
        let cardCls = "axis-card";
        if (data.estop || data.head_limit || data.tail_limit) cardCls += " fault";
        else if (MS.payload?.busy && MS.payload?.active_command?.startsWith(`home_${a}`)) cardCls += " homing";
        else if (MS.payload?.busy) cardCls += " moving";
        card.className = cardCls;
      }
    });
  }

  /* ── RENDER: HOMING SEQUENCE ────────────────────────────────── */
  function renderHomingSequence() {
    const homeOrder = MS.config?.home_order || AXES;
    const homing    = getOperation().homing || {};
    const container = el("home-sequence-display");
    if (!container) return;
    const parallelHome = Number(MS.payload?.nucleo?.protocol || MS.config?.hardware?.nucleo?.protocol_version || 0) >= 3;
    setText("home-sequence-label", parallelHome ? "X + Y + Z" : homeOrder.map((axis) => axis.toUpperCase()).join("→"));

    container.innerHTML = homeOrder.map((axis, idx) => {
      const phase = homing[axis] || "not_homed";
      const axisData = getAxis(axis);
      const effectivePhase =
        phase === "not_homed" && axisData.is_homed ? "passed" :
        phase === "not_homed" ? "not_homed" : phase;

      const statusText =
        effectivePhase === "passed"    ? "HOMED ✓" :
        effectivePhase === "searching" ? "SEARCHING" :
        effectivePhase === "sensor_found" ? "SENSOR FOUND" :
        effectivePhase === "backoff"   ? "BACKOFF" :
        effectivePhase === "latching"  ? "LATCH APPROACH" :
        effectivePhase === "zero_set"  ? "ZERO SET" :
        effectivePhase === "positioning" ? "OFFSET MOVE" :
        effectivePhase === "completed" ? "COMPLETED" :
        effectivePhase === "failed"    ? "FAILED ✗" :
        effectivePhase === "waiting"   ? "QUEUED" :
        "NOT HOMED";

      const cfg = MS.config?.axes?.[axis] || {};
      const minActive = Boolean(axisData.head_limit);
      const detailText = `MIN ${minActive ? "ACTIVE" : "CLEAR"} · Search ${Number(cfg.homing_search_speed_mm_s || 0).toFixed(1)} · Latch ${Number(cfg.homing_latch_speed_mm_s || 0).toFixed(1)} · Home ${Number(cfg.home_position_mm || 0).toFixed(1)} mm`;
      return `
        <div class="home-seq-step ${effectivePhase}" aria-label="${axis.toUpperCase()} axis homing: ${statusText}">
          <div class="home-seq-num">${idx + 1}</div>
          <div class="home-seq-axis">${axis.toUpperCase()} Axis<small class="home-seq-detail">${esc(detailText)}</small></div>
          <div class="home-seq-status">${statusText}</div>
        </div>
      `;
    }).join("");
  }

  /* ── RENDER: SLOT TABLE ─────────────────────────────────────── */
  function renderSlotTable() {
    const search = el("slot-search")?.value.trim().toLowerCase() ?? "";
    const filter = el("slot-filter")?.value ?? "all";

    const slotsData = { ...MS.slots };
    for (let i = 1; i <= 30; i++) {
      const code = String(i);
      slotsData[code] ||= { x_mm: 0, y_mm: 0, z_mm: 0, product_name: "", dispense_delay_ms: 0 };
    }

    const entries = Object.entries(slotsData)
      .sort(([a], [b]) => Number(a) - Number(b))
      .filter(([code, slot]) => {
        const derived = slotManagerStatus(slot);
        const matchFilter = filter === "all" || filter === derived;
        const matchSearch = !search ||
          String(code).includes(search) ||
          String(slot.product_name || "").toLowerCase().includes(search);
        return matchFilter && matchSearch;
      });

    const tbody = el("slot-grid");
    if (!tbody) return;

    const canMove = motionAllowed(true);
    const canEdit = MS.online && !MS.pending && !MS.payload?.busy;
    const coordinateEditorActive = tbody.contains(document.activeElement)
      && document.activeElement?.matches?.("[data-slot-coordinate]");
    if (coordinateEditorActive) {
      renderSlotManagerSummary();
      renderSlotManagerDetail();
      return;
    }
    const renderSignature = JSON.stringify({
      search,
      filter,
      selected: MS.selectedSlotCode,
      canMove,
      canEdit,
      entries: entries.map(([code, slot]) => [code, MS.slotDrafts[code] || slot]),
    });
    if (tbody.dataset.renderSignature === renderSignature) {
      renderSlotManagerSummary();
      renderSlotManagerDetail();
      return;
    }

    tbody.innerHTML = entries.map(([code, slot]) => {
      const derived = slotManagerStatus(slot);
      const productName = slot.product_name || "EMPTY";
      const validSlot = derived === "ready";
      const canDispense = validSlot && canMove && slotAtCurrentPosition(slot);
      const draft = MS.slotDrafts[code] || slot;
      return `
        <tr class="${MS.selectedSlotCode === code ? "selected" : ""}">
          <td class="mono"><button class="slot-select-btn" data-slot-select="${esc(code)}" aria-label="Select slot ${esc(code)}">${esc(code)}</button></td>
          <td><span class="slot-badge ${derived}">${derived.toUpperCase()}</span></td>
          ${AXES.map((axis) => `<td><div class="slot-coordinate-input"><input type="number" min="0" step="0.1" value="${esc(draft[`${axis}_mm`] ?? 0)}" data-slot-coordinate="${esc(code)}" data-slot-axis="${axis}" ${canEdit ? "" : "disabled"}><span>mm</span></div></td>`).join("")}
          <td>
            <div class="slot-action-cell">
              <button class="btn-slot-save" data-slot-update="${esc(code)}" ${canEdit ? "" : "disabled"}>SAVE</button>
              <button class="btn-secondary" data-slot-teach="${esc(code)}" ${canMove ? "" : "disabled"}>CURRENT</button>
              <button class="btn-slot-goto" data-slot-goto="${esc(code)}"
                      ${validSlot && canMove ? "" : "disabled"}
                      aria-label="Go to position of slot ${esc(code)}">
                GO TO
              </button>
              <button class="btn-slot-dispense" data-slot-dispense="${esc(code)}"
                      ${canDispense ? "" : "disabled"}
                      aria-label="Dispense slot ${esc(code)} (${esc(productName)})">
                DISPENSE
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
    tbody.dataset.renderSignature = renderSignature;

    renderSlotManagerSummary();
    renderSlotManagerDetail();

  }

  function slotManagerEntries() {
    return Array.from({ length: 30 }, (_, index) => {
      const code = String(index + 1);
      return [code, MS.slots[code] || { x_mm: 0, y_mm: 0, z_mm: 0, product_name: "" }];
    });
  }

  function renderSlotManagerSummary() {
    const counts = { ready: 0, empty: 0, invalid: 0 };
    slotManagerEntries().forEach(([, slot]) => {
      const state = slotManagerStatus(slot);
      if (state in counts) counts[state] += 1;
    });
    setText("slot-summary-total", 30);
    setText("slot-summary-ready", counts.ready);
    setText("slot-summary-empty", counts.empty);
    setText("slot-summary-invalid", counts.invalid);
    setText("slot-summary-selected", MS.selectedSlotCode ? `SLOT ${String(MS.selectedSlotCode).padStart(2, "0")}` : "--");
  }

  function renderSlotManagerDetail() {
    const code = MS.selectedSlotCode;
    const slot = code ? (MS.slots[code] || {}) : null;
    const detailStatus = el("slot-detail-status");
    if (!slot) {
      setText("slot-detail-title", "SELECT A SLOT");
      setText("slot-detail-saved", "--");
      setText("slot-detail-current", "--");
      setText("slot-detail-delta", "--");
      setText("slot-detail-homing", "--");
      setText("slot-detail-estimate", "--");
      setText("slot-detail-readiness", "SELECT A SLOT");
      detailStatus.className = "slot-badge empty";
      setText("slot-detail-status", "NO SELECTION");
      return;
    }
    const state = slotManagerStatus(slot);
    const current = Object.fromEntries(AXES.map((axis) => [axis, Number(getAxis(axis).position_mm)]));
    const target = Object.fromEntries(AXES.map((axis) => [axis, Number(slot[`${axis}_mm`])])) ;
    const distance = Math.sqrt(AXES.reduce((sum, axis) => sum + (Number.isFinite(target[axis]) && Number.isFinite(current[axis]) ? (target[axis] - current[axis]) ** 2 : 0), 0));
    const speed = Number(targetSpeedPayload().speed_mm_s);
    const readiness = motionInhibitReason(true) || (state !== "ready" ? `Slot ${state.replace("-", " ")}` : "READY TO MOVE");
    setText("slot-detail-title", `SLOT ${String(code).padStart(2, "0")}`);
    detailStatus.className = `slot-badge ${state}`;
    setText("slot-detail-status", state.toUpperCase());
    setText("slot-detail-saved", `X ${fmtPos(target.x)} · Y ${fmtPos(target.y)} · Z ${fmtPos(target.z)} mm`);
    setText("slot-detail-current", `X ${fmtPos(current.x)} · Y ${fmtPos(current.y)} · Z ${fmtPos(current.z)} mm`);
    setText("slot-detail-delta", `X ${fmtDelta(target.x - current.x).text} · Y ${fmtDelta(target.y - current.y).text} · Z ${fmtDelta(target.z - current.z).text} mm`);
    setText("slot-detail-homing", allAxesHomed() ? "ALL AXES HOMED" : "HOME REQUIRED");
    setText("slot-detail-estimate", Number.isFinite(distance) && speed > 0 ? `${fmtPos(distance)} mm / ~${fmtTime(distance / speed)} s` : "NO DATA");
    setText("slot-detail-readiness", readiness);
  }

  function slotPayloadFromValues(code, values) {
    const slot = MS.slots[code] || {};
    const payload = {
      product_name: slot.product_name || "",
      dispense_delay_ms: Number(slot.dispense_delay_ms || 0),
    };
    AXES.forEach((axis) => { payload[`${axis}_mm`] = Number(values[`${axis}_mm`]); });
    if (AXES.some((axis) => !Number.isFinite(payload[`${axis}_mm`]))) {
      toast("Enter valid X, Y and Z coordinates.", "error");
      return null;
    }
    return payload;
  }

  /* ── SELECTED SLOT DIRECT EDITOR ────────────────────────────── */
  function selectedSlotCode() {
    return el("selected-slot-code")?.value || MS.selectedSlotCode;
  }

  function renderSelectedSlotSequenceProcess() {
    const operation = getOperation();
    const command = String(MS.payload?.active_command || "");
    const phase = String(operation.phase || "").toUpperCase();
    const message = String(operation.message || "").toLowerCase();
    const livePhases = new Set(["MOVE_X", "MOVE_Y", "MOVE_Z", "HOLD_AT_TARGET", "HOME_Z", "HOME_Y", "HOME_X"]);
    const isSequence = command.startsWith("slot_sequence_") || livePhases.has(phase) || message.includes("slot sequence");
    const failed = isSequence && ["FAILED", "STOPPED"].includes(phase);
    const completed = isSequence && !failed && (phase === "COMPLETED" || message.includes("completed slot sequence"));
    const slotMatch = command.match(/^slot_sequence_(.+)$/i);
    const slot = slotMatch?.[1] || MS.visualTargetSlot || MS.selectedSlotCode;
    const phaseLabel = failed ? "FAILED" : completed ? "COMPLETED" : isSequence ? (phase || "STARTING") : "IDLE";
    const text = isSequence && slot ? `SEQUENCE: ${phaseLabel} · SLOT ${String(slot).padStart(2, "0")}` : `SEQUENCE: ${phaseLabel}`;
    ["motion-selected-sequence", "visual-selected-sequence", "dashboard-selected-sequence"].forEach((id) => {
      const node = el(id);
      if (!node) return;
      node.textContent = text;
      node.className = `slot-sequence-mini ${failed ? "fault" : (completed ? "complete" : (isSequence ? "active" : ""))}`;
    });
  }

  function loadSelectedSlotEditor(force = false) {
    const select = el("selected-slot-code");
    if (!select) return;

    const codes = Object.keys(MS.slots).sort((a, b) => Number(a) - Number(b));
    const previous = MS.selectedSlotCode || select.value;
    if (select.options.length !== codes.length || codes.some((code, index) => select.options[index]?.value !== code)) {
      select.innerHTML = codes.map((code) => `<option value="${esc(code)}">Slot ${esc(code)}</option>`).join("");
    }
    if (!codes.length) return;

    MS.selectedSlotCode = codes.includes(previous) ? previous : codes[0];
    select.value = MS.selectedSlotCode;
    const slot = MS.slots[MS.selectedSlotCode] || {};
    const derived = slotStatus(slot);
    const badge = el("selected-slot-status");
    if (badge) {
      badge.className = `slot-badge ${derived}`;
      badge.textContent = derived.toUpperCase();
    }

    const current = getStatus().current_position || {};
    setText("selected-slot-current",
      `Current: X ${fmtPos(current.x_mm)} · Y ${fmtPos(current.y_mm)} · Z ${fmtPos(current.z_mm)} mm`);

    if (force || !MS.slotEditorDirty) {
      AXES.forEach((axis) => {
        el(`selected-slot-${axis}`).value = Number(slot[`${axis}_mm`] || 0);
      });
      MS.slotEditorDirty = false;
    }
  }

  function selectedSlotPayload() {
    const currentSlot = MS.slots[selectedSlotCode()] || {};
    const payload = {
      product_name: currentSlot.product_name || "",
      dispense_delay_ms: Number(currentSlot.dispense_delay_ms || 0),
    };
    AXES.forEach((axis) => {
      payload[`${axis}_mm`] = Number(el(`selected-slot-${axis}`).value);
    });
    return payload;
  }

  async function saveSelectedSlot() {
    const code = selectedSlotCode();
    if (!code) return;
    const payload = selectedSlotPayload();
    if (AXES.some((axis) => !Number.isFinite(payload[`${axis}_mm`]))) {
      toast("Enter valid X, Y and Z coordinates.", "error");
      return;
    }
    const result = await command(`Save values to slot ${code}`, `/api/slots/${code}`, payload,
      { isStop: true, noCheck: true });
    if (result) {
      MS.slotEditorDirty = false;
      loadSelectedSlotEditor(true);
    }
  }

  function loadCurrentIntoSelectedSlot() {
    const current = getStatus().current_position || {};
    AXES.forEach((axis) => {
      el(`selected-slot-${axis}`).value = Number(current[`${axis}_mm`] || 0).toFixed(3);
    });
    MS.slotEditorDirty = true;
    setText("selected-slot-current", "Current position loaded — click SAVE VALUES to store it.");
  }

  function changeSelectedSlot(code) {
    MS.selectedSlotCode = code;
    MS.visualTargetSlot = code;
    MS.slotEditorDirty = false;
    loadSelectedSlotEditor(true);
    invalidateMotionWorkflow("Slot changed — load and validate the target.");
    updateButtonStates();
  }

  function loadSelectedSlotTarget() {
    const code = selectedSlotCode();
    const slot = MS.slots[code] || {};
    AXES.forEach((axis) => {
      el(`move-${axis}`).value = Number(slot[`${axis}_mm`] || 0).toFixed(3);
    });
    invalidateMotionWorkflow(`Slot ${code} loaded — validate before movement.`);
    toast(`Slot ${code} coordinates loaded into Target Positioning.`, "ok");
  }

  async function validateSelectedSlotTarget() {
    loadSelectedSlotTarget();
    const plan = await validateMove(true);
    if (plan) await previewMove(true);
  }

  function setSlotSequenceMode(enabled) {
    MS.slotSequenceMode = Boolean(enabled);
    updateSlotSequenceMode();
    toast(MS.slotSequenceMode
      ? "Sequence Mode ON — slot commands will return all axes home."
      : "Sequence Mode OFF — standard Go To Slot restored.", "ok");
  }

  function gotoSelectedSlot() {
    const code = selectedSlotCode();
    if (!code) return;
    command(slotMotionLabel(code), slotMotionEndpoint(code), targetSpeedPayload(), {
      requireHome: true,
      timeoutMs: 600000,
    });
  }

  /* ── RENDER: ALARM SUMMARY ──────────────────────────────────── */
  function renderAlarmSummary() {
    const node = el("alarm-summary");
    if (!node) return;
    const active = alarmChannels().filter((channel) => channel.active && channel.level === "fault");
    if (!active.length) {
      node.className = "alarm-summary clear";
      node.innerHTML = `<div class="alarm-summary-title">NO ACTIVE ALARMS</div><div class="alarm-detail">Machine operation normal.</div>`;
      return;
    }
    const status = getStatus();
    const severity = status.estop ? "CRITICAL" : "WARNING";
    const effect = status.estop
      ? "All motion inhibited — E-Stop active."
      : "Motion inhibited until condition is cleared.";
    const action = status.estop
      ? "Release the physical E-Stop button, then click Reset Alarm."
      : "Click Reset Alarm, then re-home if required.";
    node.className = "alarm-summary active";
    node.innerHTML = `
      <div class="alarm-summary-title">${active.length} ACTIVE ALARM${active.length > 1 ? "S" : ""} — ${severity}</div>
      <div class="alarm-detail">${active.map((channel) => esc(`${channel.code}: ${channel.detail}`)).join("<br>")}<br>
        <b>Effect:</b> ${effect}<br>
        <b>Action:</b> ${action}
      </div>
    `;
  }

  /* ── RENDER: SAFETY STRIP ───────────────────────────────────── */
  function updateSafetyStrip() {
    const status = getStatus();
    const homed  = allAxesHomed();
    const reason = motionInhibitReason(true);
    const estopActive = Boolean(status.estop);

    // Controller
    const ctrlNode = document.getElementById("strip-controller");
    if (ctrlNode) {
      ctrlNode.className = `safety-ind-value ${MS.online ? "ok" : "fault"}`;
      ctrlNode.innerHTML = `<span class="status-dot"></span> ${MS.online ? "ONLINE" : "OFFLINE"}`;
    }

    // E-Stop
    const estopNode = el("strip-estop");
    const estopDetail = el("strip-estop-detail");
    const polarityVerified = MS.payload?.io?.polarity_verified;
    if (estopNode) {
      estopNode.className = `safety-ind-value ${estopActive ? "fault" : (polarityVerified === false ? "warn" : "ok")}`;
      estopNode.textContent = estopActive ? "E-STOP ACTIVE" : (polarityVerified === false ? "UNVERIFIED" : "CLEAR");
    }
    if (estopDetail) {
      estopDetail.textContent = polarityVerified === false ? "POLARITY PENDING" : "NC VERIFIED";
      estopDetail.className = `safety-ind-sub ${polarityVerified === false ? "warn" : "ok"}`;
    }

    // Homing
    const homingNode = el("strip-homing");
    if (homingNode) {
      homingNode.className = `safety-ind-value ${homed ? "ok" : "warn"}`;
      homingNode.textContent = homed ? "ALL HOMED ✓" : "NOT READY";
    }
    const homingDetail = el("strip-homing-detail");
    if (homingDetail) {
      homingDetail.textContent = AXES.map((a) =>
        `${a.toUpperCase()} ${getAxis(a).is_homed ? "✓" : "!"}`
      ).join("  ");
    }

    // Motion authority is the operator-controlled enable/disable state. Keep
    // it separate from readiness so an unhomed axis never looks "disabled".
    const motionNode = el("strip-motion");
    if (motionNode) {
      const motionEnabled = MS.online && MS.payload?.safety?.motion_enabled === true;
      motionNode.className = `safety-ind-value ${motionEnabled ? "ok" : "fault"}`;
      motionNode.textContent = motionEnabled ? "ENABLED" : "DISABLED";
    }

    // Readiness combines every current motion gate (connection, E-Stop,
    // alarms, Home and authority). It does not change Motion Authority.
    const readinessNode = el("strip-readiness");
    if (readinessNode) {
      const ready = !reason;
      readinessNode.className = `safety-ind-value ${ready ? "ok" : "warn"}`;
      readinessNode.textContent = ready ? "READY" : "INHIBITED";
    }

    // Reason
    const reasonNode = el("strip-motion-reason");
    if (reasonNode) {
      reasonNode.className = `motion-inhibit-reason ${reason ? "" : "clear"}`;
      reasonNode.textContent = reason || "Machine ready — motion authority enabled and all safety conditions met";
    }

    // Alarm count
    const alarmNode = el("strip-alarms");
    if (alarmNode) {
      const cnt = activeAlarmCount();
      alarmNode.className = `safety-ind-value ${cnt > 0 ? "fault" : "ok"}`;
      alarmNode.textContent = String(cnt);
    }

    // Sidebar readiness
    const sbCtrl = el("sb-controller");
    if (sbCtrl) {
      sbCtrl.className = `readiness-val ${MS.online ? "ok" : "fault"}`;
      sbCtrl.textContent = MS.online ? "ONLINE" : "OFFLINE";
    }
    const sbEstop = el("sb-estop");
    if (sbEstop) {
      sbEstop.className = `readiness-val ${estopActive ? "fault" : "ok"}`;
      sbEstop.textContent = estopActive ? "ACTIVE" : "CLEAR";
    }
    const sbAlarms = el("sb-alarms");
    if (sbAlarms) {
      sbAlarms.className = `readiness-val ${activeAlarmCount() ? "fault" : "ok"}`;
      sbAlarms.textContent = String(activeAlarmCount());
    }
    const navAlarmCount = el("nav-alarm-count");
    if (navAlarmCount) {
      const channels = alarmChannels();
      const faultCount = channels.filter((channel) => channel.active && channel.level === "fault").length;
      const warningCount = channels.filter((channel) => channel.active && channel.level === "warn").length;
      const severity = faultCount > 0 ? "fault" : (warningCount > 0 ? "warn" : "clear");
      navAlarmCount.textContent = String(faultCount + warningCount);
      navAlarmCount.className = `nav-alarm-badge ${severity}`;
      const navAlarms = el("nav-alarms");
      if (navAlarms) {
        navAlarms.classList.remove("alarm-fault", "alarm-warn", "alarm-clear");
        navAlarms.classList.add(`alarm-${severity}`);
      }
    }
  }

  /* ── RENDER: HEADER ─────────────────────────────────────────── */
  function updateHeader() {
    const status  = getStatus();
    const op      = getOperation();
    const now     = new Date().toLocaleTimeString();

    // Device identity is derived from the active controller configuration:
    // legacy Pi has no IRIV IO backend, while the new controller does.
    const deviceNode = el("hdr-device");
    const sidebarDeviceNode = el("sidebar-device-label");
    // A legacy status payload does not contain `io`; receiving any status is
    // enough to classify that controller as MOCKUP unless IRIV is explicit.
    const hasIdentity = Boolean(MS.lastStatusAt);
    const isIriv = MS.payload?.io?.enabled === true;
    const deviceShort = !hasIdentity ? "IDENTIFYING" : (isIriv ? "V1" : "MOCKUP");
    const deviceLabel = !hasIdentity
      ? "Checking device..."
      : (isIriv ? "V1" : "MOCKUP");
    const deviceClass = !hasIdentity ? "device-identifying" : (isIriv ? "device-new" : "device-legacy");
    if (deviceNode) {
      deviceNode.textContent = deviceShort;
      deviceNode.className = deviceClass;
      deviceNode.title = deviceLabel;
    }
    if (sidebarDeviceNode) {
      sidebarDeviceNode.textContent = deviceLabel;
      sidebarDeviceNode.className = deviceClass;
    }
    if (hasIdentity) document.title = `NARIT VENDING — ${deviceLabel}`;

    // Connection
    const connNode = el("hdr-connection");
    if (connNode) {
      connNode.className = MS.online ? "online" : "offline";
      connNode.textContent = MS.online ? "ONLINE" : "OFFLINE";
    }

    // IRIV IO Field Bus
    const ioNode = el("hdr-iriv-io");
    if (ioNode) {
      const ioOk = MS.payload?.io?.communication_ok === true;
      const ioEnabled = MS.payload?.io?.enabled === true;
      ioNode.textContent = !MS.online ? "--" : (ioEnabled ? (ioOk ? "ONLINE" : "OFFLINE") : "DISABLED");
      ioNode.className = !MS.online || !ioEnabled ? "offline" : (ioOk ? "online" : "fault");
    }

    // Nucleo STM32 Motion Controller Link
    const nucleoNode = el("hdr-nucleo");
    if (nucleoNode) {
      const nucOk = MS.payload?.nucleo?.communication_ok === true;
      const nucEnabled = MS.payload?.nucleo?.enabled === true;
      nucleoNode.textContent = !MS.online ? "--" : (nucEnabled ? (nucOk ? "SAFE LINK" : "OFFLINE") : "DISABLED");
      nucleoNode.className = !MS.online || !nucEnabled ? "offline" : (nucOk ? "online" : "fault");
    }

    // Machine state
    const msNode = el("hdr-machine-state");
    if (msNode) {
      let cls = "state-notready";
      let txt = "NOT READY";
      const s = getStatus();
      if (!MS.online) { cls = "state-alarm"; txt = "OFFLINE"; }
      else if (s.estop) { cls = "state-estop"; txt = "E-STOP"; }
      else if (MS.payload?.busy) {
        const cmd = MS.payload?.active_command || "";
        if (cmd.startsWith("home")) { cls = "state-homing"; txt = "HOMING"; }
        else { cls = "state-moving"; txt = "MOVING"; }
      }
      else if (s.state === "alarm") { cls = "state-alarm"; txt = "ALARM"; }
      else if (allAxesHomed()) { cls = "state-ready"; txt = "READY"; }
      msNode.className = cls;
      msNode.textContent = txt;
    }

    // Time
    setText("hdr-time", now);
    // Footer time
    setText("footer-status-time", now);
  }

  /* ── RENDER: FOOTER STATUS BAR ──────────────────────────────── */
  function updateFooter() {
    const status   = getStatus();
    const homed    = allAxesHomed();
    const estop    = Boolean(status.estop);
    const ready    = motionInhibitReason(true) === "";
    const op       = getOperation();

    // Connection pill
    const connPill = el("footer-connection");
    if (connPill) {
      connPill.className = `status-pill ${MS.online ? "online" : "offline"}`;
      connPill.innerHTML = `<span class="status-dot"></span>${MS.online ? "ONLINE" : "OFFLINE"}`;
    }
    // Ready pill
    const readyPill = el("footer-ready");
    if (readyPill) {
      readyPill.className = `status-pill ${ready ? "ready" : "not-ready"}`;
      readyPill.textContent = ready ? "READY" : "NOT READY";
    }
    // E-Stop pill
    const estopPill = el("footer-estop");
    if (estopPill) {
      estopPill.className = `status-pill ${estop ? "estop" : "clear"}`;
      estopPill.textContent = estop ? "E-STOP ACTIVE" : "E-STOP CLEAR";
    }
    // Homed pill
    const homedPill = el("footer-homed");
    if (homedPill) {
      homedPill.className = `status-pill ${homed ? "homed" : "not-homed"}`;
      homedPill.textContent = homed ? "ALL HOMED" : "NOT HOMED";
    }

    // Center text
    const cmd = MS.payload?.active_command || "None";
    const motionState = MS.payload?.busy ? "Executing" : "Idle";
    setText("footer-status-text",
      `Command: ${cmd}  |  Motion: ${motionState}  |  ${op.message || "Ready"}`);

    // Persistent compact coordinates — visible on every workspace and sourced
    // from the same controller snapshot as the Motion Control axis cards.
    for (const axis of AXES) {
      const node = el(`footer-axis-${axis}`);
      const output = node?.querySelector("output");
      const position = Number(getAxis(axis).position_mm);
      if (output) output.textContent = MS.online && Number.isFinite(position) ? fmtPos(position) : "--";
      if (node) {
        const moving = MS.payload?.busy && String(op.active_axis || "").toLowerCase() === axis;
        node.classList.toggle("moving", Boolean(moving));
        node.classList.toggle("offline", !MS.online);
        node.title = `${axis.toUpperCase()} axis actual position: ${output?.textContent || "--"} mm`;
      }
    }
  }

  function renderMotionCommand() {
    const command = MS.payload?.motion_command || {};
    const operation = getOperation();
    const elapsed = command.elapsed_s == null ? NaN : Number(command.elapsed_s);
    const estimate = command.estimated_duration_s == null ? NaN : Number(command.estimated_duration_s);
    const remaining = Number.isFinite(elapsed) && Number.isFinite(estimate)
      ? Math.max(estimate - elapsed, 0)
      : NaN;
    setText("motion-command-id", command.command_id ? String(command.command_id).slice(0, 12).toUpperCase() : "NONE");
    setText("motion-command-phase", `${String(command.command_type || "IDLE").toUpperCase()} / ${String(operation.phase || "READY").toUpperCase()}`);
    setText("motion-command-time", `${Number.isFinite(elapsed) ? fmtTime(elapsed) + " s" : "--"} / ${Number.isFinite(remaining) ? fmtTime(remaining) + " s" : "NO DATA"}`);
    setText("motion-command-trajectory", String(command.trajectory_state || "READY").toUpperCase());
    setText("motion-command-queue", command.queue_depth ?? 0);
    const controlledStop = el("controlled-stop");
    if (controlledStop) controlledStop.disabled = !MS.online || !MS.payload?.busy;
    const abort = el("abort-motion");
    if (abort) abort.disabled = !MS.online || !MS.payload?.busy;
  }

  /* ── RENDER: BUTTON STATES ──────────────────────────────────── */
  function updateButtonStates() {
    const canHome = canHomeAxis();

    // Jog buttons
    const inhibitReason = motionInhibitReason(false);
    const jogBanner = el("jog-inhibit-banner");
    if (jogBanner) {
      jogBanner.style.display = inhibitReason ? "flex" : "none";
      setText("jog-inhibit-text", inhibitReason);
    }
    $$("[data-jog]").forEach((btn) => {
      const [axis, direction] = btn.dataset.jog.split(":");
      const state = getAxis(axis);
      const towardMin = Number(direction) < 0;
      const atDirectionalLimit = towardMin ? Boolean(state.head_limit) : Boolean(state.tail_limit);
      // Keep both directions available. The Controller remains authoritative:
      // a direction into an active limit is rejected without latching STOP,
      // while the direction away from it moves immediately.
      btn.disabled = !canJogAxis(axis);
      btn.dataset.limitActive = atDirectionalLimit ? "true" : "false";
      btn.title = atDirectionalLimit
        ? `${axis.toUpperCase()} ${towardMin ? "Min" : "Max"} limit is active; this direction will be safely rejected`
        : `Hold to jog ${axis.toUpperCase()}${towardMin ? "−" : "+"}; release to stop`;
    });

    if (!MS.manualJog.active) {
      const bypassHome = Boolean($("#jog-allow-unhomed")?.checked);
      const homed = allAxesHomed();
      setText("jog-status-text", homed ? "READY" : (bypassHome ? "UNHOMED JOG PERMITTED" : "HOME REQUIRED"));
      const jogStatus = el("jog-status-text");
      if (jogStatus) {
        jogStatus.className = `safety-ind-sub ${homed ? "ok" : (bypassHome ? "warn" : "")}`;
      }
    }

    const selectedCode = selectedSlotCode();
    const selectedSlot = MS.slots[selectedCode] || {};
    const canUseSlot = motionAllowed(true);
    const selectedSlotReady = slotStatus(selectedSlot) === "ready";
    updateSlotSequenceMode();
    el("selected-slot-load-target").disabled = !MS.online || !selectedSlotReady;
    el("selected-slot-validate").disabled = !canUseSlot || !selectedSlotReady;
    el("selected-slot-goto").disabled = !canUseSlot || !selectedSlotReady;
    el("target-load-current").disabled = !MS.online;
    el("target-load-selected-slot").disabled = !MS.online || !selectedSlotReady;
    if (document.getElementById("visual-load-preview")) updateVisualButtons();

    // Home buttons — use the same Controller-derived interlock reason as all
    // other motion controls.  In particular, do not present Home as available
    // while the explicit Motion Enable latch is off.
    const homeReason = motionInhibitReason(false);
    const homeAllButton = el("home-all");
    homeAllButton.disabled = Boolean(homeReason);
    homeAllButton.title = homeReason || "Home all axes";
    homeAllButton.setAttribute("aria-disabled", String(Boolean(homeReason)));

    $$('[data-travel-axis]').forEach((button) => {
      const axis = button.dataset.travelAxis;
      // Physical endpoint seeking is also the recovery/calibration path when
      // an axis has lost its coordinate reference, so it must not require Home.
      const reason = axis ? motionInhibitReason(false) : "Axis is unavailable";
      button.disabled = Boolean(reason);
      button.title = reason || `${axis.toUpperCase()} axis is ready for the next command`;
      button.setAttribute("aria-disabled", String(Boolean(reason)));
    });
    $$('[data-axis-goto]').forEach((button) => {
      const axis = button.dataset.axisGoto;
      const reason = axis ? motionInhibitReasonForAxes([axis]) : "Axis is unavailable";
      button.disabled = Boolean(reason);
      button.title = reason || `Move ${axis.toUpperCase()} to the entered position`;
    });
    const travelReason = motionInhibitReason(false);
    const travelInhibit = el("travel-limit-inhibit");
    if (travelInhibit) {
      travelInhibit.textContent = travelReason
        ? `LOCKED: ${travelReason}`
        : "READY: Physical-limit seek ignores configured travel and stops only at the selected sensor or a safety fault.";
      travelInhibit.classList.toggle("is-ready", !travelReason);
    }
    const travelReset = el("travel-reset-interlock");
    if (travelReset) {
      travelReset.disabled = !MS.online || Boolean(MS.payload?.busy) || (!MS.payload?.safety?.stop_requested && !MS.payload?.last_error);
    }
    const operatorStop = el("operator-stop");
    if (operatorStop) operatorStop.disabled = !MS.online;
    AXES.forEach((axis) => {
      const maximum = Number(MS.config?.axes?.[axis]?.max_travel_mm);
      const data = getAxis(axis);
      setText(`travel-limit-${axis}-range`, `0.0 — ${Number.isFinite(maximum) ? fmtPos(maximum) : "--"} mm`);
      setText(`travel-limit-${axis}-current`, `${fmtPos(data.position_mm)} mm`);
      setText(`travel-limit-${axis}-sensors`, `MIN ${data.head_limit ? "TRIGGERED" : "CLEAR"} · MAX ${data.tail_limit ? "TRIGGERED" : "CLEAR"}`);
      const card = document.querySelector(`[data-axis-card="${axis}"]`);
      if (card) card.classList.toggle("limit-active", Boolean(data.head_limit || data.tail_limit));
      const input = el(`move-${axis}`);
      if (input && Number.isFinite(maximum)) input.max = String(maximum);
      const directInput = el(`axis-goto-${axis}`);
      if (directInput && Number.isFinite(maximum)) directInput.max = String(maximum);
    });
    $$(".home-axis").forEach((btn) => {
      btn.disabled = Boolean(homeReason);
      btn.title = homeReason || `Home ${btn.dataset.axis?.toUpperCase() || "axis"}`;
      btn.setAttribute("aria-disabled", String(Boolean(homeReason)));
    });

    // Stop button
    el("stop-button").disabled = !MS.online;

    // Clear alarm
    el("clear-alarm").disabled = !MS.online || Boolean(MS.payload?.busy);

    // Execute move
    updateExecuteButton();

    // Active command display
    setText("active-command", `Command: ${MS.payload?.active_command || "None"}`);

    // Operation message
    setText("operation-message", getOperation().message || "Controller ready");
  }

  /* ── RENDER: FEED OVERRIDE ──────────────────────────────────── */
  function updateFeedOverride() {
    const pctDisplay = document.getElementById("fo-pct-display");
    if (pctDisplay) pctDisplay.textContent = String(MS.feedOverridePct);
    const overrideValue = document.getElementById("fo-override-val");
    if (overrideValue) overrideValue.textContent = `${MS.feedOverridePct} %`;

    // Programmed speed from the target speed field
    syncAxisSpeedBanks();
    const progSpd = effectiveMotionSpeed();
    const effSpd  = progSpd * (MS.feedOverridePct / 100);
    const programmedSpeed = document.getElementById("fo-prog-speed");
    const effectiveSpeed = document.getElementById("fo-eff-speed");
    if (programmedSpeed) programmedSpeed.textContent = progSpd > 0 ? `${fmtSpd(progSpd)} mm/s` : "-- mm/s";
    if (effectiveSpeed) effectiveSpeed.textContent = progSpd > 0 ? `${fmtSpd(effSpd)} mm/s` : "-- mm/s";

    // Highlight active preset
    $$(".fo-preset-btn").forEach((btn) => {
      btn.classList.toggle("active", Number(btn.dataset.fo) === MS.feedOverridePct);
    });
  }

  /* ── MASTER RENDER ──────────────────────────────────────────── */
  const VALID_VIEWS = new Set([
    "dashboard", "motion", "visualization", "diagnostics", "io-status", "configuration",
    "motor-test", "system-control", "mqtt", "slots", "alarms", "events", "flow", "sequence-monitor", "architecture",
  ]);
  const DIAGNOSTIC_VIEWS = new Set(["diagnostics", "io-status", "alarms", "events", "flow", "sequence-monitor", "architecture"]);
  const POSITION_VIEWS = new Set(["slots", "visualization"]);
  const SETUP_VIEWS = new Set(["configuration", "motor-test"]);

  if (!window.NaritRouter) throw new Error("HMI router failed to load");
  if (!window.NaritPageControllers) throw new Error("HMI page controllers failed to load");
  if (!window.NaritIOPageController) throw new Error("HMI I/O page controller failed to load");
  if (!window.NaritEventsPageController) throw new Error("HMI Events page controller failed to load");
  if (!window.NaritFlowPageController) throw new Error("HMI Flow page controller failed to load");
  if (!window.NaritMqttPageController) throw new Error("HMI MQTT page controller failed to load");
  if (!window.NaritAlarmsPageController) throw new Error("HMI Alarms page controller failed to load");
  if (!window.NaritSlotsPageController) throw new Error("HMI Slots page controller failed to load");
  if (!window.NaritSelectedSlotController) throw new Error("HMI Selected Slot controller failed to load");
  if (!window.NaritVisualizationPageController) throw new Error("HMI Visualization page controller failed to load");
  if (!window.NaritDemoPageController) throw new Error("HMI Demo page controller failed to load");
  if (!window.NaritIORegistryView) throw new Error("HMI I/O registry view failed to load");
  if (!window.NaritSystemControlPageController) throw new Error("HMI System Control page controller failed to load");
  if (!window.NaritMotionTravelController) throw new Error("HMI Motion Travel controller failed to load");
  if (!window.NaritMotionTargetController) throw new Error("HMI Motion Target controller failed to load");
  if (!window.NaritMotionJogSafetyController) throw new Error("HMI Motion Jog Safety controller failed to load");
  const pageControllers = window.NaritPageControllers.createRegistry({
    onError: (error, context) => console.error(
      `[HMI] ${context.view || "unknown"} page ${context.phase} failed`,
      error,
    ),
  });
  const workspaceRouter = window.NaritRouter.create({
    state: MS,
    validViews: VALID_VIEWS,
    fallbackView: "motion",
    groups: [
      { primaryId: "nav-diagnostics", views: DIAGNOSTIC_VIEWS },
      { primaryId: "nav-configuration", views: SETUP_VIEWS },
      { primaryId: "nav-slots", views: POSITION_VIEWS },
    ],
    beforeNavigate: (currentView, nextView) => {
      if (currentView === "motor-test" && nextView !== "motor-test" && motorTestState().armed) {
        stopMotorTestJog("Motor Test Mode closed");
        apiCall("/api/maintenance/motor-test", "POST", { action: "cancel" }).then(refresh).catch(() => {});
      }
    },
    afterNavigate: (nextView) => {
      renderWorkspacePages();
      pageControllers.activate(nextView);
    },
  });


  function switchWorkspace(view, updateHash = true) {
    return workspaceRouter.navigate(view, updateHash);
  }

  function openHomingControls() {
    switchWorkspace("motion");
    window.requestAnimationFrame(() => {
      const homingControls = el("homing-controls");
      homingControls?.scrollIntoView({ behavior: "smooth", block: "start" });
      homingControls?.focus({ preventScroll: true });
      homingControls?.classList.add("attention-focus");
      window.setTimeout(() => homingControls?.classList.remove("attention-focus"), 1600);
    });
  }

  function axisSpeedLimit(axis) {
    const cfg = MS.config?.axes?.[axis] || {};
    const candidates = [cfg.commissioned_max_speed_mm_s, cfg.max_speed_mm_s, Number(cfg.max_pulse_hz) / Number(cfg.steps_per_mm)]
      .map(Number).filter((value) => Number.isFinite(value) && value > 0);
    return candidates.length ? Math.min(...candidates) : 250;
  }

  function axisSpeed(axis) {
    return Math.max(0.1, Math.min(axisSpeedLimit(axis), Number(MS.axisSpeeds[axis]) || 5));
  }

  function effectiveMotionSpeed(axes = AXES) {
    const selected = axes.filter((axis) => AXES.includes(axis));
    return Math.min(...(selected.length ? selected : AXES).map(axisSpeed)) * (MS.feedOverridePct / 100);
  }

  function renderAxisSpeedBanks() {
    $$('[data-axis-speed-bank]').forEach((bank) => {
      if (bank.dataset.ready === "true") return;
      bank.innerHTML = AXES.map((axis) => `<label class="axis-speed-row">
        <strong>${axis.toUpperCase()}</strong>
        <input type="range" min="0.1" max="250" step="0.1" data-axis-speed-range="${axis}" aria-label="${axis.toUpperCase()} axis speed">
        <input type="number" min="0.1" max="250" step="0.1" data-axis-speed-number="${axis}" aria-label="${axis.toUpperCase()} axis speed value">
        <span>mm/s</span><small data-axis-speed-conversion="${axis}">-- pulse/s · -- rpm</small>
      </label>`).join("") + '<p class="axis-speed-note">Single-axis commands use that axis value. Coordinated XYZ and slot moves use the lowest participating-axis value.</p>';
      bank.dataset.ready = "true";
    });
    syncAxisSpeedBanks();
  }

  function syncAxisSpeedBanks() {
    AXES.forEach((axis) => {
      const speed = axisSpeed(axis);
      MS.axisSpeeds[axis] = speed;
      const max = axisSpeedLimit(axis);
      $$(`[data-axis-speed-range="${axis}"], [data-axis-speed-number="${axis}"]`).forEach((input) => {
        input.max = String(max);
        if (document.activeElement !== input) input.value = speed.toFixed(1);
      });
      const cfg = MS.config?.axes?.[axis] || {};
      const ppm = Number(cfg.steps_per_mm || 0);
      const ppr = Number(cfg.motor_steps_per_rev || 0) * Number(cfg.driver_microsteps || 0);
      const pulse = speed * ppm;
      const rpm = ppr > 0 ? pulse * 60 / ppr : NaN;
      $$(`[data-axis-speed-conversion="${axis}"]`).forEach((node) => {
        node.textContent = `${Math.round(pulse).toLocaleString()} pulse/s · ${Number.isFinite(rpm) ? rpm.toFixed(1) : "--"} rpm`;
      });
    });
    const coordinated = effectiveMotionSpeed();
    MS.selectedJogSpeed = coordinated;
    setText("jog-speed-display", coordinated.toFixed(1));
  }

  function setAxisSpeed(axis, rawValue, invalidate = true) {
    if (!AXES.includes(axis)) return;
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed) || parsed <= 0) return;
    MS.axisSpeeds[axis] = Math.min(axisSpeedLimit(axis), Math.max(0.1, parsed));
    try { localStorage.setItem("narit.axisSpeeds", JSON.stringify(MS.axisSpeeds)); } catch (_) {}
    if (invalidate && MS.validation.stage !== "idle") invalidateMotionWorkflow("Axis speed changed — validate, preview and arm the GOTO command again.");
    syncAxisSpeedBanks();
    updateFeedOverride();
    // Speed is a next-command parameter. Re-evaluate direct Jog and Min/Max
    // controls immediately; they are not dependent on the GOTO arm token.
    updateButtonStates();
    const locked = motionInhibitReasonForAxes([axis]);
    setText("travel-limit-feedback", locked
      ? `${axis.toUpperCase()} speed saved for the next command. Motion remains locked: ${locked}`
      : `${axis.toUpperCase()} speed set to ${axisSpeed(axis).toFixed(1)} mm/s. The axis is ready for the next Min/Max or Jog command.`);
  }

  function applySetupTab(tabName = "motor") {
    MS.currentSetupTab = tabName;
    const motorFields = new Set(["motor_steps_per_rev", "driver_microsteps", "lead_screw_pitch_mm", "steps_per_mm", "max_travel_mm", "max_speed_mm_s", "default_speed_mm_s", "max_pulse_hz", "commissioned_max_speed_mm_s", "acceleration", "deceleration", "jog_step_mm", "settle_delay", "forward_direction", "scurve_enabled", "scurve_profile_type", "scurve_start_speed_mm_s", "scurve_end_speed_mm_s", "scurve_max_jerk_mm_s3", "scurve_control_period_us"]);
    const homingFields = new Set(["home_position_mm", "homing_search_speed_mm_s", "homing_latch_speed_mm_s", "homing_timeout_s", "home_direction"]);
    const travelFields = new Set(["motor_steps_per_rev", "driver_microsteps", "lead_screw_pitch_mm", "steps_per_mm", "max_travel_mm"]);
    const motorPanel = $(".motor-pulse-config-panel");
    const travelPanel = $(".travel-calibration-panel");
    const pinPanel = $(".configuration-pin-panel");
    const showMotorPanel = tabName === "motor" || tabName === "homing" || tabName === "travel";
    if (motorPanel) motorPanel.hidden = !showMotorPanel;
    if (travelPanel) travelPanel.hidden = tabName !== "travel";
    if (pinPanel) pinPanel.hidden = showMotorPanel;
    $$("[data-motor-card] label").forEach((label) => {
      const field = label.querySelector("[data-config-field]")?.dataset.configField;
      label.hidden = tabName === "homing" ? !homingFields.has(field) : tabName === "travel" ? !travelFields.has(field) : tabName === "motor" ? !motorFields.has(field) : false;
    });
    $$("[data-motor-card] .motor-derived").forEach((node) => { node.hidden = tabName === "homing"; });
    $$("[data-motor-card] .scurve-config").forEach((node) => { node.hidden = tabName !== "motor"; });
    $$("#configuration-pin-editor .schedule-card").forEach((card, index) => {
      card.hidden = (tabName === "nucleo" && index !== 0) || (tabName === "io" && index !== 1);
    });
    $$('[data-setup-tab]').forEach((button) => {
      const active = button.dataset.setupTab === tabName;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.setAttribute("tabindex", active ? "0" : "-1");
    });
    $$('[data-setup-sidebar]').forEach((button) => {
      const active = button.dataset.setupSidebar === tabName && MS.currentView === "configuration";
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
  }

  function renderVisualization() {
    const slotGrid = document.getElementById("visual-slot-grid");
    if (!slotGrid) return;

    const commandName = MS.payload?.active_command || "";
    const commandTarget = commandName.match(/^goto_slot_(\d+)$/)?.[1];
    if (commandTarget) MS.visualTargetSlot = commandTarget;
    const targetCode = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const targetSlot = MS.slots[targetCode] || {};
    const moving = Boolean(MS.pending || MS.payload?.busy);
    const current = getStatus().current_position || {};
    const xPosition = Number(current.x_mm ?? getAxis("x").position_mm ?? 0);
    const yPosition = Number(current.y_mm ?? getAxis("y").position_mm ?? 0);
    const zPosition = Number(current.z_mm ?? getAxis("z").position_mm ?? 0);
    const xMax = Number(MS.config?.axes?.x?.max_travel_mm || 1);
    const yMax = Number(MS.config?.axes?.y?.max_travel_mm || 1);
    const zMax = Number(MS.config?.axes?.z?.max_travel_mm || 1);
    const xPct = Math.max(0, Math.min(100, (xPosition / xMax) * 100));
    const yPct = Math.max(0, Math.min(100, (yPosition / yMax) * 100));
    const zPct = Math.max(0, Math.min(100, (zPosition / zMax) * 100));

    let nearestCode = "";
    let nearestDistance = Infinity;
    Object.entries(MS.slots).forEach(([code, slot]) => {
      if (slotStatus(slot) !== "ready") return;
      const distance = Math.hypot(xPosition - Number(slot.x_mm || 0), yPosition - Number(slot.y_mm || 0));
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestCode = code;
      }
    });
    if (nearestDistance > 3) nearestCode = "";

    slotGrid.innerHTML = Array.from({ length: 30 }, (_, index) => {
      const code = String(index + 1);
      const slot = MS.slots[code] || {};
      const configured = slotStatus(slot) === "ready";
      const classes = ["visual-slot", configured ? "configured" : "empty"];
      if (code === targetCode) classes.push("target");
      if (code === targetCode && moving) classes.push("moving-target");
      if (code === nearestCode) classes.push("at-position");
      return `<button type="button" class="${classes.join(" ")}" data-visual-slot="${code}"
        title="Select Slot ${code} to edit, save or move">
        <span class="visual-slot-number">${String(index + 1).padStart(2, "0")}</span>
        <small>${configured ? `X${fmt(slot.x_mm, 0)} · Y${fmt(slot.y_mm, 0)}` : "NOT SET"}</small>
      </button>`;
    }).join("");

    const markerX = 6 + xPct * .9;
    const markerY = 8 + yPct * .84;
    const xyMarker = document.getElementById("vis-xy-carriage");
    if (xyMarker) {
      xyMarker.style.left = `${markerX}%`;
      xyMarker.style.top = `${markerY}%`;
      xyMarker.classList.toggle("moving", moving);
    }

    const targetIndex = Math.max(0, Number(targetCode || 1) - 1);
    const targetColumn = targetIndex % 6;
    const targetRow = Math.floor(targetIndex / 6);
    const targetX = 6 + ((targetColumn + .5) / 6) * 90;
    const targetY = 8 + ((targetRow + .5) / 5) * 84;
    const trajectory = document.getElementById("visual-trajectory");
    const trajectoryLine = document.getElementById("visual-trajectory-line");
    if (trajectory && trajectoryLine) {
      trajectory.classList.toggle("active", moving && Boolean(targetCode));
      trajectoryLine.setAttribute("x1", markerX);
      trajectoryLine.setAttribute("y1", markerY);
      trajectoryLine.setAttribute("x2", targetX);
      trajectoryLine.setAttribute("y2", targetY);
    }

    const zAxis = getAxis("z");
    const zMarker = document.getElementById("vis-z-carriage");
    const zFill = document.getElementById("vis-z-fill");
    const zTargetMarker = document.getElementById("vis-z-target-marker");
    if (zMarker) zMarker.style.bottom = `${zPct}%`;
    if (zFill) zFill.style.height = `${zPct}%`;
    const targetZPct = Math.max(0, Math.min(100, (Number(targetSlot.z_mm || 0) / zMax) * 100));
    if (zTargetMarker) {
      zTargetMarker.style.bottom = `${targetZPct}%`;
      zTargetMarker.classList.toggle("active", Boolean(targetCode));
    }

    const zState = document.getElementById("vis-z-state");
    if (zState) {
      const homed = Boolean(zAxis.is_homed);
      zState.className = `axis-state-badge ${homed ? "homed" : "not-homed"}`;
      zState.textContent = homed ? "HOMED" : "NOT HOMED";
    }

    setText("vis-x-value", fmtPos(xPosition));
    setText("vis-y-value", fmtPos(yPosition));
    setText("vis-z-value", fmtPos(zPosition));
    setText("vis-z-max", fmt(zMax, 1));
    setText("vis-target-slot", targetCode ? `SLOT ${String(targetCode).padStart(2, "0")}` : "--");
    setText("vis-target-z", targetCode ? `${fmtPos(targetSlot.z_mm)} mm` : "-- mm");
    setText("vis-z-steps", fmtSteps(zAxis.position_steps));
    setText("vis-motion-state", moving ? "MOVING" : "IDLE");
    setText("vis-target-summary", targetCode ? `SLOT ${String(targetCode).padStart(2, "0")}` : "SLOT --");
    setText("vis-target-coordinates", targetCode
      ? `X ${fmtPos(targetSlot.x_mm)} · Y ${fmtPos(targetSlot.y_mm)} · Z ${fmtPos(targetSlot.z_mm)} mm`
      : "X -- · Y -- · Z --");
    setText("vis-gantry-state", moving ? `MOVING TO SLOT ${String(targetCode).padStart(2, "0")}` : "IDLE");
    setText("vis-gantry-detail", `X ${fmtPos(xPosition)} · Y ${fmtPos(yPosition)} · Z ${fmtPos(zPosition)} mm`);
    renderVisualSlotEditor();
  }

  function renderVisualSlotEditor(force = false) {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    const derived = slotStatus(slot);
    setText("visual-editor-title", `SLOT ${String(code).padStart(2, "0")}`);
    const badge = el("visual-editor-status");
    if (badge) {
      badge.className = `slot-badge ${derived}`;
      badge.textContent = derived.toUpperCase();
    }
    if (force || !MS.visualEditorDirty) {
      AXES.forEach((axis) => {
        const input = el(`visual-slot-${axis}`);
        if (input) input.value = Number(slot[`${axis}_mm`] || 0);
      });
      MS.visualEditorDirty = false;
    }
  }

  function visualSlotValues() {
    return Object.fromEntries(AXES.map((axis) => [`${axis}_mm`, Number(el(`visual-slot-${axis}`)?.value)]));
  }

  function selectVisualizationSlot(code) {
    MS.selectedSlotCode = String(code || "1");
    MS.visualTargetSlot = MS.selectedSlotCode;
    MS.visualEditorDirty = false;
    MS.visualPreview = null;
    MS.visualEditMode = false;
    loadSelectedSlotEditor(true);
    renderVisualizationV32();
  }

  function updateVisualizationCoordinateDraft() {
    MS.visualEditorDirty = true;
    MS.visualPreview = null;
    const values = visualSlotValues();
    const original = MS.visualOriginalSlot || {};
    setText("visual-edit-comparison", AXES.map((axis) => `${axis.toUpperCase()} ${fmtPos(original[`${axis}_mm`])} → ${fmtPos(values[`${axis}_mm`])}`).join(" · "));
    updateVisualButtons();
  }

  function loadCurrentIntoVisualSlot() {
    if (!MS.visualEditMode) return;
    const current = getStatus().current_position || {};
    AXES.forEach((axis) => {
      el(`visual-slot-${axis}`).value = Number(current[`${axis}_mm`] || 0).toFixed(3);
    });
    MS.visualEditorDirty = true;
    const original = MS.visualOriginalSlot || {};
    setText("visual-edit-comparison", AXES.map((axis) => `${axis.toUpperCase()} ${fmtPos(original[`${axis}_mm`])} → ${fmtPos(current[`${axis}_mm`])}`).join(" · "));
    updateVisualButtons();
  }

  async function saveVisualSlot() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const payload = slotPayloadFromValues(code, visualSlotValues());
    if (!payload) return;
    const result = await command(`Save visualization slot ${code}`, `/api/slots/${code}`, payload,
      { isStop: true, noCheck: true });
    if (result) {
      MS.visualEditorDirty = false;
      renderVisualSlotEditor(true);
    }
  }

  function visualSlotIsValid(slot) {
    return AXES.every((axis) => {
      const value = Number(slot?.[`${axis}_mm`]);
      const max = Number(MS.config?.axes?.[axis]?.max_travel_mm);
      return Number.isFinite(value) && Number.isFinite(max) && value >= 0 && value <= max;
    });
  }

  function visualDataState() {
    const ageMs = MS.lastStatusAt ? Date.now() - MS.lastStatusAt : Infinity;
    if (!MS.online) return { label: "OFFLINE", className: "fault", live: false, reason: "Controller API unavailable" };
    if (ageMs > 2500) return { label: "STALE DATA", className: "warn", live: false, reason: `Last API update ${Math.round(ageMs / 1000)} seconds ago` };
    return { label: "LIVE", className: "ok", live: true, reason: "API status updated within 1 second" };
  }

  function renderVisualizationV32() {
    const slotGrid = document.getElementById("visual-slot-grid");
    if (!slotGrid) return;

    const dataState = visualDataState();
    const status = getStatus();
    const operation = getOperation();
    const current = status.current_position || {};
    const commandName = MS.payload?.active_command || "";
    const commandTarget = commandName.match(/^goto_slot_(\d+)$/)?.[1];
    const selectedCode = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const targetCode = commandTarget || selectedCode;
    const targetSlot = MS.slots[targetCode] || {};
    const selectedSlot = MS.slots[selectedCode] || {};
    const moving = dataState.live && Boolean(MS.payload?.busy);
    const xMax = Number(MS.config?.axes?.x?.max_travel_mm || 1);
    const yMax = Number(MS.config?.axes?.y?.max_travel_mm || 1);
    const zMax = Number(MS.config?.axes?.z?.max_travel_mm || 1);
    const safeZ = Number(MS.config?.safe_z_mm || 0);
    const xPosition = dataState.live ? Number(current.x_mm ?? getAxis("x").position_mm) : NaN;
    const yPosition = dataState.live ? Number(current.y_mm ?? getAxis("y").position_mm) : NaN;
    const zPosition = dataState.live ? Number(current.z_mm ?? getAxis("z").position_mm) : NaN;
    const targetValid = visualSlotIsValid(targetSlot) && slotStatus(targetSlot) === "ready";
    const selectedValid = visualSlotIsValid(selectedSlot) && slotStatus(selectedSlot) === "ready";
    const targetX = Number(targetSlot.x_mm);
    const targetY = Number(targetSlot.y_mm);
    const targetZ = Number(targetSlot.z_mm);
    const xPct = Number.isFinite(xPosition) ? Math.max(0, Math.min(100, xPosition / xMax * 100)) : 0;
    const yPct = Number.isFinite(yPosition) ? Math.max(0, Math.min(100, yPosition / yMax * 100)) : 0;
    const zPct = Number.isFinite(zPosition) ? Math.max(0, Math.min(100, zPosition / zMax * 100)) : 0;
    const targetXPct = targetValid ? Math.max(0, Math.min(100, targetX / xMax * 100)) : 0;
    const targetYPct = targetValid ? Math.max(0, Math.min(100, targetY / yMax * 100)) : 0;
    const targetZPct = targetValid ? Math.max(0, Math.min(100, targetZ / zMax * 100)) : 0;
    const atPosition = dataState.live && targetValid && Math.hypot(xPosition - targetX, yPosition - targetY, zPosition - targetZ) <= 2;

    slotGrid.innerHTML = Array.from({ length: 30 }, (_, index) => {
      const code = String(index + 1);
      const slot = MS.slots[code] || {};
      const configured = slotStatus(slot) === "ready";
      const valid = configured && visualSlotIsValid(slot);
      const isSelected = code === selectedCode;
      const isCommandTarget = code === targetCode && moving;
      const isAtPosition = code === targetCode && atPosition;
      const classes = ["visual-slot", !configured ? "empty" : valid ? "configured" : "invalid"];
      if (isSelected) classes.push("selected");
      if (isCommandTarget) classes.push("moving-target");
      if (isAtPosition) classes.push("at-position");
      const stateLabel = !configured ? "EMPTY" : !valid ? "INVALID" : isCommandTarget ? "TARGET" : isAtPosition ? "AT POSITION" : isSelected ? "SELECTED" : "READY";
      return `<button type="button" class="${classes.join(" ")}" data-visual-slot="${code}" title="Select Slot ${code}">
        <span class="visual-slot-number">${String(index + 1).padStart(2, "0")}</span>
        <small>${stateLabel}</small>
      </button>`;
    }).join("");

    const markerX = 5 + xPct * .9;
    const markerY = 5 + yPct * .9;
    const targetMarkerX = 5 + targetXPct * .9;
    const targetMarkerY = 5 + targetYPct * .9;
    const xyMarker = document.getElementById("vis-xy-carriage");
    const xyTarget = document.getElementById("vis-xy-target");
    if (xyMarker) {
      xyMarker.style.left = `${markerX}%`;
      xyMarker.style.top = `${markerY}%`;
      xyMarker.classList.toggle("moving", moving);
      xyMarker.classList.toggle("unknown", !dataState.live);
    }
    if (xyTarget) {
      xyTarget.style.left = `${targetMarkerX}%`;
      xyTarget.style.top = `${targetMarkerY}%`;
      xyTarget.classList.toggle("active", targetValid);
    }

    const trajectory = document.getElementById("visual-trajectory");
    const trajectoryLine = document.getElementById("visual-trajectory-line");
    if (trajectory && trajectoryLine) {
      trajectory.classList.toggle("active", dataState.live && targetValid && Boolean(MS.visualPreview || moving));
      trajectoryLine.setAttribute("x1", markerX);
      trajectoryLine.setAttribute("y1", markerY);
      trajectoryLine.setAttribute("x2", targetMarkerX);
      trajectoryLine.setAttribute("y2", targetMarkerY);
    }

    const zAxis = getAxis("z");
    const zMarker = document.getElementById("vis-z-carriage");
    const zFill = document.getElementById("vis-z-fill");
    const zTargetMarker = document.getElementById("vis-z-target-marker");
    const zSafeMarker = document.getElementById("vis-z-safe-marker");
    if (zMarker) { zMarker.style.bottom = `${zPct}%`; zMarker.classList.toggle("unknown", !dataState.live); }
    if (zFill) zFill.style.height = dataState.live ? `${zPct}%` : "0%";
    if (zTargetMarker) { zTargetMarker.style.bottom = `${targetZPct}%`; zTargetMarker.classList.toggle("active", targetValid); }
    if (zSafeMarker) zSafeMarker.style.bottom = `${Math.max(0, Math.min(100, safeZ / zMax * 100))}%`;

    const zState = document.getElementById("vis-z-state");
    if (zState) {
      const homed = dataState.live && Boolean(zAxis.is_homed);
      zState.className = `axis-state-badge ${!dataState.live ? "fault" : homed ? "homed" : "not-homed"}`;
      zState.textContent = !dataState.live ? dataState.label : homed ? "HOMED" : "NOT HOMED";
    }

    setText("visual-x-scale", `X+ ${fmt(xMax, 0)} mm`);
    setText("visual-y-scale", `Y+ ${fmt(yMax, 0)} mm`);
    setText("vis-x-value", dataState.live ? fmtPos(xPosition) : "UNKNOWN");
    setText("vis-y-value", dataState.live ? fmtPos(yPosition) : "UNKNOWN");
    setText("vis-z-value", dataState.live ? fmtPos(zPosition) : "UNKNOWN");
    setText("vis-z-max", fmt(zMax, 1));
    setText("vis-target-z", targetValid ? `${dataState.live ? fmtPos(zPosition) : "--"} / ${fmtPos(targetZ)} mm` : "-- / -- mm");
    const zDelta = dataState.live && targetValid ? targetZ - zPosition : NaN;
    setText("vis-z-delta", Number.isFinite(zDelta) ? `${fmtDelta(zDelta).text} / ${Math.abs(zDelta) < .001 ? "IDLE" : zDelta > 0 ? "+" : "−"}` : "-- / UNKNOWN");
    setText("vis-z-steps", dataState.live ? fmtSteps(zAxis.position_steps) : "UNKNOWN");
    setText("vis-z-safe", `${fmtPos(safeZ)} mm`);
    setText("vis-z-limits", dataState.live ? `${zAxis.head_limit ? "ACTIVE" : "CLEAR"} / ${zAxis.tail_limit ? "ACTIVE" : "CLEAR"}` : "UNKNOWN / UNKNOWN");
    setText("vis-z-drive", "NO DATA / NO DATA");

    const stateChip = el("visual-data-state");
    if (stateChip) { stateChip.textContent = dataState.label; stateChip.className = `page-status-chip ${dataState.className}`; }
    setText("visual-state-controller", MS.online ? "ONLINE" : "OFFLINE");
    const visualFault = getStatus().state === "alarm" || activeAlarmCount() > 0;
    setText("visual-state-machine", !dataState.live ? "UNKNOWN" : visualFault ? "ALARM" : motionInhibitReason(true) ? "NOT READY" : "READY");
    setText("visual-state-motion", !dataState.live ? "UNKNOWN" : moving ? String(operation.phase || "MOVING").toUpperCase() : "IDLE");
    setText("visual-state-command", commandName || "NONE");
    setText("visual-state-slot", targetCode ? `SLOT ${String(targetCode).padStart(2, "0")}` : "--");
    setText("visual-state-reason", dataState.live ? (motionInhibitReason(true) || operation.message || dataState.reason) : dataState.reason);

    const commandSelect = el("visual-command-slot");
    if (commandSelect) {
      const codes = Array.from({ length: 30 }, (_, index) => String(index + 1));
      if (commandSelect.options.length !== codes.length) {
        commandSelect.innerHTML = codes.map((code) => `<option value="${code}">Slot ${code}</option>`).join("");
      }
      commandSelect.value = selectedCode;
    }
    const commandStatus = el("visual-command-status");
    if (commandStatus) {
      const commandSlotState = !selectedValid ? (slotStatus(selectedSlot) === "empty" ? "empty" : "invalid") : "ready";
      commandStatus.className = `slot-badge ${commandSlotState}`;
      commandStatus.textContent = commandSlotState.toUpperCase();
    }
    AXES.forEach((axis) => {
      const input = el(`visual-command-${axis}`);
      if (input) input.value = selectedValid ? Number(selectedSlot[`${axis}_mm`]).toFixed(3) : "";
    });
    setText("visual-command-current", dataState.live
      ? `Current: X ${fmtPos(xPosition)} · Y ${fmtPos(yPosition)} · Z ${fmtPos(zPosition)} mm`
      : "Current: UNKNOWN — controller data unavailable");

    setText("vis-target-summary", `SLOT ${String(selectedCode).padStart(2, "0")}`);
    setText("vis-target-coordinates", selectedValid ? `X ${fmtPos(selectedSlot.x_mm)} · Y ${fmtPos(selectedSlot.y_mm)} · Z ${fmtPos(selectedSlot.z_mm)}` : "NOT CONFIGURED");
    const deltas = AXES.map((axis) => Number(selectedSlot[`${axis}_mm`]) - Number(current[`${axis}_mm`]));
    const pulses = AXES.map((axis, index) => Math.round(Math.abs(deltas[index]) * Number(MS.config?.axes?.[axis]?.steps_per_mm || 0)));
    setText("visual-slot-delta", dataState.live && selectedValid ? AXES.map((axis, index) => `${axis.toUpperCase()} ${fmtDelta(deltas[index]).text}`).join(" · ") : "X -- · Y -- · Z --");
    setText("visual-slot-pulses", dataState.live && selectedValid ? AXES.map((axis, index) => `${axis.toUpperCase()} ${fmtSteps(pulses[index])}`).join(" · ") : "X -- · Y -- · Z --");
    setText("visual-slot-validity", !selectedValid ? "INVALID / NOT CONFIGURED" : MS.visualPreview ? "BACKEND VALIDATED" : "NOT VALIDATED");
    setText("visual-slot-estimate", MS.visualPreview ? `${fmtPos(MS.visualPreview.total_distance_mm)} mm / ${fmtTime(MS.visualPreview.duration_s)} s` : "NO DATA");
    setText("visual-slot-homing", !dataState.live ? "UNKNOWN" : allAxesHomed() ? "ALL HOMED" : "HOME ALL AXES REQUIRED");

    const previewState = el("visual-preview-state");
    if (previewState) {
      previewState.textContent = MS.visualPreview ? "VALIDATED" : "NOT VALIDATED";
      previewState.className = MS.visualPreview ? "ok" : "warn";
    }
    const previewDetails = el("visual-trajectory-details");
    if (previewDetails) {
      previewDetails.innerHTML = MS.visualPreview
        ? `<b>${esc(MS.visualPreview.profile || "TRAPEZOIDAL")}</b> · MASTER ${esc(String(MS.visualPreview.master_axis || "--").toUpperCase())} · ${fmtTime(MS.visualPreview.duration_s)} s<br>${Object.values(MS.visualPreview.axes || {}).map((axis) => `${esc(axis.axis.toUpperCase())}: ${fmtPos(axis.distance_mm)} mm · ${fmtSteps(axis.steps)} pulses · ${fmt(axis.pulse_hz, 0)} Hz`).join("<br>")}<br>SOFT LIMIT: PASS · COLLISION ZONE: NO DATA · DRIVE FEEDBACK: NO DATA`
        : "Select a configured slot, then click LOAD AS PREVIEW.";
    }

    const axisReadouts = el("visual-axis-readouts");
    if (axisReadouts) axisReadouts.innerHTML = AXES.map((axis) => {
      const axisData = getAxis(axis);
      const actual = dataState.live ? Number(current[`${axis}_mm`]) : NaN;
      const planned = MS.visualPreview?.axes?.[axis];
      const target = planned?.target_mm ?? (selectedValid ? Number(selectedSlot[`${axis}_mm`]) : NaN);
      const delta = Number.isFinite(actual) && Number.isFinite(target) ? target - actual : NaN;
      return `<article class="visual-axis-row ${axisData.is_homed ? "ok" : "warn"}"><b>${axis.toUpperCase()}</b><div><span>Actual</span><strong>${Number.isFinite(actual) ? fmtPos(actual) : "UNKNOWN"}</strong></div><div><span>Target / Delta</span><strong>${Number.isFinite(target) ? `${fmtPos(target)} / ${fmtDelta(delta).text}` : "NO DATA"}</strong></div><div><span>Pulses</span><strong>${dataState.live ? fmtSteps(axisData.position_steps) : "UNKNOWN"}</strong></div><div><span>Realtime Speed (CALC)</span><strong>${realtimeSpeedText(axis)}</strong></div><div><span>Home / Limits</span><strong>${axisData.is_homed ? "HOMED" : "NOT HOMED"} · ${axisData.head_limit || axisData.tail_limit ? "ACTIVE" : "CLEAR"}</strong></div><div><span>Drive / Error</span><strong>NO DATA</strong></div></article>`;
    }).join("");

    renderVisualSlotEditorV32();
    updateVisualButtons();
  }

  function renderVisualSlotEditorV32(force = false) {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    const derived = slotStatus(slot);
    setText("visual-editor-title", `SLOT ${String(code).padStart(2, "0")}`);
    const badge = el("visual-editor-status");
    if (badge) { badge.className = `slot-badge ${visualSlotIsValid(slot) ? derived : "fault"}`; badge.textContent = visualSlotIsValid(slot) ? derived.toUpperCase() : "INVALID"; }
    if (force || !MS.visualEditorDirty) {
      AXES.forEach((axis) => { el(`visual-slot-${axis}`).value = Number(slot[`${axis}_mm`] || 0); });
      MS.visualEditorDirty = false;
    }
    const editor = el("visual-slot-editor");
    if (editor) editor.classList.toggle("view-only", !MS.visualEditMode);
    setText("visual-edit-mode-state", MS.visualEditMode ? "ENGINEERING EDIT" : "VIEW ONLY");
    AXES.forEach((axis) => { el(`visual-slot-${axis}`).readOnly = !MS.visualEditMode; });
  }

  function configurationNumberInput(axis, field, value, step = "0.1") {
    return `<input class="config-input" type="number" step="${step}" value="${esc(value)}" data-config-axis="${axis}" data-config-field="${field}" aria-label="${axis.toUpperCase()} ${field.replaceAll("_", " ")}">`;
  }

  function renderConfigurationEditor(force = false) {
    if (!MS.config || (MS.configDirty && !force)) return;
    const hardware = MS.config.hardware || {};
    const motorGrid = el("configuration-motor-grid");
    if (motorGrid) motorGrid.innerHTML = AXES.map((axis) => {
      const config = MS.config.axes?.[axis] || {};
      const pulsesPerRev = Number(config.motor_steps_per_rev || 0) * Number(config.driver_microsteps || 0);
      const theoreticalSteps = pulsesPerRev / Math.max(Number(config.lead_screw_pitch_mm || 1), .0001);
      const pulseFrequency = Number(config.steps_per_mm || 0) * Number(config.max_speed_mm_s || 0);
      const scurveSupported = Boolean(MS.payload?.nucleo?.supports_buffered_scurve);
      const scurveSection = axis === "z" ? "" : `<section class="scurve-config" aria-label="Axis ${axis.toUpperCase()} staged S-curve profile">
        <div class="scurve-config-head">
          <div><strong>S-CURVE START / STOP</strong><small>Seven-segment profile · X/Y only</small></div>
          <label class="config-switch scurve-enable" title="${scurveSupported ? "Enable after validation" : "Requires NUCLEO buffered S-curve capability"}">
            <input type="checkbox" data-config-axis="${axis}" data-config-field="scurve_enabled" ${config.scurve_enabled ? "checked" : ""} ${scurveSupported ? "" : "disabled"}>
            <span>${scurveSupported ? "ENABLE" : "STAGED · NOT AVAILABLE"}</span>
          </label>
          <input type="hidden" value="seven_segment_s_curve" data-config-axis="${axis}" data-config-field="scurve_profile_type" data-config-type="string">
        </div>
        <div class="scurve-fields">
          <label><span>Start Speed</span>${configurationNumberInput(axis, "scurve_start_speed_mm_s", config.scurve_start_speed_mm_s ?? 0)}<small>mm/s</small></label>
          <label><span>End Speed</span>${configurationNumberInput(axis, "scurve_end_speed_mm_s", config.scurve_end_speed_mm_s ?? 0)}<small>mm/s</small></label>
          <label><span>Maximum Jerk</span>${configurationNumberInput(axis, "scurve_max_jerk_mm_s3", config.scurve_max_jerk_mm_s3 ?? 100)}<small>mm/s³</small></label>
          <label><span>Control Period</span>${configurationNumberInput(axis, "scurve_control_period_us", config.scurve_control_period_us ?? 1000, "1")}<small>µs</small></label>
        </div>
        <div class="scurve-preview" id="scurve-preview-${axis}" role="status">Profile preview awaiting values.</div>
      </section>`;
      return `<article class="motor-config-card" data-motor-card="${axis}">
        <div class="motor-config-head"><strong>AXIS ${axis.toUpperCase()}</strong><span>${fmt(pulseFrequency / 1000, 2)} kHz MAX</span></div>
        <div class="motor-config-fields">
          <label><span>Motor Steps / Rev</span>${configurationNumberInput(axis, "motor_steps_per_rev", config.motor_steps_per_rev, "1")}</label>
          <label><span>Driver Microsteps</span>${configurationNumberInput(axis, "driver_microsteps", config.driver_microsteps, "1")}</label>
          <label><span>Effective Travel / Rev</span>${configurationNumberInput(axis, "lead_screw_pitch_mm", config.lead_screw_pitch_mm)}<small>mm/rev after gearing</small></label>
          <label><span>Pulse Calibration</span>${configurationNumberInput(axis, "steps_per_mm", config.steps_per_mm)}<small>pulse/mm</small></label>
          <label><span>Maximum Travel</span>${configurationNumberInput(axis, "max_travel_mm", config.max_travel_mm)}<small>mm</small></label>
          <label><span>Maximum Speed</span>${configurationNumberInput(axis, "max_speed_mm_s", config.max_speed_mm_s)}<small>mm/s</small></label>
          <label><span>Default Speed</span>${configurationNumberInput(axis, "default_speed_mm_s", config.default_speed_mm_s)}<small>mm/s</small></label>
          <label><span>Home Position</span>${configurationNumberInput(axis, "home_position_mm", config.home_position_mm ?? 0)}<small>mm after Min sensor</small></label>
          <label><span>Max Pulse Rate</span>${configurationNumberInput(axis, "max_pulse_hz", config.max_pulse_hz ?? 50000, "100")}<small>pulse/s</small></label>
          <label><span>Commissioned Max</span>${configurationNumberInput(axis, "commissioned_max_speed_mm_s", config.commissioned_max_speed_mm_s ?? config.max_speed_mm_s)}<small>mm/s</small></label>
          <label><span>Home Search Speed</span>${configurationNumberInput(axis, "homing_search_speed_mm_s", config.homing_search_speed_mm_s ?? config.default_speed_mm_s)}<small>mm/s</small></label>
          <label><span>Home Latch Speed</span>${configurationNumberInput(axis, "homing_latch_speed_mm_s", config.homing_latch_speed_mm_s ?? 1)}<small>mm/s</small></label>
          <label><span>Home Watchdog</span>${configurationNumberInput(axis, "homing_timeout_s", config.homing_timeout_s ?? 120, "1")}<small>seconds</small></label>
          <label><span>Acceleration</span>${configurationNumberInput(axis, "acceleration", config.acceleration)}<small>mm/s²</small></label>
          <label><span>Deceleration</span>${configurationNumberInput(axis, "deceleration", config.deceleration)}<small>mm/s²</small></label>
          <label><span>Jog Step</span>${configurationNumberInput(axis, "jog_step_mm", config.jog_step_mm)}<small>mm</small></label>
          <label><span>Settle Delay</span>${configurationNumberInput(axis, "settle_delay", config.settle_delay, "0.01")}<small>sec</small></label>
          <label><span>Home Direction</span><select class="config-select" data-config-axis="${axis}" data-config-field="home_direction"><option value="0" ${Number(config.home_direction) === 0 ? "selected" : ""}>LOW / 0</option><option value="1" ${Number(config.home_direction) === 1 ? "selected" : ""}>HIGH / 1</option></select></label>
          <label><span>Forward Direction</span><select class="config-select" data-config-axis="${axis}" data-config-field="forward_direction"><option value="0" ${Number(config.forward_direction) === 0 ? "selected" : ""}>LOW / 0</option><option value="1" ${Number(config.forward_direction) === 1 ? "selected" : ""}>HIGH / 1</option></select></label>
        </div>
        <div class="motor-derived"><span>Theoretical <b id="config-theoretical-${axis}">${fmt(theoreticalSteps, 3)} pulse/mm</b></span><span>Pulse Frequency <b id="config-frequency-${axis}">${fmt(pulseFrequency, 0)} Hz</b></span><span>Pulses / Rev <b id="config-ppr-${axis}">${fmt(pulsesPerRev, 0)}</b></span></div>
        ${scurveSection}
      </article>`;
    }).join("");
    updateConfigurationDerived();
    renderTravelCalibration();

    const isIrivBoard = hardware.board_profile === "IRIV_PiControl_CM4" || Boolean(hardware.iriv_io?.enabled) || MS.payload?.io?.enabled === true;
    if (isIrivBoard) {
      setText("configuration-board-profile", `Profile: IRIV PiControl CM4 · Modbus TCP 10.0.0.10:502 · NUCLEO-F439ZI Motion Engine`);
      const pinEditor = el("configuration-pin-editor");
      if (pinEditor) {
        pinEditor.innerHTML = `
          <section class="pin-editor-group iriv-hw-schedule">
            <div class="pin-editor-title"><strong>Hardware Subsystems Assignment Schedule</strong><span class="schedule-tag ok">HARDWARE LOCKED</span></div>
            <div class="schedule-summary-box">
              <p>Physical I/O and motor step/dir pulse generation are decoupled from Raspberry Pi GPIO and owned by dedicated industrial hardware. Axis motion parameters (speeds, travel, acceleration) above can be tuned and saved to the machine safely.</p>
            </div>
            <div class="schedule-grid">
              <div class="schedule-card">
                <strong>STM32 NUCLEO Motion Controller (PA8, PA9, PA5 via 6-ch NMOS)</strong>
                <ul>
                  <li><b>Axis X:</b> Pulse: <code>PA8 (TIM1_CH1)</code> · Direction: <code>PB0</code> → HBS860H</li>
                  <li><b>Axis Y:</b> Pulse: <code>PA9 (TIM1_CH2)</code> · Direction: <code>PB1</code> → HBS860H</li>
                  <li><b>Axis Z:</b> Pulse: <code>PA5 (TIM2_CH1)</code> · Direction: <code>PB2</code> → DM542</li>
                  <li><b>Watchdog Gate:</b> 500 ms serial heartbeat timeout; disarms on comm loss</li>
                  <li><b>Rate Boundary:</b> 10–1,000 Hz, 1–10,000 pulses single-axis limit</li>
                </ul>
              </div>
              <div class="schedule-card">
                <strong>IRIV IO Modbus TCP Subsystem (10.0.0.10:502 · Unit 255)</strong>
                <ul>
                  <li><b>DI0–DI5:</b> X/Y/Z Min &amp; Max Limit Switches (Active HIGH)</li>
                  <li><b>DI6:</b> Dedicated Z Home switch (Decoupled from Z Min limit)</li>
                  <li><b>DI7–DI9:</b> Product Drop Parking, Drop Sensor &amp; Pickup Sensor</li>
                  <li><b>DI10:</b> E-Stop &amp; KM1 safety relay feedback (NC contact · Active LOW)</li>
                  <li><b>DO0–DO3:</b> Ready, Moving, Alarm &amp; Dispense Relay Coils</li>
                </ul>
              </div>
            </div>
          </section>
        `;
      }
      MS.configDirty = false;
      updateConfigurationState();
      applySetupTab($("[data-setup-tab].active")?.dataset.setupTab || "motor");
      return;
    }

    setText("configuration-board-profile", `Board: ${hardware.board_profile || "--"} · BCM GPIO 0–27`);
    const pinGroups = [
      ["motors", "Motor Outputs", hardware.motors || {}],
      ["digital_inputs", "Safety & Position Sensors", hardware.digital_inputs || {}],
      ["digital_outputs", "Status Outputs", hardware.digital_outputs || {}],
    ];
    const pinEditor = el("configuration-pin-editor");
    if (pinEditor) pinEditor.innerHTML = pinGroups.map(([groupName, title, signals]) => `
      <section class="pin-editor-group">
        <div class="pin-editor-title"><strong>${esc(title)}</strong><span>${Object.keys(signals).length} SIGNALS</span></div>
        <div class="pin-editor-table">
          ${groupName === "motors" ? Object.entries(signals).flatMap(([axis, motor]) => [
            `<div class="pin-editor-row"><b>${esc(axis.toUpperCase())} STEP / PULSE</b><span>MOTOR OUTPUT</span><label>GPIO <input class="pin-input" type="number" min="0" max="27" step="1" value="${esc(motor.step_pin)}" data-pin-group="motors" data-pin-name="${esc(axis)}" data-pin-field="step_pin"></label><label class="config-switch"><input type="checkbox" ${motor.active_high ? "checked" : ""} data-pin-group="motors" data-pin-name="${esc(axis)}" data-pin-field="active_high"><span>STEP/DIR HIGH</span></label></div>`,
            `<div class="pin-editor-row"><b>${esc(axis.toUpperCase())} DIRECTION</b><span>MOTOR OUTPUT</span><label>GPIO <input class="pin-input" type="number" min="0" max="27" step="1" value="${esc(motor.dir_pin)}" data-pin-group="motors" data-pin-name="${esc(axis)}" data-pin-field="dir_pin"></label><span class="pin-shared-logic">USES STEP/DIR LOGIC</span></div>`,
            `<div class="pin-editor-row"><b>${esc(axis.toUpperCase())} ENABLE</b><span>MOTOR OUTPUT</span><label>GPIO <input class="pin-input" type="number" min="0" max="27" step="1" value="${esc(motor.enable_pin)}" data-pin-group="motors" data-pin-name="${esc(axis)}" data-pin-field="enable_pin"></label><label class="config-switch"><input type="checkbox" ${motor.enable_active_high ?? motor.active_high ? "checked" : ""} data-pin-group="motors" data-pin-name="${esc(axis)}" data-pin-field="enable_active_high"><span>ENABLE HIGH</span></label></div>`,
          ]).join("") : ""}
          ${groupName === "digital_inputs" ? Object.entries(signals).map(([name, input]) => `<div class="pin-editor-row"><b>${esc(name.replaceAll("_", " ").toUpperCase())}</b><span>${name.includes("lim_") || name.includes("home_") ? "POSITION SENSOR" : "SAFETY INPUT"}</span><label>GPIO <input class="pin-input" type="number" min="0" max="27" step="1" value="${esc(input.pin)}" data-pin-group="digital_inputs" data-pin-name="${esc(name)}" data-pin-field="pin"></label><label class="config-switch"><input type="checkbox" ${input.pull_up ? "checked" : ""} data-pin-group="digital_inputs" data-pin-name="${esc(name)}" data-pin-field="pull_up"><span>PULL-UP</span></label><label class="config-switch"><input type="checkbox" ${input.active_high ? "checked" : ""} data-pin-group="digital_inputs" data-pin-name="${esc(name)}" data-pin-field="active_high"><span>ACTIVE HIGH</span></label></div>`).join("") : ""}
          ${groupName === "digital_outputs" ? Object.entries(signals).map(([name, output]) => `<div class="pin-editor-row"><b>${esc(name.replaceAll("_", " ").toUpperCase())}</b><span>DIGITAL OUTPUT</span><label>GPIO <input class="pin-input" type="number" min="0" max="27" step="1" value="${esc(output.pin)}" data-pin-group="digital_outputs" data-pin-name="${esc(name)}" data-pin-field="pin"></label><label class="config-switch"><input type="checkbox" ${output.initial_value ? "checked" : ""} data-pin-group="digital_outputs" data-pin-name="${esc(name)}" data-pin-field="initial_value"><span>INITIAL ON</span></label><label class="config-switch"><input type="checkbox" ${output.active_high ? "checked" : ""} data-pin-group="digital_outputs" data-pin-name="${esc(name)}" data-pin-field="active_high"><span>ACTIVE HIGH</span></label></div>`).join("") : ""}
        </div>
      </section>`).join("");

    MS.configDirty = false;
    updateConfigurationState();
  }

  function updateConfigurationDerived() {
    AXES.forEach((axis) => {
      const value = (field) => Number(document.querySelector(`[data-config-axis="${axis}"][data-config-field="${field}"]`)?.value || 0);
      const pulsesPerRev = value("motor_steps_per_rev") * value("driver_microsteps");
      const theoretical = pulsesPerRev / Math.max(value("lead_screw_pitch_mm"), .0001);
      const frequency = value("steps_per_mm") * value("max_speed_mm_s");
      setText(`config-theoretical-${axis}`, `${fmt(theoretical, 3)} pulse/mm`);
      setText(`config-frequency-${axis}`, `${fmt(frequency, 0)} Hz`);
      setText(`config-ppr-${axis}`, fmt(pulsesPerRev, 0));
      const card = document.querySelector(`[data-motor-card="${axis}"]`);
      if (card) card.classList.toggle("fault", frequency > 50000);
      if (axis !== "z") {
        const jerk = value("scurve_max_jerk_mm_s3");
        const acceleration = value("acceleration");
        const periodUs = value("scurve_control_period_us");
        const transitionMs = jerk > 0 ? (acceleration / jerk) * 1000 : Number.NaN;
        const valid = jerk > 0 && Number.isInteger(periodUs) && periodUs >= 100 && periodUs <= 10000;
        setText(`scurve-preview-${axis}`, valid
          ? `Preview · jerk transition ${fmt(transitionMs, 1)} ms · control ${(periodUs / 1000).toFixed(3)} ms · disabled until capability handshake`
          : "Invalid profile · jerk must be > 0 and control period must be 100–10,000 µs.");
      }
    });
  }

  function updateConfigurationState(message = "") {
    const restartRequired = Boolean(MS.config?.restart_required || MS.payload?.safety?.configuration_restart_required);
    const statusNode = el("configuration-save-status");
    if (statusNode) {
      statusNode.textContent = MS.configSaving ? "SAVING" : MS.configDirty ? "UNSAVED" : restartRequired ? "RESTART REQUIRED" : "SAVED";
      statusNode.className = `page-status-chip ${MS.configDirty || restartRequired ? "warn" : "ok"}`;
    }
    el("configuration-save").disabled = !MS.configDirty || MS.configSaving || Boolean(MS.payload?.busy);
    el("configuration-reset").disabled = !MS.configDirty || MS.configSaving;
    el("configuration-apply").disabled = !restartRequired || MS.configSaving || Boolean(MS.payload?.busy);
    const validation = el("configuration-validation");
    if (validation) {
      validation.textContent = message || (MS.configDirty
        ? "Unsaved configuration — SAVE TO PI validates GPIO assignments and pulse limits."
        : restartRequired
          ? "Configuration saved on Raspberry Pi. Motion is locked until APPLY & RESTART completes."
          : "Configuration active. Changing pulse or GPIO values does not move the machine.");
      validation.className = `configuration-validation ${MS.configDirty || restartRequired ? "warn" : "ok"}`;
    }
  }

  function collectConfigurationPayload() {
    const axes = {};
    AXES.forEach((axis) => {
      axes[axis] = {};
      document.querySelectorAll(`[data-config-axis="${axis}"]`).forEach((input) => {
        axes[axis][input.dataset.configField] = input.dataset.configType === "string"
          ? input.value
          : input.type === "checkbox"
            ? input.checked
            : Number(input.value);
      });
      const travelCard = document.querySelector(`.travel-calibration-card[data-travel-axis="${axis}"]`);
      if (travelCard) {
        const travelValue = (field) => Number(travelCard.querySelector(`[data-travel-field="${field}"]`)?.value);
        axes[axis].nominal_travel_mm = travelValue("nominal");
        axes[axis].measured_travel_mm = travelValue("measured");
        axes[axis].travel_safety_margin_mm = travelValue("margin");
      }
    });
    // IRIV owns physical I/O, so its GPIO editor is intentionally not rendered.
    // Preserve the installed hardware config and overlay only browser-editable fields.
    const hardware = JSON.parse(JSON.stringify(MS.config?.hardware || {}));
    hardware.motors ||= {};
    hardware.digital_inputs ||= {};
    hardware.digital_outputs ||= {};
    document.querySelectorAll("[data-pin-group]").forEach((input) => {
      const group = input.dataset.pinGroup;
      const name = input.dataset.pinName;
      const field = input.dataset.pinField;
      hardware[group][name] ||= {};
      hardware[group][name][field] = input.type === "checkbox" ? input.checked : Number(input.value);
    });
    return { axes, hardware };
  }

  async function saveControllerConfiguration() {
    if (!MS.configDirty || MS.configSaving) return;
    if (!window.confirm("Save motor pulse and GPIO configuration to Raspberry Pi?\nMotion will be locked until APPLY & RESTART.")) return;
    MS.configSaving = true;
    updateConfigurationState("Validating and saving configuration to Raspberry Pi...");
    try {
      const data = await apiCall("/api/config", "PUT", collectConfigurationPayload(), 12000);
      MS.config = data.config;
      MS.configDirty = false;
      renderConfigurationEditor(true);
      updateConfigurationState("Configuration saved. Review values, then press APPLY & RESTART.");
      toast("Configuration saved to Raspberry Pi — restart required.", "ok");
      log("Motor pulse and GPIO configuration saved", "info", "CONFIG");
      await refresh();
    } catch (err) {
      updateConfigurationState(`SAVE REJECTED — ${humanizeError(err.message)}`);
      toast(humanizeError(err.message), "error");
      log(`Configuration save rejected: ${err.message}`, "error", "CONFIG");
    } finally {
      MS.configSaving = false;
      updateConfigurationState();
    }
  }

  async function applyControllerConfiguration() {
    if (!window.confirm("Apply configuration and restart the Raspberry Pi controller service now?\nAll axes must be homed again after restart.")) return;
    MS.configSaving = true;
    updateConfigurationState("Controller restart requested. Waiting for API...");
    try {
      await apiCall("/api/config/apply", "POST", {}, 5000);
      toast("Controller restarting — please wait.", "ok");
      let activeConfig = null;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        try {
          const config = await apiCall("/api/config", "GET", undefined, 1500);
          if (config.axes && config.hardware && config.restart_required === false) {
            activeConfig = config;
            break;
          }
        } catch { /* Controller is restarting. */ }
      }
      if (!activeConfig) throw new Error("Controller did not reload the saved configuration within 30 seconds");
      MS.config = activeConfig;
      MS.configSaving = false;
      await refresh();
      renderConfigurationEditor(true);
      toast("Configuration applied — home all axes before motion.", "ok");
      log("Controller restarted with saved configuration", "info", "CONFIG");
    } catch (err) {
      MS.configSaving = false;
      updateConfigurationState(`RESTART STATUS — ${humanizeError(err.message)}`);
      toast(humanizeError(err.message), "error");
    }
  }

  function updateVisualButtons() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    const validSlot = visualSlotIsValid(slot) && slotStatus(slot) === "ready";
    const idle = MS.online && !MS.pending && !MS.payload?.busy;
    el("visual-load-preview").disabled = !validSlot || !idle;
    el("visual-home-all").disabled = !canHomeAxis();
    el("visual-send-motion").disabled = !validSlot;
    const gotoButton = el("visual-slot-goto");
    gotoButton.disabled = !validSlot || !idle || MS.visualGotoPending || Boolean(motionInhibitReason(true));
    gotoButton.textContent = MS.visualGotoPending || MS.payload?.busy ? "MOVING..." : "GOTO SLOT";
    el("visual-edit-enable").disabled = !idle || MS.visualEditMode;
    el("visual-slot-load-current").disabled = !MS.visualEditMode || !idle || !allAxesHomed();
    el("visual-slot-save").disabled = !MS.visualEditMode || !idle || !MS.visualEditorDirty;
    el("visual-edit-cancel").disabled = !MS.visualEditMode;
  }

  async function previewVisualSlot() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    if (!visualSlotIsValid(slot) || slotStatus(slot) !== "ready") return;
    try {
      const data = await apiCall("/api/motion/preview", "POST", {
        x_mm: Number(slot.x_mm), y_mm: Number(slot.y_mm), z_mm: Number(slot.z_mm),
        speed_mm_s: effectiveMotionSpeed(),
      });
      MS.visualPreview = data.plan;
      toast(`Slot ${code} trajectory validated for preview only.`, "ok");
      log(`Visualization preview validated for slot ${code}`, "info", "MOTION");
    } catch (err) {
      MS.visualPreview = null;
      toast(humanizeError(err.message), "error");
      log(`Visualization preview rejected: ${humanizeError(err.message)}`, "error", "INTERLOCK");
    }
    renderVisualizationV32();
  }

  function loadVisualSlotTarget() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    if (!visualSlotIsValid(slot) || slotStatus(slot) !== "ready") {
      toast(`Slot ${code} has no valid saved position.`, "error");
      return;
    }
    AXES.forEach((axis) => { el(`move-${axis}`).value = Number(slot[`${axis}_mm`]).toFixed(3); });
    invalidateMotionWorkflow(`Target loaded from Visualization — Slot ${code}.`);
    toast(`Slot ${code} target loaded. Validate or press GOTO SLOT.`, "ok");
    log(`Visualization target loaded: slot ${code}`, "info", "MOTION");
  }

  async function gotoVisualSlot() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    if (!visualSlotIsValid(slot) || slotStatus(slot) !== "ready") {
      toast(`Slot ${code} has no valid saved position.`, "error");
      return;
    }
    const inhibitReason = motionInhibitReason(true);
    if (inhibitReason) {
      toast(inhibitReason, "error");
      log(`Visualization GOTO Slot ${code} blocked: ${inhibitReason}`, "error", "INTERLOCK");
      return;
    }

    const payload = {
      x_mm: Number(slot.x_mm),
      y_mm: Number(slot.y_mm),
      z_mm: Number(slot.z_mm),
      speed_mm_s: effectiveMotionSpeed(),
    };

    MS.visualGotoPending = true;
    updateVisualButtons();
    try {
      const preview = await apiCall("/api/motion/preview", "POST", payload);
      MS.visualPreview = preview.plan;
      renderVisualizationV32();
      toast(`Slot ${code} validated — movement starting.`, "ok");

      const result = await command(slotMotionLabel(code), slotMotionEndpoint(code), {
        speed_mm_s: payload.speed_mm_s,
      }, {
        requireHome: true,
        timeoutMs: 600000,
      });
      if (result) {
        MS.visualPreview = null;
        log(`Visualization GOTO Slot ${code} completed`, "info", "MOTION");
      }
    } catch (err) {
      const message = humanizeError(err.message);
      toast(message, "error");
      log(`Visualization GOTO Slot ${code} rejected: ${message}`, "error", "INTERLOCK");
    } finally {
      MS.visualGotoPending = false;
      renderVisualizationV32();
    }
  }

  function sendVisualTargetToMotion() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    if (!visualSlotIsValid(slot) || slotStatus(slot) !== "ready") return;
    AXES.forEach((axis) => { el(`move-${axis}`).value = Number(slot[`${axis}_mm`]).toFixed(3); });
    invalidateMotionWorkflow(`Target loaded from Visualization — Slot ${code}.`);
    switchWorkspace("motion");
    toast(`Slot ${code} loaded. Complete VALIDATE → PREVIEW → ARM → EXECUTE.`, "ok");
    log(`Target loaded from Visualization: slot ${code}`, "info", "MOTION");
  }

  function setVisualEditMode(enabled) {
    const idle = MS.online && !MS.pending && !MS.payload?.busy;
    if (enabled && !idle) { toast("Edit Mode requires controller online and machine idle.", "error"); return; }
    MS.visualEditMode = enabled;
    MS.visualOriginalSlot = enabled ? { ...(MS.slots[MS.visualTargetSlot || MS.selectedSlotCode || "1"] || {}) } : null;
    MS.visualEditorDirty = false;
    renderVisualSlotEditorV32(true);
    setText("visual-edit-comparison", enabled ? "Engineering Edit Mode enabled. Review Old → New values before saving." : "Enable Engineering Edit Mode to modify stored coordinates. Saving never moves the machine.");
    updateVisualButtons();
  }

  async function saveVisualSlotV32() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const values = visualSlotValues();
    const candidate = { ...values };
    if (!visualSlotIsValid(candidate)) { toast("Position is outside configured soft limits.", "error"); return; }
    const duplicate = Object.entries(MS.slots).find(([otherCode, slot]) => otherCode !== code && AXES.every((axis) => Math.abs(Number(slot[`${axis}_mm`]) - Number(values[`${axis}_mm`])) < 0.001));
    if (duplicate) { toast(`Position duplicates Slot ${duplicate[0]}.`, "error"); return; }
    const original = MS.visualOriginalSlot || MS.slots[code] || {};
    const comparison = AXES.map((axis) => `${axis.toUpperCase()} ${fmtPos(original[`${axis}_mm`])} → ${fmtPos(values[`${axis}_mm`])}`).join(" · ");
    setText("visual-edit-comparison", comparison);
    if (!window.confirm(`Save Slot ${code} position?\n${comparison}\nThis does not move the machine.`)) return;
    const payload = slotPayloadFromValues(code, values);
    if (!payload) return;
    const result = await command(`Save visualization slot ${code}`, `/api/slots/${code}`, payload, { isStop: true, noCheck: true });
    if (result) {
      log(`Visualization slot ${code} saved: ${comparison}`, "info", "CONFIG");
      setVisualEditMode(false);
      renderVisualizationV32();
    }
  }

  function trackDashboardOperation(payload) {
    const busy = Boolean(payload?.busy);
    const commandName = payload?.active_command || payload?.operation?.phase || "";
    if (busy && (!MS.dashboardWasBusy || MS.dashboardTrackedCommand !== commandName)) {
      MS.dashboardOperationStartedAt = Date.now();
      MS.dashboardTrackedCommand = commandName;
    }
    if (!busy) {
      MS.dashboardOperationStartedAt = null;
      MS.dashboardTrackedCommand = "";
    }
    MS.dashboardWasBusy = busy;
  }

  function dashboardAlarmAction(channel) {
    if (channel.code === "CTRL") return "Check Pi power, network and web service";
    if (channel.code === "ESTOP") return "Release physical E-Stop, then reset alarms";
    if (channel.code === "STOP") return "Press Reset Alarms and verify safety";
    if (channel.code.endsWith("-HOME")) return `Home ${channel.code[0]} axis before motion`;
    if (channel.code.endsWith("-MIN") || channel.code.endsWith("-MAX")) return "Inspect limit sensor and axis position";
    return "Open Alarm Management for diagnosis";
  }

  function renderDashboard() {
    const status = getStatus();
    const operation = getOperation();
    const alarmCount = activeAlarmCount();
    const homed = allAxesHomed();
    const safetyClear = MS.online && !status.estop && !MS.payload?.safety?.stop_requested && alarmCount === 0;
    const ready = safetyClear && homed && !MS.payload?.busy;
    const configuredSlots = Object.values(MS.slots || {}).filter((slot) => slotStatus(slot) === "ready").length;
    const summary = !MS.online ? "OFFLINE" : (alarmCount ? "ALARM" : (ready ? "READY" : "NOT READY"));
    const summaryClass = !MS.online || alarmCount ? "fault" : (ready ? "ok" : "warn");

    setText("dashboard-readiness-summary", summary);
    setClass("dashboard-readiness-summary", summaryClass);
    setText("dashboard-state-detail", operation.message || motionInhibitReason(true) || "Controller ready");
    setText("dashboard-slots", `${configuredSlots} READY`);
    const dashboardHealth = el("dashboard-health");
    if (dashboardHealth) {
      dashboardHealth.textContent = summary === "READY" ? "SYSTEM READY" : summary;
      dashboardHealth.className = `page-status-chip ${summaryClass === "warn" ? "" : summaryClass}`;
    }

    const readinessItems = [
      ["Controller", MS.online ? "ONLINE" : "OFFLINE", MS.online ? "ok" : "fault"],
      ["E-Stop", status.estop ? "ACTIVE" : (MS.online ? "CLEAR" : "UNKNOWN"), status.estop || !MS.online ? "fault" : "ok"],
      ["Interlock", safetyClear ? "ENABLED" : "INHIBITED", safetyClear ? "ok" : "warn"],
      ...AXES.map((axis) => [`${axis.toUpperCase()} Home`, getAxis(axis).is_homed ? "HOMED" : "NOT HOMED", getAxis(axis).is_homed ? "ok" : "warn"]),
      ...AXES.map((axis) => {
        const data = getAxis(axis);
        const active = data.head_limit || data.tail_limit;
        return [`${axis.toUpperCase()} Limits`, active ? `${data.head_limit ? "MIN" : "MAX"} ACTIVE` : "CLEAR", active ? "fault" : "ok"];
      }),
      ["Alarms", String(alarmCount), alarmCount ? "fault" : "ok"],
    ];
    const readinessGrid = el("dashboard-readiness-grid");
    if (readinessGrid) readinessGrid.innerHTML = readinessItems.map(([label, value, stateClass]) => `
      <div class="dashboard-readiness-item ${stateClass}"><span>${esc(label)}</span><strong><i></i>${esc(value)}</strong></div>
    `).join("");

    const commandName = MS.payload?.active_command || "";
    const targetCode = commandName.match(/(?:goto_slot_|dispense_?)(\d+)/)?.[1] || "";
    const targetSlot = targetCode ? MS.slots[targetCode] : null;
    const busy = Boolean(MS.payload?.busy);
    const phase = MS.online ? String(operation.phase || (busy ? "running" : "ready")).toUpperCase() : "UNKNOWN";
    const motionState = !MS.online ? "OFFLINE" : (status.estop ? "STOPPED" : (busy ? (commandName.startsWith("home") ? "HOMING" : commandName.includes("dispense") ? "DISPENSING" : "MOVING") : "IDLE"));
    const elapsed = busy && MS.dashboardOperationStartedAt ? Date.now() - MS.dashboardOperationStartedAt : NaN;
    setText("dashboard-command", commandName || "NONE");
    setText("dashboard-operation-phase", phase);
    setText("dashboard-active-axis", operation.active_axis ? operation.active_axis.toUpperCase() : "--");
    setText("dashboard-target-slot", targetCode ? `SLOT ${String(targetCode).padStart(2, "0")}` : "--");
    setText("dashboard-start-time", MS.dashboardOperationStartedAt ? new Date(MS.dashboardOperationStartedAt).toLocaleTimeString() : "--:--:--");
    setText("dashboard-elapsed-time", Number.isFinite(elapsed) ? fmtDuration(elapsed) : "--");
    setText("dashboard-remaining-time", "NO DATA");
    setText("dashboard-operation-message", MS.online ? (operation.message || "Controller ready") : "Controller API unavailable");
    setText("dashboard-motion-state", motionState);
    setClass("dashboard-motion-state", busy ? "active" : (motionState === "OFFLINE" || motionState === "STOPPED" ? "fault" : "ok"));
    const progressBar = el("dashboard-progress-bar");
    if (progressBar) progressBar.className = busy ? "indeterminate" : "";

    const dashboardAxes = el("dashboard-axis-grid");
    if (dashboardAxes) dashboardAxes.innerHTML = AXES.map((axis) => {
      const data = getAxis(axis);
      const actual = Number(data.position_mm || 0);
      const target = targetSlot ? Number(targetSlot[`${axis}_mm`]) : NaN;
      const delta = Number.isFinite(target) ? target - actual : NaN;
      const direction = !busy || !Number.isFinite(delta) || Math.abs(delta) < 0.001 ? "IDLE" : (delta > 0 ? `${axis.toUpperCase()}+` : `${axis.toUpperCase()}−`);
      const limitState = data.head_limit ? "MIN ACTIVE" : (data.tail_limit ? "MAX ACTIVE" : "CLEAR");
      const axisState = !MS.online ? "UNKNOWN" : (data.head_limit || data.tail_limit ? "FAULT" : (data.is_homed ? "HOMED" : "NOT HOMED"));
      return `<article class="dashboard-axis-row ${data.head_limit || data.tail_limit ? "fault" : (data.is_homed ? "ok" : "warn")}">
        <div class="dashboard-axis-name"><b>${axis.toUpperCase()}</b><span>${esc(axisState)}</span></div>
        <div><span>Actual</span><strong>${MS.online ? fmtPos(actual) : "---"}<small> mm</small></strong></div>
        <div><span>Target</span><strong>${Number.isFinite(target) ? fmtPos(target) : "---"}<small> mm</small></strong></div>
        <div><span>Delta</span><strong>${Number.isFinite(delta) ? fmtDelta(delta).text : "---"}<small> mm</small></strong></div>
        <div><span>Pulse</span><strong>${MS.online ? fmtSteps(data.position_steps) : "---"}</strong></div>
        <div><span>Direction</span><strong>${esc(direction)}</strong></div>
        <div><span>Limits</span><strong>${esc(limitState)}</strong></div>
        <div class="dashboard-axis-speed"><span>Cmd / Eff.</span><strong>${fmtSpd(axisSpeed(axis))} / ${fmtSpd(effectiveMotionSpeed([axis]))}<small> mm/s</small></strong></div>
      </article>`;
    }).join("");

    const selectedCode = MS.dashboardSelectedSlot || "1";
    const selectedSlot = MS.slots[selectedCode] || {};
    setText("dashboard-selected-slot", `SLOT ${String(selectedCode).padStart(2, "0")}`);
    setText("dashboard-selected-coordinates", slotStatus(selectedSlot) === "ready"
      ? `X ${fmtPos(selectedSlot.x_mm)} · Y ${fmtPos(selectedSlot.y_mm)} · Z ${fmtPos(selectedSlot.z_mm)} mm`
      : "POSITION NOT CONFIGURED");
    const currentPosition = status.current_position || {};
    const nearestCode = Object.entries(MS.slots || {}).find(([, slot]) => AXES.every((axis) => Math.abs(Number(slot[`${axis}_mm`] || 0) - Number(currentPosition[`${axis}_mm`] || 0)) < 0.05))?.[0];
    const slotGrid = el("dashboard-slot-grid");
    if (slotGrid) slotGrid.innerHTML = Array.from({ length: 30 }, (_, index) => {
      const code = String(index + 1);
      const slot = MS.slots[code] || {};
      const configured = slotStatus(slot) === "ready";
      const invalid = configured && AXES.some((axis) => {
        const value = Number(slot[`${axis}_mm`]);
        const max = Number(MS.config?.axes?.[axis]?.max_travel_mm ?? Infinity);
        return !Number.isFinite(value) || value < 0 || value > max;
      });
      const classes = ["dashboard-slot", configured ? "ready" : "empty"];
      if (invalid) classes.push("fault");
      if (code === selectedCode) classes.push("selected");
      if (code === targetCode && busy) classes.push("moving");
      if (code === nearestCode) classes.push("at-position");
      return `<button type="button" class="${classes.join(" ")}" data-dashboard-slot="${code}" aria-label="Select slot ${code} details"><b>${String(index + 1).padStart(2, "0")}</b><small>${invalid ? "INVALID" : configured ? "READY" : "EMPTY"}</small></button>`;
    }).join("");

    const activeChannels = alarmChannels().filter((channel) => channel.active).slice(0, 5);
    setText("dashboard-alarm-count", String(activeChannels.length));
    const alarmList = el("dashboard-alarm-list");
    const alarmTime = MS.payload?.timestamp ? new Date(MS.payload.timestamp).toLocaleTimeString() : "--:--:--";
    if (alarmList) alarmList.innerHTML = activeChannels.length ? activeChannels.map((channel) => `
      <article class="dashboard-alarm-item ${channel.level}">
        <i></i><div><strong>${esc(channel.code)} · ${esc(channel.label)}</strong><span>${esc(channel.detail)}</span><small>${esc(alarmTime)} · ${esc(dashboardAlarmAction(channel))}</small></div>
      </article>`).join("") : `<div class="dashboard-empty-state ok">✓ NO ACTIVE ALARMS</div>`;

    const eventList = el("dashboard-event-list");
    if (eventList) eventList.innerHTML = MS.events.slice(0, 8).map((event) => `
      <li class="${esc(event.level)}"><time>${event.at.toLocaleTimeString()}</time><b>${esc(event.subsystem)}</b><span>${esc(event.message)}</span></li>
    `).join("") || `<li class="empty"><span>NO EVENTS RECORDED</span></li>`;

    renderDashboardIOSummary();
  }

  function motorTestFrequencyCap() {
    const reported = Number(motorTestState().max_frequency_hz);
    if (Number.isFinite(reported) && reported >= 10) return reported;
    return Number(MS.payload?.nucleo?.protocol || 1) >= 3 ? 50000 : 1000;
  }

  function renderTravelCalibration() {
    const grid = el("travel-calibration-grid");
    if (!grid || !MS.config) return;
    grid.innerHTML = AXES.map((axis) => {
      const cfg = MS.config.axes?.[axis] || {};
      const nominal = Number(cfg.nominal_travel_mm ?? (axis === "z" ? 180 : 1800));
      const measured = Number(cfg.measured_travel_mm ?? nominal);
      const margin = Number(cfg.travel_safety_margin_mm ?? (axis === "z" ? 3 : 10));
      const usable = Math.max(0, measured - margin);
      const drive = cfg.drive_type || (axis === "z" ? "timing_belt" : "lead_screw");
      return `<article class="travel-calibration-card" data-travel-axis="${axis}">
        <div class="motor-config-head"><strong>AXIS ${axis.toUpperCase()}</strong><span>${drive === "timing_belt" ? "TIMING BELT" : "LEAD SCREW"}</span></div>
        <div class="travel-source-note">${axis === "z" ? "GTD-A001 · 2GT belt · requested nominal stroke 180 mm" : `MISUMI MTSRL25-1800 · physical screw pitch 5 mm · calibrated effective travel ${Number(cfg.lead_screw_pitch_mm || 24.7273).toFixed(4)} mm/motor rev`}</div>
        <label class="travel-direct-label"><span><strong>Maximum Travel</strong></span>${configurationNumberInput(axis, "max_travel_mm", cfg.max_travel_mm)}<small>mm — editable directly; Save and Apply are required</small></label>
        <div class="travel-calibration-fields">
          <label><span>Nominal / Spec</span><input class="config-input" type="number" min="0.1" step="0.1" value="${nominal}" data-travel-field="nominal"><small>mm</small></label>
          <label><span>Measured Min → Max</span><input class="config-input" type="number" min="0.1" step="0.1" value="${measured}" data-travel-field="measured"><small>mm measured by operator</small></label>
          <label><span>Safety Margin</span><input class="config-input" type="number" min="0" step="0.1" value="${margin}" data-travel-field="margin"><small>mm removed before Max</small></label>
        </div>
        <div class="travel-result"><span>Recommended software travel</span><strong data-travel-result>${fmt(usable, 3)} mm</strong></div>
        <button type="button" class="btn-secondary" data-apply-travel="${axis}">USE MEASURED − MARGIN</button>
      </article>`;
    }).join("");
  }

  function updateTravelCard(card) {
    const measured = Number(card.querySelector('[data-travel-field="measured"]')?.value);
    const margin = Number(card.querySelector('[data-travel-field="margin"]')?.value);
    const result = Number.isFinite(measured) && Number.isFinite(margin) ? measured - margin : NaN;
    const resultNode = card.querySelector("[data-travel-result]");
    if (resultNode) resultNode.textContent = Number.isFinite(result) && result > 0 ? `${fmt(result, 3)} mm` : "INVALID";
    card.classList.toggle("fault", !Number.isFinite(result) || result <= 0);
    return result;
  }

  function motorTestParameters() {
    const freqVal = Number(el("motor-test-frequency")?.value || 400);
    const frequencyCap = motorTestFrequencyCap();
    return {
      axis: el("motor-test-axis")?.value || "x",
      direction: el("motor-test-direction")?.value || "forward",
      frequency: Math.max(10, Math.min(frequencyCap, Number.isFinite(freqVal) ? freqVal : 400)),
      pulses: Number(el("motor-test-pulses")?.value || 200),
      stepsPerRev: Number(el("motor-test-steps-rev")?.value || 200),
      microsteps: Number(el("motor-test-microsteps")?.value || 2),
      pitch: Number(el("motor-test-pitch")?.value || 5),
      ignoreLimits: el("motor-test-bypass-limits") ? el("motor-test-bypass-limits").checked : false,
    };
  }

  function loadMotorTestAxisConfig() {
    const axis = el("motor-test-axis")?.value || "x";
    const config = MS.config?.axes?.[axis];
    if (!config) return;
    el("motor-test-steps-rev").value = Number(config.motor_steps_per_rev || 200);
    el("motor-test-microsteps").value = Number(config.driver_microsteps || 2);
    el("motor-test-pitch").value = Number(config.lead_screw_pitch_mm || 5);
    const freqEl = el("motor-test-frequency");
    if (freqEl && (!freqEl.value || Number(freqEl.value) > motorTestFrequencyCap() || Number(freqEl.value) < 10)) {
      freqEl.value = "400";
    }
    updateMotorTestCalculations();
  }

  function updateMotorTestCalculations() {
    if (!document.getElementById("motor-test-start")) return;
    const parameters = motorTestParameters();
    const ppr = parameters.stepsPerRev * parameters.microsteps;
    const ppm = ppr / parameters.pitch;
    const duration = parameters.pulses / parameters.frequency;
    const distance = parameters.pulses / ppm;
    const rpm = parameters.frequency * 60 / ppr;
    const rawFreq = Number(el("motor-test-frequency")?.value);
    const frequencyCap = motorTestFrequencyCap();
    const jogValid = Number.isFinite(rawFreq) && rawFreq >= 10 && rawFreq <= frequencyCap
      && Number.isFinite(parameters.stepsPerRev) && parameters.stepsPerRev > 0
      && Number.isFinite(parameters.microsteps) && parameters.microsteps > 0
      && Number.isFinite(parameters.pitch) && parameters.pitch > 0;
    const valid = jogValid
      && Number.isInteger(parameters.pulses) && parameters.pulses >= 1 && parameters.pulses <= 10000
      && Number.isFinite(duration) && duration <= 10;
    setText("motor-test-ppr", Number.isFinite(ppr) ? Math.round(ppr).toLocaleString() : "INVALID");
    setText("motor-test-ppm", Number.isFinite(ppm) ? fmt(ppm, 3) : "INVALID");
    const durationField = el("motor-test-duration");
    if (durationField) durationField.value = Number.isFinite(duration) ? fmt(duration, 3) : "INVALID";
    setText("motor-test-distance", Number.isFinite(distance) ? `${fmt(distance, 3)} mm` : "INVALID");
    setText("motor-test-rpm", Number.isFinite(rpm) ? `${fmt(rpm, 2)} rpm` : "INVALID");
    const armed = Boolean(motorTestState().armed);
    const ready = armed && MS.online && !MS.pending
      && !Boolean(MS.payload?.busy) && !Boolean(getStatus().estop);
    el("motor-test-start").disabled = !valid || !ready || MS.motorTestJog.active;
    $$("[data-motor-test-jog]").forEach((button) => {
      button.disabled = !jogValid || (MS.motorTestJog.active ? button !== MS.motorTestJog.button : !ready);
    });
    // Enable/disable Goto Limit buttons
    $$("[data-goto-axis]").forEach((button) => {
      const axis  = button.dataset.gotoAxis?.toUpperCase();
      const limit = button.dataset.gotoLimit;
      if (motorTestGoto.active) {
        if (button === motorTestGoto.button) {
          button.disabled = false;
          button.textContent = "\u25A0 ABORT GOTO";
        } else {
          button.disabled = true;
        }
      } else {
        button.disabled = !ready || MS.motorTestJog.active;
        if (axis && limit) {
          button.textContent = limit === "min" ? "\u27EA " + axis + " MIN" : axis + " MAX \u27EB";
        }
      }
    });
    const gotoProfileEl = el("motor-test-goto-profile");
    if (gotoProfileEl) {
      gotoProfileEl.textContent = ready
        ? fmt(parameters.frequency, 0) + " Hz \xB7 Full-stroke"
        : (armed ? "WAITING \u2014 system busy" : "ARM first to enable");
    }
    setText(
      "motor-test-jog-profile",
      jogValid ? `HOLD TO RUN · ${fmt(parameters.frequency, 0)} Hz (STM32)` : "INVALID PROFILE",
    );
    if (Number.isFinite(rawFreq) && rawFreq > frequencyCap) {
      setText("motor-test-result", `STM32 protocol frequency limit is ${frequencyCap.toLocaleString()} Hz.`);
    } else if (!valid) {
      setText("motor-test-result", `INVALID PROFILE — frequency must be 10–${frequencyCap.toLocaleString()} Hz; one-shot duration maximum 10 seconds and 10,000 pulses.`);
    }
  }

  async function runMotorTestPulse(axis, direction) {
    el("motor-test-axis").value = axis;
    el("motor-test-direction").value = direction;
    loadMotorTestAxisConfig();
    renderMotorTest();
    const parameters = motorTestParameters();
    setText("motor-test-result", "Pulse test running via STM32 Nucleo — use physical E-Stop if needed.");
    const result = await command(
      `Motor test ${axis.toUpperCase()} ${direction}`,
      "/api/maintenance/motor-test",
      {
        action: "pulse",
        axis,
        direction,
        pulse_count: parameters.pulses,
        pulse_frequency_hz: parameters.frequency,
        ignore_limits: parameters.ignoreLimits,
      },
      { noCheck: true, timeoutMs: 15000 },
    );
    if (result) {
      const completed = result.result || {};
      setText("motor-test-result", `TEST COMPLETE — ${completed.pulse_count || parameters.pulses} pulses at ${fmt(completed.pulse_frequency_hz || parameters.frequency, 0)} Hz. Safety bypass: ${parameters.ignoreLimits ? "ON" : "OFF"}.`);
    }
  }

  function stopMotorTestJog(message = "JOG RELEASED — pulse output stopped.") {
    if (!MS.motorTestJog.active) return;
    MS.motorTestJog.active = false;
    MS.motorTestJog.token += 1;
    MS.motorTestJog.button?.classList.remove("running");
    MS.motorTestJog.button = null;
    setText("motor-test-result", message);
  }

  async function startMotorTestJog(axis, direction, button) {
    if (MS.motorTestJog.active || button.disabled) return;
    el("motor-test-axis").value = axis;
    el("motor-test-direction").value = direction;
    loadMotorTestAxisConfig();
    const token = ++MS.motorTestJog.token;
    MS.motorTestJog.active = true;
    MS.motorTestJog.button = button;
    button.classList.add("running");
    setText("motor-test-result", `HOLD JOG ACTIVE — Axis ${axis.toUpperCase()} ${direction.toUpperCase()}. Release the button to stop.`);
    try {
      while (MS.motorTestJog.active && MS.motorTestJog.token === token) {
        const frequency = Math.min(motorTestFrequencyCap(), Math.max(10, Number(el("motor-test-frequency")?.value || 400)));
        const pulseCount = Math.max(1, Math.min(1000, Math.round(frequency * 0.2)));
        await apiCall(
          "/api/maintenance/motor-test",
          "POST",
          {
            action: "pulse",
            axis,
            direction,
            pulse_count: pulseCount,
            pulse_frequency_hz: frequency,
            ignore_limits: Boolean(el("motor-test-bypass-limits")?.checked ?? false),
          },
          3000,
        );
      }
    } catch (error) {
      if (MS.motorTestJog.token === token) {
        stopMotorTestJog(`JOG STOPPED — ${humanizeError(error.message)}`);
        toast(humanizeError(error.message), "error");
      }
    } finally {
      if (MS.motorTestJog.token === token) stopMotorTestJog();
      refresh().catch(() => {});
    }
  }

  // ── Goto Limit (Motor Test) ──────────────────────────────────────────────
  // State for goto limit operation
  const motorTestGoto = { active: false, token: 0, button: null };

  function stopMotorTestGoto(message) {
    if (!motorTestGoto.active) return;
    motorTestGoto.active = false;
    motorTestGoto.token += 1;
    if (motorTestGoto.button) {
      motorTestGoto.button.classList.remove("running");
      motorTestGoto.button.disabled = false;
    }
    motorTestGoto.button = null;
    const statusEl = el("motor-test-goto-status");
    if (statusEl) {
      statusEl.textContent = message || "GOTO COMPLETE";
      statusEl.style.display = "";
      statusEl.className = "motor-test-goto-status done";
    }
    updateMotorTestCalculations();
  }

  async function runGotoLimit(axis, limit, button) {
    if (motorTestGoto.active || MS.motorTestJog.active || button.disabled) return;
    const state = motorTestState();
    if (!state.armed) {
      toast("ARM TEST MODE first before using Goto Limit.", "warn");
      return;
    }
    const ignoreLimits = Boolean(el("motor-test-bypass-limits")?.checked ?? false);
    const frequency = Math.min(motorTestFrequencyCap(), Math.max(10, Number(el("motor-test-frequency")?.value || 400)));
    // Full-stroke: calculate pulses from config max_travel_mm
    const axisCfg = MS.config?.axes?.[axis] || {};
    const stepsPerRev = Number(axisCfg.motor_steps_per_rev || 200);
    const microsteps  = Number(axisCfg.driver_microsteps || 2);
    const pitch       = Number(axisCfg.lead_screw_pitch_mm || 5);
    const maxTravel   = Number(axisCfg.max_travel_mm || 100);
    const ppm = (stepsPerRev * microsteps) / pitch;              // pulses per mm
    const totalPulses = Math.ceil(maxTravel * ppm * 1.05);       // +5% safety margin
    // direction: min → reverse, max → forward
    const direction = (limit === "min") ? "reverse" : "forward";

    const token = ++motorTestGoto.token;
    motorTestGoto.active = true;
    motorTestGoto.button = button;
    button.classList.add("running");
    button.disabled = true;

    const statusEl = el("motor-test-goto-status");
    if (statusEl) {
      statusEl.style.display = "";
      statusEl.className = "motor-test-goto-status active";
      statusEl.textContent = `GOTO ${axis.toUpperCase()} ${limit.toUpperCase()} — Running ${fmt(maxTravel, 1)} mm stroke at ${fmt(frequency, 0)} Hz ...`;
    }
    updateMotorTestCalculations();

    // Send in chunks of 200ms worth of pulses (same as hold-jog), cycling until done
    const chunkPulses = Math.max(1, Math.min(1000, Math.round(frequency * 0.2)));
    let pulsesRemaining = totalPulses;
    try {
      while (motorTestGoto.active && motorTestGoto.token === token && pulsesRemaining > 0) {
        const sendPulses = Math.min(chunkPulses, pulsesRemaining);
        const resp = await apiCall(
          "/api/maintenance/motor-test",
          "POST",
          {
            action: "pulse",
            axis,
            direction,
            pulse_count: sendPulses,
            pulse_frequency_hz: frequency,
            ignore_limits: ignoreLimits,
          },
          3000,
        );
        // Stop if limit switch hit (backend returns ok:false when limit tripped)
        if (resp && resp.ok === false) {
          stopMotorTestGoto(`LIMIT REACHED — ${axis.toUpperCase()} ${limit.toUpperCase()} end stop.`);
          return;
        }
        pulsesRemaining -= sendPulses;
      }
    } catch (err) {
      if (motorTestGoto.token === token) {
        stopMotorTestGoto(`GOTO STOPPED — ${humanizeError(err.message)}`);
        toast(humanizeError(err.message), "error");
      }
      return;
    }
    if (motorTestGoto.token === token) {
      stopMotorTestGoto(`GOTO ${axis.toUpperCase()} ${limit.toUpperCase()} — Full stroke complete.`);
    }
    refresh().catch(() => {});
  }

  function renderMotorTest() {
    if (!document.getElementById("motor-test-page-status")) return;
    const test = motorTestState();
    const armed = Boolean(test.armed);
    const status = getStatus();
    const isStopReq = Boolean(MS.payload?.safety?.stop_requested);
    const isAlarm = MS.payload?.machine_state === "ALARM";

    const pageStatus = el("motor-test-page-status");
    if (pageStatus) {
      pageStatus.textContent = armed ? "ARMED (TEST MODE)" : (isAlarm ? "ALARM TRIPPED" : "DISARMED");
      pageStatus.className = `page-status-chip ${armed ? "warn" : (isAlarm ? "fault" : "")}`;
    }

    const safetyPanel = el("motor-test-safety");
    if (safetyPanel) safetyPanel.classList.toggle("armed", armed);

    if (armed) {
      setText("motor-test-countdown", "TEST MODE ACTIVE (ARMED) — READY TO PULSE / JOG");
    } else if (isAlarm || isStopReq) {
      setText("motor-test-countdown", "WARNING: ALARM TRIPPED — CLICK RESET ALARMS TO UNLOCK");
    } else {
      setText("motor-test-countdown", "PRESS ARM TO ENABLE PULSE OUTPUT");
    }

    const armBtn = el("motor-test-arm");
    if (armBtn) {
      armBtn.disabled = armed || !MS.online || MS.pending || Boolean(MS.payload?.busy)
        || Boolean(status.estop) || isStopReq;
    }
    const cancelBtn = el("motor-test-cancel");
    if (cancelBtn) cancelBtn.disabled = !armed || !MS.online || MS.pending;

    const startBtn = el("motor-test-start");
    if (startBtn) startBtn.disabled = !armed || !MS.online || MS.pending;

    // Enable / disable hold-to-run jog buttons
    $$("[data-motor-test-jog]").forEach((btn) => {
      btn.disabled = !armed || !MS.online || MS.pending;
    });

    // Update Telemetry Panel
    const nucChip = el("test-nucleo-chip");
    const nucComm = MS.payload?.nucleo?.communication_ok;
    if (nucChip) {
      const protocol = Number(MS.payload?.nucleo?.protocol || 1);
      nucChip.textContent = nucComm ? `${armed ? "ARMED" : "ONLINE"} (V${protocol})` : "OFFLINE";
      nucChip.className = `page-status-chip ${nucComm ? (armed ? "warn" : "ok") : "fault"}`;
    }

    const telLink = el("test-tel-link");
    if (telLink) {
      const port = MS.payload?.nucleo?.port ? MS.payload.nucleo.port.split("/").pop() : "ttyACM0";
      telLink.textContent = nucComm ? `${MS.payload?.nucleo?.device || "NUCLEO"} · ${port} @ 115200` : "DISCONNECTED";
    }

    const telMoving = el("test-tel-moving");
    if (telMoving) {
      const m = MS.payload?.nucleo?.moving || {};
      const isMoving = Boolean(m.x || m.y || m.z);
      telMoving.textContent = isMoving ? `PULSING (X:${m.x} Y:${m.y} Z:${m.z})` : "IDLE (0 steps/s)";
      telMoving.style.color = isMoving ? "var(--ok, #25d389)" : "";
    }

    const telWatchdog = el("test-tel-watchdog");
    if (telWatchdog) {
      telWatchdog.textContent = MS.payload?.nucleo?.watchdog ? "ACTIVE (500ms hardware timer)" : "INACTIVE";
    }

    const telPower = el("test-tel-power");
    if (telPower) {
      const estop = Boolean(status.estop || MS.payload?.io?.inputs?.estop);
      telPower.textContent = estop ? "E-STOP TRIPPED (60V CUT)" : "KM1 RELAY CLOSED (60V LIVE)";
      telPower.style.color = estop ? "var(--red-bright, #ff4d4d)" : "var(--ok, #25d389)";
    }

    updateMotorTestCalculations();
  }


  function renderMqttMonitor() {
    if (!document.getElementById("mqtt-page-status")) return;
    const data = MS.mqtt || {};
    const state = String(data.state || "UNKNOWN").toUpperCase();
    const enabled = Boolean(data.enabled);
    const runtimeEnabled = Boolean(data.runtime_enabled);
    const connected = Boolean(data.connected);
    const stateClass = connected ? "ok" : (state === "CONNECTING" ? "warn" : (enabled ? "fault" : "disabled"));
    const broker = data.broker || {};
    const client = data.client || {};
    const topics = data.topics || {};

    setText("mqtt-page-status", state);
    setClass("mqtt-page-status", `page-status-chip ${stateClass === "disabled" ? "" : stateClass}`);
    setText("mqtt-link-state", connected ? "CONNECTED" : state);
    setText("mqtt-link-detail", enabled ? `${broker.host || "--"}:${broker.port || "--"}` : "MQTT disabled in configuration");
    setText("mqtt-client-id", client.cabinet_id || "--");
    setText("mqtt-client-detail", data.client_available ? "Paho client available" : "Client unavailable");
    setText("mqtt-rx-count", Number(data.received_count || 0).toLocaleString());
    setText("mqtt-tx-count", Number(data.published_count || 0).toLocaleString());
    setText("mqtt-command-count", Number(data.command_count || 0).toLocaleString());
    setText("mqtt-rejected-count", `Rejected: ${Number(data.rejected_count || 0).toLocaleString()}`);
    setText("mqtt-last-rx", `Last RX: ${fmtTimestamp(data.last_message_at)}`);
    setText("mqtt-last-tx", `Last TX: ${fmtTimestamp(data.last_publish_at)}`);
    setText("mqtt-broker-address", `${broker.host || "--"}:${broker.port || "--"}`);
    setText("mqtt-keepalive", broker.keepalive_s == null ? "--" : `${broker.keepalive_s} seconds`);
    setText("mqtt-auth-state", broker.authentication_configured ? "CONFIGURED" : "NOT CONFIGURED");
    setText("mqtt-connected-at", fmtTimestamp(data.connected_at));
    setText("mqtt-disconnected-at", fmtTimestamp(data.disconnected_at));
    setText("mqtt-session-count", `${Number(data.connect_count || 0)} / ${Number(data.disconnect_count || 0)}`);
    setText("mqtt-last-error", data.last_error || "NO ERROR");
    setText("mqtt-telemetry-time", `Telemetry: ${fmtTimestamp(data.timestamp)}`);

    const connectButton = document.getElementById("mqtt-connect");
    const disconnectButton = document.getElementById("mqtt-disconnect");
    if (connectButton) connectButton.disabled = MS.mqttControlPending || !enabled || !data.client_available || runtimeEnabled;
    if (disconnectButton) disconnectButton.disabled = MS.mqttControlPending || !runtimeEnabled;

    const linkCard = document.getElementById("mqtt-card-link");
    if (linkCard) linkCard.className = `mqtt-summary-card ${stateClass}`;
    const errorPanel = document.getElementById("mqtt-error-panel");
    if (errorPanel) errorPanel.classList.toggle("fault", Boolean(data.last_error));
    const navLight = document.getElementById("nav-mqtt-light");
    if (navLight) {
      navLight.className = `nav-link-light ${connected ? "connected" : (enabled ? "fault" : "disabled")}`;
      navLight.setAttribute("aria-label", `MQTT ${connected ? "connected" : state.toLowerCase()}`);
    }

    const renderTopics = (id, values) => {
      const container = document.getElementById(id);
      if (!container) return;
      const items = Array.isArray(values) ? values : [];
      container.innerHTML = items.length ? items.map((topic) => `<code>${esc(topic)}</code>`).join("") : "<code>--</code>";
    };
    renderTopics("mqtt-subscribe-topics", topics.subscribe);
    renderTopics("mqtt-publish-topics", topics.publish);

    const stream = document.getElementById("mqtt-message-stream");
    if (stream) {
      const messages = Array.isArray(data.messages) ? data.messages : [];
      stream.innerHTML = messages.length ? messages.map((message) => {
        const payload = typeof message.payload === "string" ? message.payload : JSON.stringify(message.payload, null, 2);
        const direction = String(message.direction || "--").toUpperCase();
        return `<article class="mqtt-message-row ${direction.toLowerCase()}">
          <time>${esc(fmtTimestamp(message.timestamp))}</time>
          <b>${esc(direction)}</b>
          <span>${esc(message.qos ?? 0)}</span>
          <div><code>${esc(message.topic || "--")}</code><pre>${esc(payload)}</pre></div>
        </article>`;
      }).join("") : '<div class="mqtt-empty-state">NO MQTT MESSAGES RECEIVED</div>';
    }
  }

  function renderSequenceMonitor() {
    const operation = getOperation();
    const activeCommand = String(MS.payload?.active_command || "");
    const phase = String(operation.phase || "").toUpperCase();
    const message = String(operation.message || "");
    const messageLower = message.toLowerCase();
    const reportedSteps = Array.isArray(operation.steps)
      ? operation.steps
      : Array.isArray(MS.payload?.sequence?.steps) ? MS.payload.sequence.steps : [];
    // Never invent a sequence.  When the Controller has no step list, show
    // only the phase it actually reported instead of a hard-coded workflow.
    const phaseOrder = reportedSteps.map((item) => String(item?.phase || item).toUpperCase()).filter(Boolean);
    if (!phaseOrder.length && phase) phaseOrder.push(phase);
    const phaseLabels = {
      VALIDATE_SLOT: ["Validate Slot", "Read configured target and readiness"], MOVE_X: ["Move X", "Move X axis to saved target"],
      MOVE_Y: ["Move Y", "Move Y axis to saved target"], MOVE_Z: ["Move Z", "Move Z axis to saved target"],
      VERIFY_TARGET: ["Verify Target", "Confirm XYZ is within tolerance"], HOLD_AT_TARGET: ["Hold at Target", "Hold 3 s; poll E-Stop and stop"],
      HOME_Z: ["Home Z", "Return vertical axis to reference"], HOME_Y: ["Home Y", "Return row axis to reference"],
      HOME_X: ["Home X", "Return travel axis to reference"], VERIFY_HOME: ["Verify Home", "Confirm all axes homed at reference"],
      COMPLETED: ["Completed", "Publish final result and verification"],
    };
    const phaseIndex = phaseOrder.indexOf(phase);
    const liveSequencePhase = phaseOrder.includes(phase) && !["COMPLETED", "FAILED", "STOPPED"].includes(phase);
    const sequenceContext = activeCommand.startsWith("slot_sequence_") || messageLower.includes("slot sequence");
    const sequenceFailed = sequenceContext && ["FAILED", "STOPPED"].includes(phase);
    const sequenceCompleted = sequenceContext && !sequenceFailed && (phase === "COMPLETED" || messageLower.includes("completed slot sequence"));
    const slotMatch = activeCommand.match(/^slot_sequence_(.+)$/i);
    const slotCode = slotMatch?.[1] || (sequenceContext ? (MS.visualTargetSlot || MS.selectedSlotCode || "NO DATA") : "NO DATA");
    const slot = MS.slots?.[slotCode] || {};
    const activeIndex = phaseIndex;
    const command = MS.payload?.motion_command || {};

    const stateChip = el("sequence-monitor-state");
    if (stateChip) {
      const state = sequenceFailed ? "FAILED" : sequenceCompleted ? "COMPLETED" : sequenceContext ? "EXECUTING" : "NOT RUNNING";
      stateChip.textContent = state;
      stateChip.className = `page-status-chip ${sequenceFailed ? "fault" : (sequenceCompleted ? "ok" : "")}`;
    }
    setText("sequence-monitor-command", sequenceContext ? (activeCommand || "SLOT SEQUENCE") : "NO ACTIVE SEQUENCE");
    setText("sequence-monitor-phase", sequenceContext ? (phase || "NO DATA") : "WAITING");
    setText("sequence-monitor-axis", sequenceContext ? (operation.active_axis ? String(operation.active_axis).toUpperCase() : "--") : "--");
    setText("sequence-monitor-slot", slotCode || "NO DATA");
    setText("sequence-monitor-elapsed", sequenceContext && Number.isFinite(Number(command.elapsed_s)) ? `${fmtTime(command.elapsed_s)} s` : "--");
    setText("sequence-monitor-message", sequenceContext ? (message || "Controller is updating sequence state") : "Waiting for a Slot Sequence");
    setText("sequence-monitor-reason", sequenceFailed ? (MS.payload?.last_error || message || "Controller stopped the sequence before it could continue.") : sequenceCompleted ? "Controller reports target and home workflow complete. Review final status and verification before the next command." : sequenceContext ? "Live phase is reported by the Controller. This page is read-only and does not create a motion command." : "No Slot Sequence is active. Start a sequence from Slot Manager or receive a valid MQTT release command; this monitor will then show Controller-reported progress.");
    setText("sequence-order-title", sequenceContext
      ? phaseOrder.map((item) => phaseLabels[item][0]).join(" → ")
      : "Waiting for Controller sequence data");

    const steps = el("sequence-step-list");
    if (steps) steps.innerHTML = phaseOrder.map((step, index) => {
      let state = "pending";
      if (sequenceFailed && (index === activeIndex || activeIndex < 0 && index === 0)) state = "failed";
      else if (sequenceCompleted || (sequenceContext && activeIndex > index)) state = "complete";
      else if (sequenceContext && activeIndex === index) state = "active";
      const [label, detail] = phaseLabels[step] || [step.replaceAll("_", " "), "Controller-reported phase"];
      return `<li class="sequence-step ${state}"><span>${String(index + 1).padStart(2, "0")}</span><strong>${esc(label)}</strong><small>${esc(detail)}</small></li>`;
    }).join("");

    const position = el("sequence-monitor-position");
    if (position) position.innerHTML = AXES.map((axis) => {
      const current = Number(getAxis(axis).position_mm);
      const target = Number(slot[`${axis}_mm`]);
      const hasTarget = sequenceContext && Number.isFinite(target);
      const delta = hasTarget && Number.isFinite(current) ? fmtDelta(target - current).text : "---";
      return `<div><span>${axis.toUpperCase()} AXIS</span><strong>${fmtPos(current)} / ${hasTarget ? fmtPos(target) : "---"} mm</strong><small>Delta to target: ${esc(delta)} mm</small></div>`;
    }).join("");
  }

  /* ── RENDER: INDUSTRIAL I/O MATRIX & COMMISSIONING ────────── */
  function controllerIORegistry(filters = {}) {
    return window.NaritIORegistryView.channels(MS.payload?.io_registry, filters);
  }

  function controllerIOChannel(filters = {}) {
    return window.NaritIORegistryView.first(MS.payload?.io_registry, filters);
  }

  function ioDefinition(channel) {
    return window.NaritIORegistryView.definition(channel);
  }

  function irivChannelDefinitions(direction) {
    return window.NaritIORegistryView.definitions(MS.payload?.io_registry, { source: "iriv_modbus", direction });
  }

  function renderIOMatrix() {
    const diContainer = el("io-di-cards");
    const doContainer = el("io-do-cards");
    if (!diContainer && !doContainer) return;

    const rawInputs = MS.payload?.io?.raw_inputs || {};
    const logicalInputs = MS.payload?.io?.inputs || {};
    const outputs = MS.payload?.io?.outputs || {};
    const inputDetails = MS.payload?.io?.input_details || {};
    const outputDetails = MS.payload?.io?.output_details || {};
    const polarityVerified = MS.payload?.io?.polarity_verified;

    if (diContainer) {
      diContainer.innerHTML = irivChannelDefinitions("input").map((def) => {
        const detail = inputDetails[def.key] || {};
        const rawBit = def.raw_value;
        const isActive = def.active;
        const label = def.label;

        let statusClass = "inactive";
        let stateText = "INACTIVE";
        let badgeClass = "";
        let badgeText = "NORMAL";

        if (def.isSafety) {
          if (isActive) {
            statusClass = "fault";
            stateText = "TRIPPED";
            badgeClass = "fault";
            badgeText = "E-STOP";
          } else {
            statusClass = "safe";
            stateText = "CLEAR";
            badgeClass = "ok";
            badgeText = polarityVerified ? "VERIFIED" : "UNVERIFIED";
          }
        } else if (isActive) {
          statusClass = def.highlight ? "safe" : "active";
          stateText = "TRIGGERED";
          badgeClass = def.highlight ? "ok" : "warn";
          badgeText = def.highlight ? "HOME" : "LIMIT";
        }

        return `
          <div class="io-card ${statusClass} ${def.highlight ? "highlight" : ""}">
            <div class="io-card-head">
              <span class="io-channel-tag">${esc(def.address || `DI${def.channel}`)}</span>
              <span class="io-channel-badge ${badgeClass}">${badgeText}</span>
            </div>
            <div class="io-signal-name">${esc(label)}</div>
            <div class="io-signal-role">${esc(def.role)}</div>
            <div class="io-card-footer">
              <span class="io-card-raw">RAW: <b>${rawBit ? "1" : "0"}</b></span>
              <span class="io-card-state ${statusClass}"><i class="io-dot ${statusClass}"></i> ${stateText}</span>
            </div>
          </div>
        `;
      }).join("");
    }

    if (doContainer) {
      doContainer.innerHTML = irivChannelDefinitions("output").map((def) => {
        const detail = outputDetails[def.key] || {};
        const isOn = Boolean(def.active);
        const label = def.label;
        const statusClass = isOn ? (def.isAlarm ? "fault" : "active") : "inactive";

        return `
          <div class="io-card ${statusClass}">
            <div class="io-card-head">
              <span class="io-channel-tag">${esc(def.address || `DO${def.channel}`)}</span>
              <span class="io-channel-badge ${isOn ? (def.isAlarm ? "fault" : "warn") : ""}">${isOn ? "ENERGIZED" : "OFF"}</span>
            </div>
            <div class="io-signal-name">${esc(label)}</div>
            <div class="io-signal-role">${esc(def.role)}</div>
            <div class="io-card-footer">
              <span class="io-card-raw">COIL: <b>${esc(def.coil)}</b></span>
              <span class="io-card-state ${statusClass}"><i class="io-dot ${statusClass}"></i> ${isOn ? "ON" : "OFF"}</span>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  function renderDI10Commissioning() {
    const rawBit = MS.payload?.io?.raw_inputs?.DI10;
    const logicalEstop = MS.payload?.io?.inputs?.estop;
    const polarityVerified = MS.payload?.io?.polarity_verified;
    const status = getStatus();

    const rawNode = el("comm-raw-di10");
    const rawDesc = el("comm-raw-desc");
    if (rawNode) {
      if (rawBit === undefined) {
        rawNode.textContent = "--";
        rawNode.className = "";
      } else {
        rawNode.textContent = rawBit ? "1 (HIGH / 24V)" : "0 (LOW / 0V)";
        rawNode.className = rawBit ? "ok" : "fault";
      }
    }
    if (rawDesc) {
      rawDesc.textContent = rawBit
        ? "Healthy NC circuit closed (24V present)"
        : "Circuit open (E-Stop pressed or wiring disconnected)";
    }

    const logNode = el("comm-logical-estop");
    if (logNode) {
      logNode.textContent = logicalEstop ? "E-STOP ACTIVE (UNSAFE)" : "CLEAR (SAFE)";
      logNode.className = logicalEstop ? "fault" : "ok";
    }

    const polNode = el("comm-polarity-verified");
    const polDesc = el("comm-polarity-desc");
    const polBadge = el("di10-commissioning-badge");
    if (polNode) {
      polNode.textContent = polarityVerified ? "COMMISSIONED (NC CONTACT)" : "UNVERIFIED (SAFETY BLOCKED)";
      polNode.className = polarityVerified ? "ok" : "warn";
    }
    if (polDesc) {
      polDesc.textContent = polarityVerified
        ? "Active state = FALSE confirmed by operator test"
        : "Requires observed press/release states before motion";
    }
    if (polBadge) {
      polBadge.textContent = polarityVerified ? "COMMISSIONED" : "UNVERIFIED";
      polBadge.className = `page-status-chip ${polarityVerified ? "ok" : "warn"}`;
    }

    const km1Node = el("comm-km1-contact");
    if (km1Node) {
      km1Node.textContent = status.estop ? "TRIPPED / DE-ENERGIZED" : "ENERGIZED / CLOSED";
      km1Node.className = status.estop ? "fault" : "ok";
    }
  }

  /* ── RENDER: DEDICATED I/O STATUS PAGE ─────────────────────── */
  function renderIOStatusPage() {
    const ioPageDiChannels = irivChannelDefinitions("input");
    const ioPageDoChannels = irivChannelDefinitions("output");
    const rawInputs = MS.payload?.io?.raw_inputs || {};
    const logicalInputs = MS.payload?.io?.inputs || {};
    const outputs = MS.payload?.io?.outputs || {};
    const inputDetails = MS.payload?.io?.input_details || {};
    const outputDetails = MS.payload?.io?.output_details || {};
    const polarityVerified = Boolean(MS.payload?.io?.polarity_verified);
    const ioEnabled = Boolean(MS.payload?.io?.enabled);
    const ioCommOk = MS.payload?.io?.communication_ok;
    const piControl = MS.payload?.picontrol_io || {};
    const piCommOk = piControl.communication_ok;
    const piInputs = piControl.inputs || {};
    const snapshotAgeMs = MS.lastStatusAt ? Date.now() - MS.lastStatusAt : Infinity;
    const snapshotStale = snapshotAgeMs > 3000;

    // Summary Strip
    const busState = el("io-summary-bus-state");
    const busSub = el("io-summary-bus-sub");
    if (busState) {
      if (!ioEnabled) {
        busState.textContent = "LEGACY GPIO";
        busState.className = "io-summary-value ok";
        if (busSub) busSub.textContent = "Pi Native GPIO Mode";
      } else if (ioCommOk === false) {
        busState.textContent = "OFFLINE";
        busState.className = "io-summary-value fault";
        if (busSub) busSub.textContent = `${MS.payload?.io?.host || "10.0.0.10"}:${MS.payload?.io?.port || 502} (Disconnected)`;
      } else {
        busState.textContent = "ONLINE (OK)";
        busState.className = "io-summary-value ok";
        if (busSub) busSub.textContent = `${MS.payload?.io?.host || "10.0.0.10"}:${MS.payload?.io?.port || 502} Modbus TCP`;
      }
    }

    let activeDiCount = 0;
    ioPageDiChannels.forEach((def) => {
      if (def.active) activeDiCount++;
    });
    let activeDoCount = 0;
    ioPageDoChannels.forEach((def) => {
      if (def.active) activeDoCount++;
    });

    const diCountNode = el("io-summary-di-count");
    if (diCountNode) diCountNode.textContent = `${activeDiCount} / 11 Active`;

    const doCountNode = el("io-summary-do-count");
    if (doCountNode) doCountNode.textContent = `${activeDoCount} / 4 Active`;

    const estopState = el("io-summary-estop-state");
    const estopSub = el("io-summary-estop-sub");
    const isEstopActive = Boolean(logicalInputs.estop || getStatus().estop);
    if (estopState) {
      estopState.textContent = isEstopActive ? "E-STOP TRIPPED" : "CLEAR";
      estopState.className = `io-summary-value ${isEstopActive ? "fault" : "ok"}`;
    }
    if (estopSub) {
      const rawDi10 = rawInputs.DI10;
      estopSub.textContent = `DI10: ${rawDi10 ? "1 (Closed/NC)" : "0 (Open)"} · ${polarityVerified ? "Verified" : "Unverified"}`;
    }

    const piSummary = el("io-summary-picontrol-state");
    if (piSummary) {
      piSummary.textContent = piCommOk === true ? "ONLINE" : piCommOk === false ? "OFFLINE" : "NO DATA";
      piSummary.className = `io-summary-value ${piCommOk === true ? "ok" : "fault"}`;
    }
    setText("io-summary-picontrol-sub", piControl.last_success_at ? `Last poll ${fmtTimestamp(piControl.last_success_at)}` : (piControl.last_error || "No successful local-input poll"));
    const piRegistry = controllerIORegistry({ source: "picontrol_local", direction: "input" });
    const driveFaults = piRegistry.filter((channel) => channel.kind === "drive_alarm" && channel.active === true);
    const driveSummary = el("io-summary-drive-state");
    if (driveSummary) {
      driveSummary.textContent = driveFaults.length ? `${driveFaults.length} ALARM` : piCommOk === true ? "CLEAR" : "UNKNOWN";
      driveSummary.className = `io-summary-value ${driveFaults.length || piCommOk !== true ? "fault" : "ok"}`;
    }
    const pendSummary = piRegistry
      .filter((channel) => channel.kind === "position_feedback")
      .map((channel) => `${String(channel.axis || "?").toUpperCase()} ${channel.active ? "IN POSITION" : "TRACKING"}`)
      .join(" · ");
    setText("io-summary-drive-sub", driveFaults.length ? driveFaults.map((channel) => channel.label).join(" · ") : `Alarm clear${pendSummary ? ` · ${pendSummary}` : ""}`);
    setText("io-summary-age", snapshotStale ? "STALE" : `${Math.round(snapshotAgeMs)} ms`);
    setText("io-summary-latency", `IRIV ${MS.payload?.io?.poll_latency_ms ?? "--"} ms · PiControl ${piControl.poll_latency_ms ?? "--"} ms`);
    const filteredNoise = Object.values(inputDetails).reduce((total, detail) => total + Number(detail?.filtered_spikes || 0), 0);
    setText("io-summary-noise-count", String(filteredNoise));
    setText("io-summary-noise-sub", filteredNoise ? "Review channels with filtered spikes below" : "No rejected input transitions since Controller start");

    let limitsCount = 0;
    let sensorsCount = 0;
    ioPageDiChannels.forEach((def) => {
      if (def.category === "limits") limitsCount++;
      if (def.category === "sensors") sensorsCount++;
    });
    const piInputCount = Object.keys(piInputs).length;
    setText("io-filter-cnt-all", String(ioPageDiChannels.length + ioPageDoChannels.length + piInputCount));
    setText("io-filter-cnt-inputs", String(ioPageDiChannels.length + piInputCount));
    setText("io-filter-cnt-outputs", String(ioPageDoChannels.length));
    setText("io-filter-cnt-limits", String(limitsCount));
    setText("io-filter-cnt-sensors", String(sensorsCount));
    setText("io-filter-cnt-active", String(activeDiCount + activeDoCount + driveFaults.length));

    const pageHealth = el("io-page-health");
    if (pageHealth) {
      if (snapshotStale || isEstopActive || activeAlarmCount() > 0 || ioCommOk === false || piCommOk === false) {
        pageHealth.textContent = snapshotStale ? "STALE DATA" : isEstopActive ? "E-STOP ACTIVE" : "FAULT DETECTED";
        pageHealth.className = "page-status-chip fault";
      } else {
        pageHealth.textContent = "ALL SIGNALS HEALTHY";
        pageHealth.className = "page-status-chip ok";
      }
    }

    const currentFilter = MS.ioFilter || "all";
    const searchQuery = (MS.ioSearch || "").toLowerCase();

    function matchFilter(item, isOutput = false) {
      if (currentFilter === "inputs" && isOutput) return false;
      if (currentFilter === "outputs" && !isOutput) return false;
      if (currentFilter === "limits" && (isOutput || item.category !== "limits")) return false;
      if (currentFilter === "sensors" && (isOutput || item.category !== "sensors")) return false;
      if (currentFilter === "safety" && (isOutput || item.category !== "safety")) return false;
      if (currentFilter === "drive-alarms") return false;
      if (currentFilter === "active-only") {
        const active = Boolean(item.active);
        if (!active) return false;
      }
      if (searchQuery) {
        const text = `${item.channel} ${item.key} ${item.label} ${item.role} ${item.desc || ""} ${item.terminal || ""}`.toLowerCase();
        if (!text.includes(searchQuery)) return false;
      }
      return true;
    }

    const piSection = el("io-section-picontrol");
    const showPi = ["all", "inputs", "drive-alarms", "active-only"].includes(currentFilter);
    if (piSection) piSection.style.display = showPi ? "" : "none";
    const piHealth = el("io-picontrol-health");
    if (piHealth) {
      piHealth.textContent = piCommOk === true ? (driveFaults.length ? "DRIVE ALARM" : "ONLINE / CLEAR") : "COMMUNICATION FAULT";
      piHealth.className = `page-status-chip ${piCommOk === true && !driveFaults.length ? "ok" : "fault"}`;
    }
    const piCards = el("io-page-picontrol-cards");
    if (piCards) {
      const definitions = piRegistry
       .filter((def) => currentFilter !== "active-only" || def.active === true)
       .filter((def) => currentFilter !== "drive-alarms" || def.kind === "drive_alarm")
       .filter((def) => !searchQuery || `${def.label} ${def.address || ""} GPIO${def.pin ?? "--"} ${def.axis || ""} ${def.kind}`.toLowerCase().includes(searchQuery));
      piCards.innerHTML = definitions.length ? definitions.map((def) => {
        const active = def.active === true;
        const raw = def.raw_value;
        const isPend = def.kind === "position_feedback";
        const fault = def.kind === "drive_alarm" && active;
        const badge = isPend ? (active ? "IN POSITION" : "TRACKING") : (active ? "ALARM" : "CLEAR");
        return `<article class="io-card io-card-enhanced ${fault ? "fault" : "safe"}">
          <div class="io-card-head"><div class="io-head-left"><span class="io-channel-tag">PiControl ${esc(def.address || `DI${def.channel}`)}</span><span class="io-wire-tag">GPIO${esc(def.pin ?? "--")}</span></div><span class="io-channel-badge ${fault ? "fault" : (active ? "ok" : "warn")}">${badge}</span></div>
          <div class="io-signal-name">${esc(def.label)}</div><div class="io-signal-role">${esc(String(def.axis || "").toUpperCase())} ${isPend ? "position-complete feedback" : "drive alarm feedback"}</div>
          <div class="io-signal-desc">Controller registry · ${def.commissioned ? "commissioned" : "advisory / not commissioned"}${def.stale ? " · STALE" : ""}</div>
          <div class="io-card-footer"><span class="io-card-raw">RAW: <b>${raw === true ? "1" : raw === false ? "0" : "--"}</b></span><span class="io-card-state ${fault ? "fault" : "safe"}">${isPend ? badge : (active ? "FAULT ACTIVE" : "NORMAL")}</span></div>
        </article>`;
      }).join("") : '<div class="io-empty-hint">No PiControl driver-alarm inputs match the current filters.</div>';
    }

    const inputsSec = el("io-section-inputs");
    if (inputsSec) {
      const showInputs = currentFilter === "all" || currentFilter === "inputs" || currentFilter === "limits" || currentFilter === "sensors" || currentFilter === "safety" || currentFilter === "active-only";
      inputsSec.style.display = showInputs ? "" : "none";
    }
    const outputsSec = el("io-section-outputs");
    if (outputsSec) {
      const showOutputs = currentFilter === "all" || currentFilter === "outputs" || currentFilter === "active-only";
      outputsSec.style.display = showOutputs ? "" : "none";
    }

    const diContainer = el("io-page-di-cards");
    if (diContainer) {
      const visibleDis = ioPageDiChannels.filter((def) => matchFilter(def, false));
      if (visibleDis.length === 0) {
        diContainer.innerHTML = `<div class="io-empty-hint">No input signals match the current filters.</div>`;
      } else {
        diContainer.innerHTML = visibleDis.map((def) => {
          const detail = inputDetails[def.key] || {};
          const rawBit = def.raw_value;
          const isActive = def.active;
          const label = def.label;
          const logicalTransitions = Number(detail.logical_transitions || 0);
          const rawTransitions = Number(detail.raw_transitions || 0);
          const filteredSpikes = Number(detail.filtered_spikes || 0);
          const lastChange = detail.last_logical_change_at || detail.last_raw_change_at;

          let statusClass = "inactive";
          let stateText = "INACTIVE (0)";
          let badgeClass = "";
          let badgeText = "NORMAL";

          if (def.isSafety) {
            if (isActive) {
              statusClass = "fault";
              stateText = "TRIPPED";
              badgeClass = "fault";
              badgeText = "E-STOP";
            } else {
              statusClass = "safe";
              stateText = "CLEAR";
              badgeClass = "ok";
              badgeText = polarityVerified ? "VERIFIED" : "UNVERIFIED";
            }
          } else if (isActive) {
            statusClass = def.highlight ? "safe" : "active";
            stateText = "TRIGGERED (1)";
            badgeClass = def.highlight ? "ok" : "warn";
            badgeText = def.highlight ? "HOME" : "LIMIT";
          }

          return `
            <div class="io-card io-card-enhanced ${statusClass} ${def.highlight ? "highlight" : ""}">
              <div class="io-card-head">
                <div class="io-head-left">
                  <span class="io-channel-tag">${esc(def.address || `DI${def.channel}`)}</span>
                  <span class="io-wire-tag">${esc(def.terminal)}</span>
                </div>
                <span class="io-channel-badge ${badgeClass}">${badgeText}</span>
              </div>
              <div class="io-signal-name">${esc(label)}</div>
              <div class="io-signal-role">${esc(def.role)}</div>
              <div class="io-signal-desc">${esc(def.desc)}</div>
              <div class="io-card-footer">
                <span class="io-card-raw">RAW: <b>${rawBit ? "1 (24V)" : "0 (0V)"}</b></span>
                <span class="io-card-state ${statusClass}">
                  <i class="io-dot ${statusClass}"></i> ${stateText}
                </span>
              </div>
              <dl class="io-diagnostic-meta">
                <div><dt>Polarity</dt><dd>${detail.active_state === false ? "ACTIVE LOW" : "ACTIVE HIGH"}</dd></div>
                <div><dt>Debounce</dt><dd>${Number(detail.debounce_samples || 1)} samples</dd></div>
                <div><dt>Transitions</dt><dd>${logicalTransitions} / ${rawTransitions} logical/raw</dd></div>
                <div class="${filteredSpikes ? "warn" : ""}"><dt>Filtered noise</dt><dd>${filteredSpikes}</dd></div>
                <div><dt>Last change</dt><dd>${lastChange ? esc(fmtTimestamp(lastChange)) : "--"}</dd></div>
                <div><dt>Last active</dt><dd>${detail.active_since_at ? "ACTIVE NOW" : detail.last_active_duration_ms != null ? `${Number(detail.last_active_duration_ms).toFixed(0)} ms` : "--"}</dd></div>
              </dl>
            </div>
          `;
        }).join("");
      }
    }

    const doContainer = el("io-page-do-cards");
    if (doContainer) {
      const visibleDos = ioPageDoChannels.filter((def) => matchFilter(def, true));
      if (visibleDos.length === 0) {
        doContainer.innerHTML = `<div class="io-empty-hint">No output signals match the current filters.</div>`;
      } else {
        doContainer.innerHTML = visibleDos.map((def) => {
          const detail = outputDetails[def.key] || {};
          const isOn = Boolean(def.active);
          const label = def.label;
          const statusClass = isOn ? (def.isAlarm ? "fault" : "active") : "inactive";

          return `
            <div class="io-card io-card-enhanced ${statusClass}">
              <div class="io-card-head">
                <div class="io-head-left">
                  <span class="io-channel-tag">${esc(def.address || `DO${def.channel}`)}</span>
                  <span class="io-wire-tag">${esc(def.coil)}</span>
                </div>
                <span class="io-channel-badge ${isOn ? (def.isAlarm ? "fault" : "warn") : ""}">${isOn ? "ENERGIZED" : "OFF"}</span>
              </div>
              <div class="io-signal-name">${esc(label)}</div>
              <div class="io-signal-role">${esc(def.role)}</div>
              <div class="io-signal-desc">${esc(def.desc)}</div>
              <div class="io-card-footer">
                <span class="io-card-raw">COIL: <b>${esc(def.coil)}</b></span>
                <span class="io-card-state ${statusClass}">
                  <i class="io-dot ${statusClass}"></i> ${isOn ? "ON (ENERGIZED)" : "OFF"}
                </span>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    const tableBody = el("io-axes-table-body");
    if (tableBody) {
      const status = getStatus();
      const xStatus = status.x || {};
      const yStatus = status.y || {};
      const zStatus = status.z || {};

      const axisSignal = (axis, positionRole) => controllerIOChannel({ source: "iriv_modbus", direction: "input", axis, position_role: positionRole });
      const signalPill = (signal, fallback, activeFallback = false) => {
        const active = signal ? Boolean(signal.active) : Boolean(activeFallback);
        const address = signal?.address || "--";
        const label = signal?.label || fallback;
        return `<span class="limit-status-pill ${active ? "triggered" : "normal"}">${esc(address)}: ${esc(label)} ${active ? "ACTIVE" : "Normal"}</span>`;
      };
      const xMin = axisSignal("x", "min");
      const xMax = axisSignal("x", "max");
      const yMin = axisSignal("y", "min");
      const yMax = axisSignal("y", "max");
      const zMin = axisSignal("z", "min");
      const zMax = axisSignal("z", "max");
      const zHome = axisSignal("z", "home");
      const processSignals = controllerIORegistry({ source: "iriv_modbus", direction: "input", kind: "process_sensor" });
      const dispenseSignal = controllerIOChannel({ source: "iriv_modbus", direction: "output", operation_role: "dispense" });

      tableBody.innerHTML = `
        <tr>
          <td><strong class="axis-badge">X Axis</strong><div class="axis-sub">Horizontal Gantry</div></td>
          <td>${signalPill(xMin, "X Min", xStatus.head_limit)}</td>
          <td>${signalPill(xMax, "X Max", xStatus.tail_limit)}</td>
          <td><span class="limit-status-pill normal">--</span></td>
          <td><code>PA8 (PUL) / PB0 (DIR)</code><br><small>Driver: HBS860H X</small></td>
          <td>Stop X gantry instantly; inhibit negative / positive jogging accordingly.</td>
        </tr>
        <tr>
          <td><strong class="axis-badge">Y Axis</strong><div class="axis-sub">Depth Gantry</div></td>
          <td>${signalPill(yMin, "Y Min", yStatus.head_limit)}</td>
          <td>${signalPill(yMax, "Y Max", yStatus.tail_limit)}</td>
          <td><span class="limit-status-pill normal">--</span></td>
          <td><code>PA9 (PUL) / PB1 (DIR)</code><br><small>Driver: HBS860H Y</small></td>
          <td>Stop Y gantry instantly; inhibit negative / positive jogging accordingly.</td>
        </tr>
        <tr>
          <td><strong class="axis-badge">Z Axis</strong><div class="axis-sub">Vertical Elevator</div></td>
          <td>${signalPill(zMin, "Z Min", zStatus.head_limit)}</td>
          <td>${signalPill(zMax, "Z Max", zStatus.tail_limit)}</td>
          <td>${signalPill(zHome, "Z Home")}</td>
          <td><code>PA5 (PUL) / PB2 (DIR)</code><br><small>Driver: DM542 Z</small></td>
          <td>Stop Z carriage; Z Home registers gantry zero reference position.</td>
        </tr>
        <tr class="product-row">
          <td><strong class="axis-badge product">Product Delivery</strong><div class="axis-sub">Chute &amp; Dispenser</div></td>
          <td>${signalPill(processSignals[0], "Process Sensor 1")}</td>
          <td>${signalPill(processSignals[1], "Process Sensor 2")}</td>
          <td>${signalPill(processSignals[2], "Process Sensor 3")}</td>
          <td>${signalPill(dispenseSignal, "Dispense Output")}</td>
          <td>Interlocked dispensing sequence; optical confirmation before slot release.</td>
        </tr>
      `;
    }

    const rawDi10 = rawInputs.DI10;
    const estopLogic = logicalInputs.estop;
    const rawBitEl = el("io-comm-raw-di10");
    const rawDescEl = el("io-comm-raw-desc");
    if (rawBitEl) {
      if (rawDi10 === undefined) {
        rawBitEl.textContent = "--";
        rawBitEl.className = "";
      } else {
        rawBitEl.textContent = rawDi10 ? "1 (HIGH / 24V)" : "0 (LOW / 0V)";
        rawBitEl.className = rawDi10 ? "ok" : "fault";
      }
    }
    if (rawDescEl) {
      rawDescEl.textContent = rawDi10
        ? "Closed NC circuit healthy (24V present across safety loop)"
        : "Circuit broken (E-Stop pressed or safety wire disconnected)";
    }

    const logEstopEl = el("io-comm-logical-estop");
    const logDescEl = el("io-comm-logical-desc");
    if (logEstopEl) {
      logEstopEl.textContent = estopLogic ? "E-STOP TRIPPED (UNSAFE)" : "CLEAR (SAFE)";
      logEstopEl.className = estopLogic ? "fault" : "ok";
    }
    if (logDescEl) {
      logDescEl.textContent = estopLogic
        ? "Motion prohibited by controller safety interlock"
        : "Safety circuit verified closed; motion arming permitted";
    }

    const polEl = el("io-comm-polarity");
    const polBadge = el("io-di10-gate-badge");
    if (polEl) {
      polEl.textContent = polarityVerified ? "COMMISSIONED (NC CONTACT)" : "UNVERIFIED (SAFETY BLOCKED)";
      polEl.className = polarityVerified ? "ok" : "warn";
    }
    if (polBadge) {
      polBadge.textContent = polarityVerified ? "COMMISSIONED" : "UNVERIFIED";
      polBadge.className = `page-status-chip ${polarityVerified ? "ok" : "warn"}`;
    }

    const km1El = el("io-comm-km1");
    if (km1El) {
      km1El.textContent = estopLogic ? "TRIPPED / DE-ENERGIZED" : "ENERGIZED / CLOSED";
      km1El.className = estopLogic ? "fault" : "ok";
    }

    const diStream = el("io-raw-di-bitstream");
    if (diStream) {
      diStream.innerHTML = ioPageDiChannels.map((channel) => {
        const val = channel.raw_value;
        const bitVal = val ? "1" : "0";
        const cls = val ? "bit-on" : "bit-off";
        const address = channel.address || `DI${channel.channel}`;
        return `<span class="io-bit-pill ${cls}" title="${esc(channel.label)}"><b>${esc(address)}</b><code>${bitVal}</code></span>`;
      }).join("");
    }

    const doStream = el("io-raw-do-bitstream");
    if (doStream) {
      doStream.innerHTML = ioPageDoChannels.map((channel) => {
        const val = Boolean(channel.active);
        const bitVal = val ? "1" : "0";
        const cls = val ? "bit-on" : "bit-off";
        const address = channel.address || `DO${channel.channel}`;
        return `<span class="io-bit-pill ${cls}" title="${esc(channel.label)} (${esc(channel.coil)})"><b>${esc(address)}</b><code>${bitVal}</code></span>`;
      }).join("");
    }

    const modbusChip = el("io-raw-modbus-chip");
    if (modbusChip) {
      if (!ioEnabled) {
        modbusChip.textContent = "NATIVE GPIO";
        modbusChip.className = "page-status-chip ok";
      } else if (ioCommOk === false) {
        modbusChip.textContent = "COMM TIMEOUT";
        modbusChip.className = "page-status-chip fault";
      } else {
        modbusChip.textContent = "POLLING OK (0.1s)";
        modbusChip.className = "page-status-chip ok";
      }
    }
  }

  function renderDashboardIOSummary() {
    const summaryGrid = el("dashboard-io-summary");
    if (!summaryGrid) return;

    const items = controllerIORegistry({ source: "iriv_modbus" }).map((channel) => {
      const def = ioDefinition(channel);
      return {
        tag: def.address || `${def.direction === "input" ? "DI" : "DO"}${def.channel}`,
        name: def.label,
        active: def.active,
        isSafety: def.isSafety,
        isAlarm: def.isAlarm,
        highlight: def.highlight,
      };
    });

    summaryGrid.innerHTML = items.map((item) => {
      let cls = item.active ? (item.isSafety || item.isAlarm ? "fault" : (item.highlight ? "safe" : "active")) : "inactive";
      let dotCls = cls;
      return `<div class="dash-io-pill ${cls}"><i class="io-dot ${dotCls}"></i><b>${item.tag}</b><span>${esc(item.name)}</span></div>`;
    }).join("");

    const ioComm = el("dashboard-io-comm");
    if (ioComm) {
      const ok = MS.payload?.io?.communication_ok;
      ioComm.textContent = ok ? "10.0.0.10 ONLINE" : "OFFLINE";
      ioComm.className = ok ? "ok" : "fault";
    }

    const topoIo = el("dash-topo-io");
    if (topoIo) {
      topoIo.textContent = `IRIV IO Modbus TCP (10.0.0.10:502 · ${MS.payload?.io?.communication_ok ? "ONLINE" : "OFFLINE"})`;
    }
    const topoNuc = el("dash-topo-nucleo");
    if (topoNuc) {
      topoNuc.textContent = `NUCLEO-F439ZI (${MS.payload?.nucleo?.communication_ok ? "SAFE LINK ONLINE" : "OFFLINE"})`;
    }
    const topoEstop = el("dash-topo-estop");
    if (topoEstop) {
      topoEstop.textContent = `E-Stop & KM1 (DI10: ${rawInputs.DI10 ? "CLOSED/1" : "OPEN/0"} · ${MS.payload?.io?.polarity_verified ? "VERIFIED" : "UNVERIFIED"})`;
    }
  }

  function renderSystemControl() {
    const io = MS.payload?.io || {};
    const picontrol = MS.payload?.picontrol_io || {};
    const nucleo = MS.payload?.nucleo || {};
    const safety = MS.payload?.safety || {};
    const estop = Boolean(safety.estop_active || getStatus().estop);
    const motionEnabled = Boolean(safety.motion_enabled);
    const healthy = MS.online && io.communication_ok !== false && nucleo.communication_ok !== false && !estop;
    const cards = [
      ["IRIV Pi / Controller", MS.online ? "ONLINE" : "OFFLINE", MS.online ? "Web API and Controller IPC responding" : "Controller snapshot unavailable", MS.online],
      ["IRIV I/O", io.communication_ok ? "ONLINE" : "OFFLINE", io.last_success_at ? `Last response: ${fmtTimestamp(io.last_success_at)}` : (io.last_error || "No successful Modbus poll"), Boolean(io.communication_ok)],
      ["STM32 NUCLEO", nucleo.communication_ok ? "ONLINE" : "OFFLINE", `${nucleo.port || "USB not configured"} · Protocol v${nucleo.protocol ?? "--"}`, Boolean(nucleo.communication_ok)],
      ["DI10 E-Stop", estop ? "ACTIVE" : "CLEAR", estop ? "All-axis stop is latched" : "NC safety input is clear", !estop],
    ];
    const grid = el("system-health-grid");
    if (grid) grid.innerHTML = cards.map(([label, value, detail, ok]) => `<article class="system-health-card ${ok ? "ok" : "fault"}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></article>`).join("");
    setText("system-overall-state", healthy ? "COMMUNICATION HEALTHY" : "ACTION REQUIRED");
    setClass("system-overall-state", `page-status-chip ${healthy ? "ok" : "fault"}`);
    setText("system-motion-state", motionEnabled ? "ENABLED" : "DISABLED");
    setClass("system-motion-state", `page-status-chip ${motionEnabled ? "ok" : "fault"}`);
    setText("system-nucleo-state", nucleo.communication_ok ? "ONLINE" : "OFFLINE");
    setClass("system-nucleo-state", `page-status-chip ${nucleo.communication_ok ? "ok" : "fault"}`);
    setText("system-di10-state", estop ? "E-STOP ACTIVE" : "CLEAR");
    setClass("system-di10-state", `page-status-chip ${estop ? "fault" : "ok"}`);
    setText("system-di10-logical", estop ? "ACTIVE / STOPPED" : "CLEAR");
    setText("system-di10-raw", io.raw_inputs?.DI10 === true ? "HIGH / 1" : io.raw_inputs?.DI10 === false ? "LOW / 0" : "--");
    const enable = el("system-motion-enable");
    if (enable) enable.disabled = motionEnabled || !MS.online || estop || !io.communication_ok || !nucleo.communication_ok;
    const disable = el("system-motion-disable");
    if (disable) disable.disabled = !MS.online || !motionEnabled;
    const reset = el("system-nucleo-reset");
    if (reset) reset.disabled = !MS.online || Boolean(MS.payload?.busy);
    const drivePowerOn = picontrol.outputs?.xy_drive_power === true;
    setText("system-drive-power-state", drivePowerOn ? "POWER ON" : "POWER OFF");
    setClass("system-drive-power-state", `page-status-chip ${drivePowerOn ? "ok" : "fault"}`);
    const driveReset = el("system-drive-power-reset");
    if (driveReset) driveReset.disabled = !MS.online || Boolean(MS.payload?.busy) || picontrol.communication_ok === false;
    const driveCut = el("system-drive-power-cut");
    if (driveCut) driveCut.disabled = !MS.online || !drivePowerOn;
    const driveRestore = el("system-drive-power-restore");
    if (driveRestore) driveRestore.disabled = !MS.online || drivePowerOn || Boolean(MS.payload?.busy) || picontrol.communication_ok === false;
    const history = el("system-action-history");
    if (history) {
      const entries = MS.events.filter((event) => ["SYSTEM", "SAFETY", "INTERLOCK", "CONFIG"].includes(eventCategory(event))).slice(0, 8);
      history.innerHTML = entries.length ? entries.map((event) => `<li><time>${esc(eventTime(event))}</time><b>${esc(eventOutcome(event))}</b><span>${esc(sanitizeEventText(event.message))}</span></li>`).join("") : "<li>No system-control events in this browser session.</li>";
    }
  }

  async function runSystemAction(path, successMessage) {
    try {
      await apiCall(path, "POST", {}, 10000);
      setText("system-action-result", successMessage);
      toast(successMessage, "ok");
      await refresh();
    } catch (error) {
      setText("system-action-result", error.message);
      toast(`SYSTEM CONTROL FAILED — ${error.message}`, "error");
    }
  }

  function renderDemoSampling() {
    const demo = MS.payload?.demo || {};
    const state = String(demo.state || "IDLE").toUpperCase();
    const counters = demo.counters || {};
    setText("demo-state", state);
    setClass("demo-state", `page-status-chip ${["FAILED", "STOPPED", "E_STOPPED"].includes(state) ? "fault" : ["RUNNING", "MOVING_TO_SLOT", "STARTING"].includes(state) ? "ok" : ""}`);
    setText("demo-session", demo.session_id ? String(demo.session_id).slice(0, 10) : "--");
    setText("demo-cycle", demo.cycle || 0);
    setText("demo-slots", `${demo.current_slot || "--"} / ${demo.next_slot || "--"}`);
    setText("demo-last-result", demo.last_result || "--");
    const grid = el("demo-counter-grid");
    if (grid) grid.innerHTML = ["requested", "attempted", "passed", "failed", "skipped", "stopped", "success_rate"].map((key) => `<div><span>${esc(key.replace("_", " ").toUpperCase())}</span><strong>${esc(counters[key] ?? 0)}${key === "success_rate" ? "%" : ""}</strong></div>`).join("");
    const active = ["STARTING", "RUNNING", "MOVING_TO_SLOT", "PAUSE_REQUESTED", "PAUSED", "STOPPING"].includes(state);
    const paused = state === "PAUSED";
    const setDisabled = (id, disabled) => { const node = el(id); if (node) node.disabled = disabled; };
    setDisabled("demo-configure", active);
    setDisabled("demo-validate", active);
    setDisabled("demo-arm", active);
    setDisabled("demo-start", state !== "ARMED" || !MS.demoArmToken);
    setDisabled("demo-pause", !["STARTING", "RUNNING", "MOVING_TO_SLOT"].includes(state));
    setDisabled("demo-resume", !paused);
    setDisabled("demo-stop", !active);
    const durationInput = el("demo-max-duration");
    if (durationInput) {
      const configuredDuration = Number(demo.configuration?.max_duration_s || 0);
      durationInput.value = String(active && configuredDuration > 0 ? Math.ceil(configuredDuration) : calculateDemoMaxDuration());
    }
    renderDemoHistory();
  }

  async function loadDemoHistory(force = false) {
    if (MS.demoHistoryPending || (!force && Date.now() - MS.demoHistoryFetchedAt < 5000)) return;
    MS.demoHistoryPending = true;
    const refreshButton = el("demo-history-refresh");
    if (refreshButton) refreshButton.disabled = true;
    try {
      const data = await apiCall("/api/demo/history", "GET", undefined, 8000);
      MS.demoHistory = Array.isArray(data.sessions) ? data.sessions : [];
      MS.demoHistoryFetchedAt = Date.now();
    } catch (error) {
      const list = el("demo-history-list");
      if (list) list.innerHTML = `<p class="demo-history-empty fault">History unavailable: ${esc(error.message)}</p>`;
    } finally {
      MS.demoHistoryPending = false;
      if (refreshButton) refreshButton.disabled = false;
      renderDemoHistory();
    }
  }

  function renderDemoHistory() {
    const list = el("demo-history-list");
    if (!list) return;
    if (!MS.demoHistory.length) {
      if (!MS.demoHistoryPending) list.innerHTML = '<p class="demo-history-empty">No completed Demo Sampling sessions recorded yet.</p>';
      return;
    }
    list.innerHTML = MS.demoHistory.map((session, index) => {
      const samples = Array.isArray(session.samples) ? session.samples : [];
      const attempted = Number(session.attempted || 0);
      const passed = Number(session.passed || 0);
      const rate = attempted ? Math.round((passed / attempted) * 1000) / 10 : 0;
      const state = String(session.state || "UNKNOWN").toUpperCase();
      const stateClass = state === "COMPLETED" && Number(session.failed || 0) === 0 ? "ok" : (state === "RUNNING" ? "warn" : "fault");
      const config = session.configuration || {};
      const rows = samples.map((sample) => {
        const result = String(sample.result || "UNKNOWN").toUpperCase();
        const resultClass = result === "PASSED" ? "ok" : result === "SKIPPED" ? "warn" : "fault";
        return `<tr><td>${esc(sample.cycle_no)}</td><td>${esc(sample.slot_code)}</td><td><span class="demo-result ${resultClass}">${esc(result)}</span></td><td>${esc(fmtTime(sample.duration_s))} s</td><td>${esc(fmtTimestamp(sample.started_at))}</td><td>${esc(sample.reason || "—")}</td></tr>`;
      }).join("");
      return `<details class="demo-history-session" ${index === 0 ? "open" : ""}>
        <summary><span><b>${esc(fmtTimestamp(session.started_at))}</b><small>Session ${esc(String(session.session_id || "").slice(0, 12))}</small></span><span class="demo-result ${stateClass}">${esc(state)}</span><span>${passed}/${attempted} passed</span><span>${rate}%</span></summary>
        <div class="demo-history-meta"><span>Mode <b>${esc(config.mode || "—")}</b></span><span>Requested <b>${esc(session.requested || 0)}</b></span><span>Failed <b>${esc(session.failed || 0)}</b></span><span>Stopped <b>${esc(session.stopped || 0)}</b></span><span>Reason <b>${esc(session.final_reason || "—")}</b></span></div>
        <div class="demo-history-table-wrap"><table><thead><tr><th>Move</th><th>Slot</th><th>Result</th><th>Duration</th><th>Started</th><th>Reason</th></tr></thead><tbody>${rows || '<tr><td colspan="6">No sample rows recorded.</td></tr>'}</tbody></table></div>
      </details>`;
    }).join("");
  }

  function calculateDemoMaxDuration() {
    const count = Math.max(1, Math.min(10000, Math.floor(Number(el("demo-max-cycles")?.value) || 1)));
    const dwell = Math.max(0, Number(el("demo-dwell")?.value) || 0);
    const speed = Math.max(0.1, effectiveMotionSpeed());
    const mode = el("demo-mode")?.value || "random";
    const selected = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const candidates = (mode === "selected" ? [MS.slots?.[selected]] : Object.values(MS.slots || {}))
      .filter((slot) => slot && [slot.x_mm, slot.y_mm, slot.z_mm].every((value) => Number.isFinite(Number(value))))
      .map((slot) => ({x: Number(slot.x_mm), y: Number(slot.y_mm), z: Number(slot.z_mm)}));
    if (!candidates.length) return Math.ceil((count * (dwell + 10)) + 10);

    const safeZ = Math.max(0, Number(MS.config?.safe_z_mm ?? MS.payload?.config?.safe_z_mm ?? 10) || 10);
    const tripSeconds = (from, to) => {
      const startZ = from.z < safeZ ? safeZ : from.z;
      const clearZ = Math.max(0, safeZ - from.z);
      const xy = Math.max(Math.abs(to.x - from.x), Math.abs(to.y - from.y));
      const targetZ = Math.abs(to.z - startZ);
      return (clearZ + xy + targetZ) / speed;
    };
    const current = {x: Number(getAxis("x").position_mm || 0), y: Number(getAxis("y").position_mm || 0), z: Number(getAxis("z").position_mm || 0)};
    const firstMove = Math.max(...candidates.map((target) => tripSeconds(current, target)));
    let laterMove = 0;
    for (const from of candidates) for (const to of candidates) laterMove = Math.max(laterMove, tripSeconds(from, to));

    // 25% timing reserve plus three seconds per sample covers command setup,
    // USB acknowledgements and settling without turning the watchdog unbounded.
    const estimated = firstMove + (Math.max(0, count - 1) * laterMove) + (count * (dwell + 3));
    return Math.max(10, Math.ceil((estimated * 1.25) + 10));
  }

  function demoPayload() {
    const selected = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const mode = el("demo-mode")?.value || "sequential";
    const maxDuration = calculateDemoMaxDuration();
    const durationInput = el("demo-max-duration");
    if (durationInput) durationInput.value = String(maxDuration);
    return {
      mode,
      slots: mode === "selected" ? [selected] : Object.keys(MS.slots),
      sample_count: Number(el("demo-max-cycles")?.value || 0),
      max_duration_s: maxDuration,
      dwell_s: Number(el("demo-dwell")?.value || 0),
      speed_mm_s: effectiveMotionSpeed(),
      stop_on_failure: true,
    };
  }

  async function demoAction(action, payload = {}) {
    try {
      const data = await apiCall(`/api/demo/${action}`, "POST", payload, 10000);
      const result = data.result || data;
      if (action === "arm") MS.demoArmToken = result.arm_token || "";
      if (["configure", "validate", "start", "stop"].includes(action) && action !== "arm" && action !== "start") {
        MS.demoArmToken = "";
      }
      setText("demo-feedback", result.error || `Demo ${action}: ${result.state || "accepted"}`);
      await refresh();
      if (["start", "stop"].includes(action)) loadDemoHistory(true);
    } catch (error) {
      setText("demo-feedback", error.message);
      toast(`DEMO ${action.toUpperCase()} FAILED — ${error.message}`, "error");
    }
  }

  function invalidateDemoConfiguration() {
    MS.demoArmToken = "";
    setText("demo-feedback", "Demo parameters changed — Configure, Validate and Arm again.");
    renderDemoSampling();
  }

  function homeAllAxes() {
    return command("Home all axes", "/api/home/all", undefined, { timeoutMs: 300000 });
  }

  function homeAxis(axis) {
    if (!AXES.includes(axis)) return undefined;
    return command(`Home axis ${axis.toUpperCase()}`, `/api/home/${axis}`, undefined, { timeoutMs: 300000 });
  }

  function stopTravelMotion() {
    setText("travel-limit-feedback", "STOP requested — waiting for controller status.");
    return command("Stop motion", "/api/stop", undefined, { isStop: true, noCheck: true });
  }

  async function resetTravelInterlock() {
    setText("travel-limit-feedback", "Resetting software Stop latch and resettable alarms…");
    const result = await command("Reset stop and alarms", "/api/clear-alarm", undefined, { isStop: true, noCheck: true });
    setText("travel-limit-feedback", result
      ? "Reset accepted. Waiting for Controller readiness before enabling Min / Max."
      : "Reset was rejected. Review the interlock reason above.");
  }

  async function moveAxisToLimit(axis, limit) {
    const maximum = Number(MS.config?.axes?.[axis]?.max_travel_mm);
    if (!AXES.includes(axis) || !["min", "max"].includes(limit) || !Number.isFinite(maximum)) {
      toast("Axis travel configuration is unavailable.", "error");
      return;
    }
    const target = limit === "min" ? 0 : maximum;
    setText("travel-limit-feedback", `Moving ${axis.toUpperCase()} to ${limit.toUpperCase()} (${target.toFixed(3)} mm).`);
    const result = await command(
      `Move ${axis.toUpperCase()} to ${limit.toUpperCase()}`,
      "/api/move-to-limit",
      { axis, endpoint: limit, speed_mm_s: effectiveMotionSpeed([axis]) },
      { timeoutMs: 650000 },
    );
    setText("travel-limit-feedback", result
      ? `${axis.toUpperCase()} ${limit.toUpperCase()} command completed. Verify the displayed position and limit sensor.`
      : `${axis.toUpperCase()} ${limit.toUpperCase()} command was rejected or stopped. Review the interlock message.`);
  }

  function moveAxisToPosition(axis) {
    if (!AXES.includes(axis)) return undefined;
    const target = Number(el(`axis-goto-${axis}`)?.value);
    const maximum = Number(MS.config?.axes?.[axis]?.max_travel_mm);
    if (!Number.isFinite(target) || target < 0 || target > maximum) {
      toast(`${axis.toUpperCase()} target must be within 0-${maximum} mm.`, "error");
      return undefined;
    }
    setText("travel-limit-feedback", `Moving ${axis.toUpperCase()} to ${target.toFixed(3)} mm.`);
    return command(
      `Move ${axis.toUpperCase()} to ${target.toFixed(3)} mm`,
      "/api/move",
      { [`${axis}_mm`]: target, speed_mm_s: effectiveMotionSpeed([axis]) },
      { requiredAxes: [axis], timeoutMs: 650000 },
    );
  }

  function renderWorkspacePages() {
    const status = getStatus();
    const operation = getOperation();
    const homed = allAxesHomed();
    const ready = MS.online && !status.estop && !MS.payload?.safety?.stop_requested && homed && !MS.payload?.busy && activeAlarmCount() === 0;
    const alarmCount = activeAlarmCount();
    const configuredSlots = Object.values(MS.slots || {}).filter((slot) => slotStatus(slot) === "ready").length;

    renderDashboard();
    renderSlotTable();
    loadSelectedSlotEditor();
    renderSelectedSlotSequenceProcess();

    const dashboardAxes = document.getElementById("legacy-dashboard-axis-grid");
    if (dashboardAxes) dashboardAxes.innerHTML = AXES.map((axis) => {
      const data = getAxis(axis);
      return `<article class="dashboard-axis-card"><span>${axis.toUpperCase()} AXIS</span><strong>${fmtPos(data.position_mm)} mm</strong><small>${data.is_homed ? "HOMED" : "NOT HOMED"} · ${fmtSteps(data.position_steps)} steps</small></article>`;
    }).join("");

    renderVisualizationV32();

    const diagnostics = document.getElementById("diagnostic-grid");
    if (diagnostics) {
      const diagnosticItems = [
        ["Controller Link", MS.online ? "ONLINE" : "OFFLINE", MS.online ? "API polling every 1 second" : "No response from controller", MS.online ? "ok" : "fault"],
        ["IRIV IO Link", MS.payload?.io?.communication_ok === false ? "OFFLINE" : (MS.payload?.io?.enabled ? "ONLINE" : "DISABLED"), MS.payload?.io?.enabled ? `${MS.payload.io.host}:${MS.payload.io.port} Modbus TCP` : "Legacy GPIO configuration", MS.payload?.io?.communication_ok === false ? "fault" : "ok"],
        ["Nucleo Link", MS.payload?.nucleo?.communication_ok === false ? "OFFLINE" : (MS.payload?.nucleo?.enabled ? "ONLINE" : "DISABLED"), MS.payload?.nucleo?.enabled ? `${MS.payload.nucleo.device} · ${MS.payload.nucleo.port} · ${MS.payload.nucleo.baudrate} baud` : "Nucleo health link is disabled", MS.payload?.nucleo?.communication_ok === false ? "fault" : "ok"],
        ["Emergency Stop", status.estop ? "ACTIVE" : "CLEAR", "Hardware safety input", status.estop ? "fault" : "ok"],
        ["Homing", homed ? "COMPLETE" : "REQUIRED", AXES.map((a) => `${a.toUpperCase()}:${getAxis(a).is_homed ? "OK" : "--"}`).join("  "), homed ? "ok" : "warn"],
        ["Motion Queue", MS.payload?.busy ? "BUSY" : "IDLE", MS.payload?.active_command || "No pending command", MS.payload?.busy ? "warn" : "ok"],
        ["Active Alarms", String(alarmCount), MS.payload?.last_error || "No controller faults", alarmCount ? "fault" : "ok"],
        ["Slot Database", String(Object.keys(MS.slots || {}).length), `${configuredSlots} configured locations`, "ok"],
        ["Last Operation", operation.ok === false ? "FAILED" : "NORMAL", operation.message || "No operation message", operation.ok === false ? "fault" : "ok"],
      ];
      diagnostics.innerHTML = diagnosticItems.map(([label, value, detail, stateClass]) => `<article class="diagnostic-card ${stateClass}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></article>`).join("");
    }
    const diagHealth = document.getElementById("diag-health");
    if (diagHealth) {
      diagHealth.textContent = alarmCount ? "FAULT DETECTED" : (MS.online ? "SYSTEM HEALTHY" : "OFFLINE");
      diagHealth.className = `page-status-chip ${alarmCount || !MS.online ? "fault" : "ok"}`;
    }

    renderIOMatrix();
    renderDI10Commissioning();
    renderIOStatusPage();
    renderConfigurationEditor();
    renderMotorTest();
    renderMqttMonitor();
    renderSequenceMonitor();
    renderSystemControl();
    renderDemoSampling();

    const architectureHealth = el("architecture-health");
    if (architectureHealth) {
      const nucleoOk = MS.payload?.nucleo?.communication_ok === true;
      const ioOk = MS.payload?.io?.communication_ok !== false;
      const healthy = MS.online && nucleoOk && ioOk;
      architectureHealth.textContent = !MS.online ? "CONTROLLER OFFLINE" : !nucleoOk ? "NUCLEO OFFLINE" : !ioOk ? "IRIV I/O OFFLINE" : "ALL LINKS ONLINE";
      architectureHealth.className = `page-status-chip ${healthy ? "ok" : "fault"}`;
      const motionEnabled = MS.payload?.safety?.motion_enabled === true;
      const piInputs = MS.payload?.picontrol_io?.inputs || {};
      const driveAlarm = piInputs.x_alarm === true || piInputs.y_alarm === true;
      const safetyClear = MS.online && nucleoOk && ioOk && !status.estop && !MS.payload?.safety?.stop_requested && !driveAlarm;
      const setArchitectureLive = (id, value, ok) => {
        const node = el(id);
        if (!node) return;
        node.textContent = value;
        node.className = ok ? "ok" : "fault";
      };
      setArchitectureLive("architecture-web-live", MS.online ? "ONLINE" : "OFFLINE", MS.online);
      setArchitectureLive("architecture-controller-live", MS.online ? "ONLINE" : "OFFLINE", MS.online);
      setArchitectureLive("architecture-motion-live", motionEnabled ? "ENABLED" : "DISABLED", motionEnabled);
      setArchitectureLive("architecture-nucleo-live", nucleoOk ? "ONLINE" : "OFFLINE", nucleoOk);
      setArchitectureLive("architecture-io-live", ioOk ? "ONLINE" : "OFFLINE", ioOk);
      setArchitectureLive("architecture-safety-live", safetyClear ? "CLEAR" : "INHIBITED", safetyClear);
      setText("architecture-protocol-live", `USB Serial · Protocol v${MS.payload?.nucleo?.protocol ?? "--"}`);
    }

    const alarmList = document.getElementById("alarm-page-list");
    const alarmPriority = (channel) => channel.active ? (channel.level === "fault" ? 0 : 1) : 2;
    const orderedAlarms = alarmChannels().sort((left, right) => alarmPriority(left) - alarmPriority(right));
    const alarmRecovery = (channel) => {
      if (channel.code === "ESTOP") return "Release the physical E-Stop, verify DI10/KM1 feedback, then reset alarms.";
      if (/DRV-[XY]/.test(channel.code)) return "Inspect the HBS860H fault indication and mechanics; remove the cause before resetting drive power.";
      if (/-(MIN|MAX)$/.test(channel.code)) return "Move only away from the active limit, then verify that the sensor returns CLEAR.";
      if (/-HOME$/.test(channel.code)) return `Run Home ${channel.code.charAt(0)} after all safety inputs are clear.`;
      if (/NUCLEO|USB/.test(channel.code)) return "Check USB power/cable and protocol handshake; use Reset USB Link only while motion is stopped.";
      if (/IO|CTRL/.test(channel.code)) return "Restore the communication link and review Event Log before enabling motion.";
      return "Review the source and Event Log, remove the cause, then use Reset Alarms if the condition is clear.";
    };
    if (alarmList) alarmList.innerHTML = orderedAlarms.map((channel) => `
      <article class="alarm-page-item ${channel.active ? channel.level : "clear"}">
        <i class="alarm-point-light ${channel.active ? channel.level : "clear"}" aria-hidden="true"></i>
        <div><span>${esc(channel.code)}</span><strong>${esc(channel.label)}</strong><small>${esc(channel.detail)}</small><small class="alarm-recovery"><b>RECOVERY</b> ${esc(alarmRecovery(channel))}</small></div>
        <b class="alarm-page-state">${channel.active ? (channel.level === "fault" ? "ALARM" : "WARNING") : "NORMAL"}</b>
      </article>
    `).join("");

    const flowState = document.getElementById("flow-state");
    if (flowState) {
      flowState.textContent = MS.payload?.busy ? "EXECUTING" : (ready ? "READY" : "INTERLOCKED");
      flowState.className = `page-status-chip ${ready ? "ok" : (alarmCount ? "fault" : "")}`;
    }
    const commandName = MS.payload?.active_command || "";
    const safetyClear = MS.online && !status.estop && !MS.payload?.safety?.stop_requested && alarmCount === 0;
    const selectedSlot = MS.slots[MS.visualTargetSlot || MS.selectedSlotCode || ""] || {};
    const selectedReady = slotStatus(selectedSlot) === "ready";
    const safeZ = Number(MS.config?.safe_z_mm || 0);
    const currentZ = Number(status.current_position?.z_mm || 0);
    const operationMessage = String(operation.message || "").toLowerCase();
    const setFlow = (id, state) => {
      const node = document.getElementById(id);
      if (node) node.className = `flow-node ${state}`;
    };
    setFlow("flow-controller", MS.online ? "complete" : "blocked");
    setFlow("flow-safety", safetyClear ? "complete" : "blocked");
    setFlow("flow-home-z", getAxis("z").is_homed ? "complete" : (commandName === "home_z" || (commandName === "home_all" && getOperation().active_axis === "z") ? "active" : "pending"));
    setFlow("flow-home-x", getAxis("x").is_homed ? "complete" : (commandName === "home_x" || (commandName === "home_all" && getOperation().active_axis === "x") ? "active" : "pending"));
    setFlow("flow-home-y", getAxis("y").is_homed ? "complete" : (commandName === "home_y" || (commandName === "home_all" && getOperation().active_axis === "y") ? "active" : "pending"));
    setFlow("flow-slot", selectedReady ? "complete" : "pending");
    setFlow("flow-safe-z", commandName.startsWith("goto_slot") || commandName === "dispense" ? (currentZ >= safeZ ? "complete" : "active") : "pending");
    setFlow("flow-motion", MS.payload?.busy && (commandName.startsWith("goto_slot") || commandName === "absolute_move" || commandName === "dispense") ? "active" : (ready && selectedReady ? "complete" : "pending"));
    setFlow("flow-z-target", MS.payload?.busy && (commandName.startsWith("goto_slot") || commandName === "dispense") ? "active" : "pending");
    const verifyState = selectedReady && safetyClear && allAxesHomed() ? (MS.payload?.busy ? "active" : "complete") : "pending";
    setFlow("flow-verify", verifyState);
    setFlow("flow-dispense", commandName === "dispense" ? "active" : (operationMessage.includes("completed dispense") ? "complete" : "pending"));
    setFlow("flow-complete", operationMessage.includes("completed") ? "complete" : "pending");

    const currentXYZ = AXES.map((axis) => `${axis.toUpperCase()} ${fmtPos(getAxis(axis).position_mm)}`).join(" · ");
    const targetXYZ = selectedReady ? AXES.map((axis) => `${axis.toUpperCase()} ${fmtPos(selectedSlot[`${axis}_mm`])}`).join(" · ") : "NO DATA";
    setText("flow-machine-command", `${MS.payload?.machine_state || "NO DATA"} / ${commandName || "IDLE"}`);
    setText("flow-slot-phase", `${MS.visualTargetSlot || MS.selectedSlotCode || "NO SLOT"} / ${operation.phase || "NO DATA"}`);
    setText("flow-current-xyz", currentXYZ); setText("flow-target-xyz", targetXYZ);
    setText("flow-homing-limits", AXES.map((axis) => `${axis.toUpperCase()}:${getAxis(axis).is_homed ? "H" : "!"}${getAxis(axis).head_limit || getAxis(axis).tail_limit ? "/LIMIT" : ""}`).join(" "));
    const blocked = [];
    if (status.estop) blocked.push(["E-STOP", "Release physical E-Stop and reset alarms."]);
    if (alarmCount) blocked.push(["ACTIVE ALARM", "Clear the active fault before motion."]);
    if (!MS.online) blocked.push(["CONTROLLER OFFLINE", "Restore the Controller connection."]);
    if (MS.payload?.safety?.stop_requested) blocked.push(["SOFTWARE STOP", "Reset alarms to clear the stop latch."]);
    AXES.filter((axis) => !getAxis(axis).is_homed).forEach((axis) => blocked.push([`${axis.toUpperCase()} NOT HOMED`, `Home ${axis.toUpperCase()} before absolute motion.`]));
    if (!selectedReady) blocked.push(["INVALID SLOT", "Select a slot with valid saved XYZ."]);
    if (MS.payload?.busy) blocked.push(["MACHINE BUSY", "Wait for the current operation to finish."]);
    const interlockList = el("flow-interlock-list"); const interlockState = el("flow-interlock-state");
    if (interlockList) interlockList.innerHTML = blocked.length ? blocked.map(([title, reason]) => `<div class="flow-interlock-item"><b>${esc(title)}</b><span>${esc(reason)}</span></div>`).join("") : "<div class=\"flow-interlock-clear\">✓ Machine is clear for the next permitted operation.</div>";
    if (interlockState) { interlockState.textContent = blocked.length ? `${blocked.length} BLOCKED` : "CLEAR"; interlockState.className = `page-status-chip ${blocked.length ? "fault" : "ok"}`; }
    const history = el("flow-operation-history");
    if (history) history.innerHTML = MS.events.filter((event) => ["MOTION", "COMMAND", "INTERLOCK", "MQTT"].includes(event.subsystem)).slice(0, 10).map((event) => `<li><time>${esc(eventTime(event))}</time><b>${esc(eventOutcome(event))}</b><span>${esc(sanitizeEventText(event.message))}</span></li>`).join("") || "<li>NO OPERATION HISTORY</li>";
  }

  function updateAllUI() {
    updateHeader();
    updateSafetyStrip();
    updateFooter();
    updateButtonStates();
    updateFeedOverride();
    renderMotionCommand();
    renderWorkspacePages();
  }

  function render(payload) {
    trackDashboardOperation(payload);
    updateAxisVelocity(payload);
    MS.payload = payload;
    MS.slots   = payload.slots || {};
    if (MS.validation.stage === "armed" && !payload.motion_command?.armed && !payload.busy && !MS.pending) {
      invalidateMotionWorkflow("Arm token expired — validate and arm again.");
    }

    renderAxisCards();
    renderHomingSequence();
    renderSlotTable();
    loadSelectedSlotEditor();
    renderAlarmSummary();
    renderPreview(MS.validation.plan);
    updateAllUI();

    // Alert on new errors
    if (payload.last_error && payload.last_error !== MS.lastError) {
      log(humanizeError(payload.last_error), "error", "ALARM");
      if (Date.now() > MS.silentErrorUntil) toast(humanizeError(payload.last_error), "error");
    }
    MS.lastError = payload.last_error || "";
  }

  /* ── POLLING ────────────────────────────────────────────────── */
  async function refresh() {
    const mqttRefresh = refreshMqtt();
    try {
      const payload = await apiCall("/api/status");
      if (!MS.online) log("Controller connection established", "info", "CONTROLLER");
      MS.online = true;
      MS.lastStatusAt = Date.now();
      render(payload);
    } catch (err) {
      if (MS.online) log(`Controller connection lost: ${err.message}`, "error", "CONTROLLER");
      MS.online = false;
      updateAllUI();
    }
    await mqttRefresh;
  }

  async function refreshMqtt() {
    if (MS.mqttPollPending) return;
    MS.mqttPollPending = true;
    try {
      MS.mqtt = await apiCall("/api/mqtt/status", "GET", undefined, 4000);
    } catch (err) {
      MS.mqtt = {
        enabled: true,
        connected: false,
        state: "API ERROR",
        last_error: err.message,
        timestamp: new Date().toISOString(),
        messages: MS.mqtt?.messages || [],
      };
    } finally {
      MS.mqttPollPending = false;
      renderMqttMonitor();
    }
  }

  async function controlMqtt(action) {
    if (MS.mqttControlPending) return;
    MS.mqttControlPending = true;
    renderMqttMonitor();
    try {
      MS.mqtt = await apiCall("/api/mqtt/control", "POST", { action }, 10000);
      renderMqttMonitor();
      toast(`MQTT ${action === "connect" ? "connection started" : "disconnected"}.`, action === "connect" ? "ok" : "");
      log(`MQTT ${action} requested from HMI`, "info", "MQTT");
    } catch (err) {
      toast(`MQTT CONTROL FAILED — ${err.message}`, "error");
      log(`MQTT ${action} failed: ${err.message}`, "error", "MQTT");
    } finally {
      MS.mqttControlPending = false;
      await refreshMqtt();
    }
  }

  async function loadConfig() {
    try {
      MS.config = await apiCall("/api/config");
      // Update axis input maxima from config
      const axisCfg = MS.config.axes || {};
      AXES.forEach((a) => {
        const max = axisCfg[a]?.max_travel_mm;
        if (max) {
          const inp = el(`move-${a}`);
          if (inp) inp.setAttribute("max", max);
        }
      });
      // Rebuild homing sequence panel with actual order
      renderHomingSequence();
      renderWorkspacePages();
      updateFeedOverride();
      renderConfigurationEditor(true);
      loadMotorTestAxisConfig();
      log("Machine configuration loaded", "info", "SYSTEM");
    } catch (err) {
      log(`Config load failed: ${err.message}`, "error", "SYSTEM");
    }
  }

  /* ── BIND ALL EVENTS ────────────────────────────────────────── */
  function organizeWorkspacePanels() {
    const motionPage = $('[data-view-page="motion"]');
    const diagnosticsPage = $('[data-view-page="diagnostics"]');
    const axisPanel = $(".rpz-status");
    const jogPanel = $(".rpz-jog");
    const slotEditor = $(".rpz-slot-editor");
    const liveDiagnostics = $(".rpz-log");
    const homeZone = motionPage?.querySelector(":scope > .wz-top");
    if (motionPage && axisPanel) {
      axisPanel.classList.add("motion-axis-panel");
      motionPage.prepend(axisPanel);
    }
    if (motionPage && jogPanel) {
      jogPanel.classList.add("motion-jog-panel");
      let primaryControls = motionPage.querySelector(":scope > .motion-primary-controls");
      if (!primaryControls) {
        primaryControls = document.createElement("section");
        primaryControls.className = "motion-primary-controls";
        primaryControls.setAttribute("aria-label", "Homing and manual jog controls");
        if (homeZone) motionPage.insertBefore(primaryControls, homeZone);
        else motionPage.prepend(primaryControls);
      }
      if (homeZone) primaryControls.append(homeZone);
      primaryControls.append(jogPanel);
    }
    if (motionPage && slotEditor) {
      slotEditor.classList.add("motion-slot-panel");
      motionPage.append(slotEditor);
    }
    if (diagnosticsPage && liveDiagnostics) {
      liveDiagnostics.classList.add("diagnostics-live-log");
      diagnosticsPage.append(liveDiagnostics);
    }
    const diagnosticsTabs = $('[data-view-page="diagnostics"] .setup-tabs');
    ["io-status", "alarms", "events", "flow", "sequence-monitor", "architecture"].forEach((view) => {
      const page = $(`[data-view-page="${view}"]`);
      if (page && diagnosticsTabs && !page.querySelector(".context-tabs")) {
        const nav = diagnosticsTabs.cloneNode(true);
        nav.classList.add("context-tabs");
        page.prepend(nav);
      }
    });
    const setupTabs = $('[data-view-page="configuration"] .setup-tabs');
    const commissioningPage = $('[data-view-page="motor-test"]');
    if (commissioningPage && setupTabs && !commissioningPage.querySelector(".context-tabs")) {
      const nav = setupTabs.cloneNode(true);
      nav.classList.add("context-tabs");
      commissioningPage.prepend(nav);
    }
  }

  function stopManualJog(sendControllerStop = true) {
    if (MS.manualJog.holdTimer) {
      clearTimeout(MS.manualJog.holdTimer);
      MS.manualJog.holdTimer = null;
    }
    if (!MS.manualJog.active && !MS.manualJog.isHolding) return;
    const wasHolding = MS.manualJog.isHolding;
    MS.manualJog.active = false;
    MS.manualJog.isHolding = false;
    MS.manualJog.token += 1;
    if (MS.manualJog.button) {
      MS.manualJog.button.classList.remove("running");
      MS.manualJog.button = null;
    }
    const bypassHome = Boolean($("#jog-allow-unhomed")?.checked);
    setText("jog-status-text", allAxesHomed() ? "READY" : (bypassHome ? "UNHOMED JOG PERMITTED" : "HOME REQUIRED"));
    if (sendControllerStop && wasHolding) {
      apiCall("/api/motion/controlled-stop", "POST", {}, 2500).catch(() => {});
    }
  }

  let beginManualJog;
  let endManualJog;

  function bind() {
    /* --- Workspace navigation --- */
    workspaceRouter.start();

    /* --- Emergency Stop --- */
    el("stop-button").addEventListener("click", () => {
      command("Emergency stop", "/api/stop", undefined, { isStop: true, noCheck: true });
    });

    /* --- Reset Alarm --- */
    el("clear-alarm").addEventListener("click", () => {
      command("Reset alarms", "/api/clear-alarm", undefined, { isStop: true, noCheck: true });
    });

    /* --- Hold-to-Run Manual Jog Engine --- */
    beginManualJog = function (axis, dir, btn, event) {
      if (btn && btn.disabled) return;
      if (!canJogAxis(axis)) {
        toast(`${axis.toUpperCase()} cannot jog: not homed or motion inhibited`, "warn");
        return;
      }

      if (event && event.pointerId != null && btn) {
        try { btn.setPointerCapture(event.pointerId); } catch (_) {}
      }

      stopManualJog();
      const token = ++MS.manualJog.token;
      MS.manualJog.active = true;
      MS.manualJog.button = btn;
      MS.manualJog.isHolding = false;
      if (btn) btn.classList.add("running");

      const HOLD_DELAY_MS = 200;
      MS.manualJog.holdTimer = setTimeout(async () => {
        MS.manualJog.holdTimer = null;
        if (!MS.manualJog.active || MS.manualJog.token !== token) return;
        MS.manualJog.isHolding = true;
        setText("jog-status-text", `JOGGING ${axis.toUpperCase()} ${dir === "1" ? "+" : "−"}...`);
        try {
          if (MS.manualJog.active && MS.manualJog.token === token && canJogAxis(axis)) {
            const payload = buildJogPayload(axis, dir, true);
            await apiCall("/api/jog", "POST", payload, 650000);
          }
        } catch (err) {
          if (MS.manualJog.token === token) {
            toast(humanizeError(err.message), "error");
          }
        } finally {
          if (MS.manualJog.token === token) {
            stopManualJog(false);
            refresh().catch(() => {});
          }
        }
      }, HOLD_DELAY_MS);
    };

    endManualJog = function (axis, dir, btn) {
      if (!MS.manualJog.active) return;
      if (MS.manualJog.holdTimer) {
        // Released before hold threshold -> single step move
        clearTimeout(MS.manualJog.holdTimer);
        MS.manualJog.holdTimer = null;
        stopManualJog();
        command(`Jog ${axis.toUpperCase()} ${dir === "1" ? "+" : "−"}${MS.selectedJogStep} mm`,
          "/api/jog", buildJogPayload(axis, dir, false), { silent: true });
      } else {
        // Was in hold continuous mode -> stop
        stopManualJog();
      }
    };

    /* --- Jog step presets --- */
    $$(".step-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        MS.selectedJogStep = Number(btn.dataset.step);
        $$(".step-btn").forEach((b) => b.classList.toggle("active", b === btn));
        setText("jog-step-display", fmtSpd(MS.selectedJogStep));
        // Keep hidden input in sync (for any legacy code reading it)
        if (el("jog-step")) el("jog-step").value = MS.selectedJogStep;
      });
    });

    /* --- Jog speed presets --- */
    $$(".speed-preset").forEach((btn) => {
      btn.addEventListener("click", () => {
        AXES.forEach((axis) => { MS.axisSpeeds[axis] = Number(btn.dataset.speed); });
        MS.selectedJogSpeed = Number(btn.dataset.speed);
        try { localStorage.setItem("narit.axisSpeeds", JSON.stringify(MS.axisSpeeds)); } catch (_) {}
        $$(".speed-preset").forEach((b) => b.classList.toggle("active", b === btn));
        syncAxisSpeedBanks();
        if (el("move-speed")) el("move-speed").value = MS.selectedJogSpeed;
        updateFeedOverride();
        // Also save to controller
        command(`Set coordinated speed ${MS.selectedJogSpeed} mm/s`, "/api/speed",
          { speed_mm_s: MS.selectedJogSpeed }, { isStop: true, noCheck: true });
      });
    });


    /* --- Feed override presets --- */
    $$(".fo-preset-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        MS.feedOverridePct = Number(btn.dataset.fo);
        if (MS.validation.stage !== "idle") invalidateMotionWorkflow("Feed override changed — validate again.");
        updateFeedOverride();
      });
    });

    document.addEventListener("input", (event) => {
      const control = event.target.closest?.("[data-axis-speed-range], [data-axis-speed-number]");
      if (!control) return;
      setAxisSpeed(control.dataset.axisSpeedRange || control.dataset.axisSpeedNumber, control.value);
    });
    $$('[data-setup-tab]').forEach((button) => {
      button.addEventListener('click', () => {
        if (MS.currentView !== "configuration") switchWorkspace("configuration");
        applySetupTab(button.dataset.setupTab);
      });
    });

    el("motor-test-arm").addEventListener("click", async () => {
      const result = await command("Arm Motor Test Mode", "/api/maintenance/motor-test", { action: "arm" }, { isStop: true, noCheck: true });
      if (result) {
        MS.keyboardJogEnabled = false;
        el("jog-keyboard-enable").checked = false;
        setText("motor-test-result", "TEST MODE ARMED — press and hold a Test Jog button to rotate; release to stop.");
      }
    });
    el("motor-test-cancel").addEventListener("click", async () => {
      stopMotorTestJog("Motor Test Mode cancelled. Pulse output is disabled.");
      const result = await command("Cancel Motor Test Mode", "/api/maintenance/motor-test", { action: "cancel" }, { isStop: true, noCheck: true });
      if (result) {
        setText("motor-test-result", "Motor Test Mode cancelled. Pulse output is disabled.");
      }
    });
    el("motor-test-start").addEventListener("click", () => {
      const parameters = motorTestParameters();
      runMotorTestPulse(parameters.axis, parameters.direction);
    });
    $$("[data-motor-test-jog]").forEach((button) => {
      const beginJog = (event) => {
        event.preventDefault();
        if (button.disabled) return;
        const [axis, direction] = button.dataset.motorTestJog.split(":");
        if (event.pointerId != null) button.setPointerCapture?.(event.pointerId);
        startMotorTestJog(axis, direction, button);
      };
      button.addEventListener("pointerdown", beginJog);
      button.addEventListener("pointerup", () => stopMotorTestJog());
      button.addEventListener("pointercancel", () => stopMotorTestJog("JOG CANCELLED — pulse output stopped."));
      button.addEventListener("lostpointercapture", () => stopMotorTestJog());
      button.addEventListener("keydown", (event) => {
        if ((event.key === "Enter" || event.key === " ") && !event.repeat) beginJog(event);
      });
      button.addEventListener("keyup", (event) => {
        if (event.key === "Enter" || event.key === " ") stopMotorTestJog();
      });
      button.addEventListener("contextmenu", (event) => event.preventDefault());
    });
    // Goto Limit buttons — single click, runs full stroke
    $$("[data-goto-axis]").forEach((button) => {
      button.addEventListener("click", () => {
        const axis  = button.dataset.gotoAxis;
        const limit = button.dataset.gotoLimit;
        if (!axis || !limit) return;
        if (motorTestGoto.active) {
          stopMotorTestGoto("GOTO ABORTED by user.");
        } else {
          runGotoLimit(axis, limit, button);
        }
      });
    });
    window.addEventListener("blur", () => {
      stopMotorTestJog("WINDOW LOST FOCUS — pulse output stopped.");
      stopMotorTestGoto("WINDOW LOST FOCUS — goto stopped.");
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) { stopMotorTestJog("PAGE HIDDEN — pulse output stopped."); stopMotorTestGoto("PAGE HIDDEN — goto stopped."); }
    });
    el("motor-test-open-config").addEventListener("click", () => switchWorkspace("configuration"));
    el("motor-test-axis").addEventListener("change", () => {
      loadMotorTestAxisConfig();
      renderMotorTest();
    });
    ["motor-test-direction", "motor-test-frequency", "motor-test-pulses", "motor-test-steps-rev", "motor-test-microsteps", "motor-test-pitch"].forEach((id) => {
      el(id)?.addEventListener("input", updateMotorTestCalculations);
      el(id)?.addEventListener("change", updateMotorTestCalculations);
    });
    el("motor-test-reset-alarm")?.addEventListener("click", () => {
      command("Reset alarms", "/api/clear-alarm", undefined, { isStop: true, noCheck: true });
    });
    $$(".quick-preset-chips button").forEach((chip) => {
      chip.addEventListener("click", () => {
        const parent = chip.closest(".quick-preset-chips");
        const targetId = parent?.dataset.targetInput;
        const targetInput = el(targetId);
        if (targetInput) {
          targetInput.value = chip.dataset.val;
          parent.querySelectorAll(".chip-btn").forEach((c) => c.classList.toggle("active", c === chip));
          updateMotorTestCalculations();
        }
      });
    });


    const configurationPage = document.querySelector('[data-view-page="configuration"]');
    const markConfigurationDirty = (event) => {
      if (!event.target.matches("[data-config-axis], [data-pin-group], [data-travel-field]")) return;
      if (event.target.dataset.pinGroup === "digital_inputs" && event.target.dataset.pinField === "pull_up") {
        const activeLogic = document.querySelector(`[data-pin-group="digital_inputs"][data-pin-name="${event.target.dataset.pinName}"][data-pin-field="active_high"]`);
        if (activeLogic) activeLogic.checked = !event.target.checked;
      }
      MS.configDirty = true;
      updateConfigurationDerived();
      updateConfigurationState();
    };
    configurationPage.addEventListener("input", markConfigurationDirty);
    configurationPage.addEventListener("change", markConfigurationDirty);
    configurationPage.addEventListener("input", (event) => {
      const card = event.target.closest?.("[data-travel-axis]");
      if (card) {
        updateTravelCard(card);
      }
    });
    configurationPage.addEventListener("click", (event) => {
      const button = event.target.closest?.("[data-apply-travel]");
      if (!button) return;
      const axis = button.dataset.applyTravel;
      const card = button.closest("[data-travel-axis]");
      const usable = updateTravelCard(card);
      const maxInput = document.querySelector(`[data-config-axis="${axis}"][data-config-field="max_travel_mm"]`);
      if (!maxInput || !Number.isFinite(usable) || usable <= 0) {
        updateConfigurationState(`${axis.toUpperCase()}: measured travel must be greater than the safety margin.`);
        return;
      }
      maxInput.value = usable.toFixed(3);
      MS.configDirty = true;
      updateConfigurationDerived();
      updateConfigurationState(`${axis.toUpperCase()}: Maximum Travel staged at ${usable.toFixed(3)} mm. SAVE and APPLY are required; no motion was commanded.`);
    });
    el("configuration-reset").addEventListener("click", () => renderConfigurationEditor(true));
    el("configuration-save").addEventListener("click", saveControllerConfiguration);
    el("configuration-apply").addEventListener("click", applyControllerConfiguration);

    el("dashboard-slot-grid").addEventListener("click", (event) => {
      const slotButton = event.target.closest("[data-dashboard-slot]");
      if (!slotButton) return;
      MS.dashboardSelectedSlot = slotButton.dataset.dashboardSlot;
      renderDashboard();
    });

    /* --- Event log filter --- */
    $$(".evt-filter-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        MS.logFilter = btn.dataset.filter;
        $$(".evt-filter-btn").forEach((b) => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-pressed", String(b === btn));
        });
        renderEventLog();
      });
    });

    $$('[data-homing-shortcut]').forEach((button) => button.addEventListener("click", openHomingControls));

  }

  /* ── INIT ───────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", () => {
    try {
      const saved = JSON.parse(localStorage.getItem("narit.axisSpeeds") || "{}");
      AXES.forEach((axis) => {
        if (Number.isFinite(Number(saved[axis])) && Number(saved[axis]) > 0) MS.axisSpeeds[axis] = Number(saved[axis]);
      });
    } catch (_) {}
    organizeWorkspacePanels();
    renderAxisSpeedBanks();
    pageControllers.register("io-status", window.NaritIOPageController.create({
      state: MS,
      render: renderIOStatusPage,
      refresh,
      toast,
      onError: (error) => console.error("[HMI] I/O refresh failed", error),
    }));
    pageControllers.register("events", window.NaritEventsPageController.create({
      state: MS,
      render: renderEventLog,
      exportCsv: exportFilteredEventsCsv,
    }));
    pageControllers.register("flow", window.NaritFlowPageController.create({ state: MS }));
    pageControllers.register("mqtt", window.NaritMqttPageController.create({
      control: controlMqtt,
      render: renderMqttMonitor,
    }));
    pageControllers.register("alarms", window.NaritAlarmsPageController.create({
      reset: () => command(
        "Reset alarms",
        "/api/clear-alarm",
        undefined,
        { isStop: true, noCheck: true },
      ),
    }));
    pageControllers.register("system-control", window.NaritSystemControlPageController.create({
      onDisableMotion: () => runSystemAction("/api/system/motion/disable", "Motion disabled; all axes stopped and disarmed."),
      onEnableMotion: () => runSystemAction("/api/system/motion/enable", "Motion enabled for future validated commands."),
      onResetNucleoLink: () => {
        if (window.confirm("Stop and disarm all axes, then reset the NUCLEO USB link and handshake? This is not a physical NRST reset.")) {
          return runSystemAction("/api/system/nucleo/reset-link", "NUCLEO USB link reset; motion remains disabled.");
        }
        return undefined;
      },
      onResetDrivePower: () => {
        const warning = "Reset X/Y drive power now? All axes will stop, NUCLEO will disarm, KM1 will remove 60 V for 3 seconds, and X/Y homing references will be cleared.";
        if (window.confirm(warning)) {
          return runSystemAction("/api/system/drives/reset-power", "X/Y drive power reset complete. Motion remains disabled; Home X/Y before use.");
        }
        return undefined;
      },
      onCutDrivePower: () => {
        if (window.confirm("Cut 60 V power to X/Y drives and keep it OFF? All axes will stop and X/Y homing references will be cleared.")) {
          return runSystemAction("/api/system/drives/cut-power", "X/Y drive power is OFF. Motion remains disabled.");
        }
        return undefined;
      },
      onRestoreDrivePower: () => {
        if (window.confirm("Restore 60 V power to X/Y drives through KM1? Motion will remain disabled and X/Y must be homed before use.")) {
          return runSystemAction("/api/system/drives/restore-power", "X/Y drive power restored. Motion remains disabled; Home X/Y before use.");
        }
        return undefined;
      },
      onError: (error) => console.error("[HMI] System Control action failed", error),
    }));
    pageControllers.register("slots", window.NaritSlotsPageController.create({
      render: renderSlotTable,
      onCoordinate: (code, axis, value) => {
        const slot = MS.slots[code] || {};
        MS.slotDrafts[code] ||= {
          x_mm: Number(slot.x_mm || 0),
          y_mm: Number(slot.y_mm || 0),
          z_mm: Number(slot.z_mm || 0),
        };
        MS.slotDrafts[code][`${axis}_mm`] = Number(value);
      },
      onSave: async (code) => {
        const payload = slotPayloadFromValues(code, MS.slotDrafts[code] || MS.slots[code] || {});
        if (!payload) return;
        const result = await command(`Save slot ${code} position`, `/api/slots/${code}`, payload,
          { isStop: true, noCheck: true });
        if (result) delete MS.slotDrafts[code];
      },
      onSelect: selectSlotFromManager,
      onGoto: (code) => {
        const slot = MS.slots[code] || {};
        const confirmation = [
          `${slotSequenceEnabled() ? "Run sequence" : "Move gantry"} to Slot ${code}?`,
          `Target: X ${fmtPos(slot.x_mm)} · Y ${fmtPos(slot.y_mm)} · Z ${fmtPos(slot.z_mm)} mm`,
          `Speed: ${fmtSpd(targetSpeedPayload().speed_mm_s)} mm/s`,
          slotSequenceEnabled()
            ? "Sequence: X → Y → Z → hold 3 s → Home Z → Home Y → Home X."
            : "Confirm the travel area is clear before continuing.",
          "Confirm the travel area is clear before continuing.",
        ].join("\n");
        if (!window.confirm(confirmation)) return;
        selectSlotFromManager(code);
        MS.visualTargetSlot = code;
        command(slotMotionLabel(code), slotMotionEndpoint(code), targetSpeedPayload(), {
          requireHome: true,
          timeoutMs: 600000,
        });
      },
      onDispense: (code) => {
        selectSlotFromManager(code);
        MS.visualTargetSlot = code;
        command(`Dispense slot ${code}`, "/api/start",
          { slot: code, ...targetSpeedPayload() }, { requireHome: true });
      },
      onTeach: async (code) => {
        MS.selectedSlotCode = code;
        const result = await command(`Save current position to slot ${code}`, `/api/slots/${code}/save-current`, undefined,
          { requireHome: true });
        if (result) delete MS.slotDrafts[code];
      },
      onError: (error) => console.error("[HMI] Slot table action failed", error),
    }));
    const selectedSlotControls = window.NaritSelectedSlotController.create({
      onSelectedChange: changeSelectedSlot,
      onLoadTarget: loadSelectedSlotTarget,
      onValidate: validateSelectedSlotTarget,
      onSequenceToggle: setSlotSequenceMode,
      onSelectedGoto: gotoSelectedSlot,
      onError: (error) => console.error("[HMI] Selected Slot action failed", error),
    });
    const motionTravelControls = window.NaritMotionTravelController.create({
      onHomeAll: homeAllAxes,
      onHomeAxis: homeAxis,
      onStop: stopTravelMotion,
      onResetInterlock: resetTravelInterlock,
      onMoveToLimit: moveAxisToLimit,
      onMoveToPosition: moveAxisToPosition,
      onError: (error) => console.error("[HMI] Motion travel action failed", error),
    });
    const motionTargetControls = window.NaritMotionTargetController.create({
      onLoadCurrent: loadCurrentManualTarget,
      onLoadSelectedSlot: loadSelectedSlotManualTarget,
      onValidate: () => validateMove(true),
      onPreview: () => previewMove(true),
      onArm: () => armMove(true),
      onExecute: () => executeArmedMotion("Execute validated move"),
      onControlledStop: () => command("Controlled stop", "/api/motion/controlled-stop", undefined, { isStop: true, noCheck: true }),
      onAbort: () => command("Abort motion", "/api/motion/abort", undefined, { isStop: true, noCheck: true }),
      onTargetChanged: () => {
        if (MS.validation.stage !== "idle") invalidateMotionWorkflow();
        updateFeedOverride();
      },
      onError: (error) => console.error("[HMI] Motion target action failed", error),
    });
    const motionJogSafety = window.NaritMotionJogSafetyController.create({
      onStop: stopManualJog,
      onBegin: (...args) => beginManualJog?.(...args),
      onEnd: (...args) => endManualJog?.(...args),
      isKeyboardEnabled: () => MS.keyboardJogEnabled,
      onKeyboardToggle: (enabled) => {
        MS.keyboardJogEnabled = enabled;
        toast(`Keyboard jog ${enabled ? "enabled" : "disabled"}.`, enabled ? "ok" : "");
      },
      onAllowUnhomedChanged: updateButtonStates,
    });
    pageControllers.register("motion", {
      mount: () => {
        const cleanupSelectedSlot = selectedSlotControls.mount();
        const cleanupTravel = motionTravelControls.mount();
        const cleanupTarget = motionTargetControls.mount();
        const cleanupJogSafety = motionJogSafety.mount();
        return () => {
          cleanupJogSafety();
          cleanupTarget();
          cleanupTravel();
          cleanupSelectedSlot();
        };
      },
    });
    const visualizationControls = window.NaritVisualizationPageController.create({
      onSelect: selectVisualizationSlot,
      onCoordinateInput: updateVisualizationCoordinateDraft,
      onLoadCurrent: loadCurrentIntoVisualSlot,
      onSave: saveVisualSlotV32,
      onLoadTarget: loadVisualSlotTarget,
      onHomeAll: () => command("Home all axes from visualization", "/api/home/all", undefined, { timeoutMs: 300000 }),
      onGoto: gotoVisualSlot,
      onPreview: previewVisualSlot,
      onSendToMotion: sendVisualTargetToMotion,
      onEdit: () => setVisualEditMode(true),
      onCancelEdit: () => setVisualEditMode(false),
      onError: (error) => console.error("[HMI] Visualization action failed", error),
    });
    const demoControls = window.NaritDemoPageController.create({
      onConfigure: () => demoAction("configure", demoPayload()),
      onValidate: () => demoAction("validate"),
      onArm: () => demoAction("arm"),
      onStart: () => {
        if (window.confirm("Start the bounded motion-only Demo Slot Sampling sequence? Confirm the machine area is clear.")) {
          return demoAction("start", { arm_token: MS.demoArmToken });
        }
        return undefined;
      },
      onPause: () => demoAction("pause"),
      onResume: () => demoAction("resume"),
      onStop: () => demoAction("stop"),
      onRefresh: () => loadDemoHistory(true),
      onParametersChanged: invalidateDemoConfiguration,
      onError: (error) => console.error("[HMI] Demo action failed", error),
    });
    pageControllers.register("visualization", {
      mount: () => {
        const cleanupControls = visualizationControls.mount();
        const cleanupDemo = demoControls.mount();
        loadDemoHistory();
        const historyTimer = window.setInterval(() => loadDemoHistory(), 5000);
        return () => {
          window.clearInterval(historyTimer);
          cleanupDemo();
          cleanupControls();
        };
      },
    });
    bind();
    switchWorkspace(location.hash.slice(1) || "motion", false);
    log("Industrial motion HMI initialised", "info", "SYSTEM");
    log("Connecting to controller...", "info", "CONTROLLER");
    loadConfig();
    refresh();
    setInterval(refresh, POLL_INTERVAL_MS);
    setInterval(() => {
      updateHeader();
      updateFooter();
    }, 1000);
  });

})();
