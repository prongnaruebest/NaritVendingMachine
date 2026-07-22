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
  const MS = {
    // Connectivity
    online: false,
    pending: false,

    // From /api/status payload
    payload: null,
    config: null,
    slots: {},

    // Event log
    events: [],
    lastError: "",

    // Validation state
    validation: { valid: false, stage: "idle", message: "Target not validated.", plan: null, axes: {}, armToken: null },

    // UI state
    feedOverridePct: 100,   // 0–100, displayed
    selectedJogStep: 1.0,
    selectedJogSpeed: 15.0,
    keyboardJogEnabled: false,
    selectedSlotCode: "",
    visualTargetSlot: "",
    slotEditorDirty: false,
    visualEditorDirty: false,
    visualEditMode: false,
    visualPreview: null,
    visualOriginalSlot: null,
    lastStatusAt: 0,
    slotDrafts: {},
    dashboardSelectedSlot: "1",
    dashboardOperationStartedAt: null,
    dashboardTrackedCommand: "",
    dashboardWasBusy: false,
    silentErrorUntil: 0,
    logFilter: "all",
    currentView: "motion",
  };

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

  /* ── STATE ACCESSORS ────────────────────────────────────────── */
  function getStatus() { return MS.payload?.status || {}; }
  function getOperation() { return MS.payload?.operation || {}; }
  function getAxis(axis) { return getStatus()[axis] || {}; }

  function allAxesHomed() {
    return AXES.every((a) => Boolean(getAxis(a).is_homed));
  }

  function activeAlarmCount() {
    return alarmChannels().filter((channel) => channel.active && channel.level === "fault").length;
  }

  function alarmChannels() {
    const status = getStatus();
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
    return channels;
  }

  /* ── DERIVED MOTION PERMISSION ──────────────────────────────── */
  function motionInhibitReason(requireHome = false) {
    const status = getStatus();
    if (!MS.online)                           return "Controller offline — reconnecting...";
    if (status.estop)                         return "MOTION LOCKED — Emergency stop active";
    if (MS.payload?.safety?.stop_requested)   return "MOTION LOCKED — reset alarms before continuing";
    if (MS.pending || MS.payload?.busy)       return "Another command is executing";
    if (requireHome && !allAxesHomed()) {
      const first = AXES.find((a) => !getAxis(a).is_homed);
      return `${first?.toUpperCase() ?? "Axis"} not homed — home all axes first`;
    }
    return "";
  }

  function canJogAxis() { return motionInhibitReason(false) === ""; }
  function canExecuteMove() { return MS.validation.valid && MS.validation.stage === "armed" && motionInhibitReason(true) === ""; }
  function canHomeAxis() { return motionInhibitReason(false) === ""; }

  /* ── SLOT STATUS ────────────────────────────────────────────── */
  function slotStatus(slot) {
    const hasProduct = Boolean(slot.product_name);
    const hasCoords = [slot.x_mm, slot.y_mm, slot.z_mm].some((v) => Number(v) !== 0);
    if (!hasProduct && !hasCoords) return "empty";
    return "ready";
  }

  /* ── API LAYER ──────────────────────────────────────────────── */
  async function apiCall(path, method = "GET", body, timeoutMs = 8000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      const responseText = await res.text();
      let data = {};
      if (responseText) {
        try {
          data = JSON.parse(responseText);
        } catch {
          throw new Error(res.ok ? "Controller returned an invalid response" : `HTTP ${res.status}`);
        }
      }
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      return data;
    } finally {
      clearTimeout(timer);
    }
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
    MS.events.unshift({ at: new Date(), message, level, subsystem });
    MS.events = MS.events.slice(0, 200);
    renderEventLog();
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
    if (pageLog) pageLog.innerHTML = markup;
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
    if (!opts.noCheck && !motionAllowed(opts.requireHome)) {
      const reason = motionInhibitReason(opts.requireHome ?? false);
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
    AXES.forEach((a) => {
      const v = el(`move-${a}`)?.value;
      if (v !== "" && v !== null && v !== undefined) body[`${a}_mm`] = Number(v);
    });
    const spd = el("target-speed")?.value;
    const time = el("target-duration")?.value;
    const timeout = el("move-timeout")?.value;
    const acceleration = el("move-acceleration")?.value;
    const deceleration = el("move-deceleration")?.value;
    if (spd) body.speed_mm_s = Number(spd);
    if (time) body.time_s = Number(time);
    if (timeout) body.timeout_s = Number(timeout);
    if (acceleration) body.acceleration_mm_s2 = Number(acceleration);
    if (deceleration) body.deceleration_mm_s2 = Number(deceleration);
    // Apply feed override
    if (body.speed_mm_s) {
      body.speed_mm_s = body.speed_mm_s * (MS.feedOverridePct / 100);
    }
    return body;
  }

  function buildJogPayload(axis, direction) {
    const body = {
      axis,
      distance_mm: MS.selectedJogStep * Number(direction),
    };
    const spd = MS.selectedJogSpeed * (MS.feedOverridePct / 100);
    if (spd > 0) body.speed_mm_s = spd;
    const jogTime = el("jog-time")?.value;
    if (jogTime) body.time_s = Number(jogTime);
    return body;
  }

  function targetSpeedPayload() {
    const body = {};
    const spd = el("target-speed")?.value || el("move-speed")?.value;
    const time = el("target-duration")?.value;
    if (spd) body.speed_mm_s = Number(spd) * (MS.feedOverridePct / 100);
    if (time) body.time_s = Number(time);
    return body;
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
    const timeoutSeconds = Number(el("move-timeout")?.value || 30);
    const result = await command(label, "/api/motion/execute", {
      arm_token: MS.validation.armToken,
      request_id: requestId,
    }, { requireHome: true, timeoutMs: Math.max(15000, (timeoutSeconds + 10) * 1000) });
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
      const programmedSpeed = Number(el("target-speed")?.value || 0);
      const effectiveSpeed = axisPlan?.speed_mm_s;
      setText(`axis-speed-${a}`, programmedSpeed > 0 ? `${fmtSpd(programmedSpeed)} / ${effectiveSpeed == null ? "--" : fmtSpd(effectiveSpeed)}` : "-- / --");
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

    container.innerHTML = homeOrder.map((axis, idx) => {
      const phase = homing[axis] || "not_homed";
      const axisData = getAxis(axis);
      const effectivePhase =
        phase === "not_homed" && axisData.is_homed ? "passed" :
        phase === "not_homed" ? "not_homed" : phase;

      const statusText =
        effectivePhase === "passed"    ? "HOMED ✓" :
        effectivePhase === "searching" ? "SEARCHING" :
        effectivePhase === "backoff"   ? "BACKOFF" :
        effectivePhase === "completed" ? "COMPLETED" :
        effectivePhase === "failed"    ? "FAILED ✗" :
        effectivePhase === "waiting"   ? "QUEUED" :
        "NOT HOMED";

      return `
        <div class="home-seq-step ${effectivePhase}" aria-label="${axis.toUpperCase()} axis homing: ${statusText}">
          <div class="home-seq-num">${idx + 1}</div>
          <div class="home-seq-axis">${axis.toUpperCase()} Axis</div>
          <div class="home-seq-status">${statusText}</div>
        </div>
      `;
    }).join("");
  }

  /* ── RENDER: SLOT TABLE ─────────────────────────────────────── */
  function renderSlotTable() {
    const search = el("slot-search")?.value.trim().toLowerCase() ?? "";
    const filter = el("slot-filter")?.value ?? "all";

    const entries = Object.entries(MS.slots)
      .sort(([a], [b]) => Number(a) - Number(b))
      .filter(([code, slot]) => {
        const derived = slotStatus(slot);
        const matchFilter = filter === "all" || filter === derived ||
          (filter === "configured" && derived !== "empty");
        const matchSearch = !search ||
          String(code).includes(search) ||
          String(slot.product_name || "").toLowerCase().includes(search);
        return matchFilter && matchSearch;
      });

    const tbody = el("slot-grid");
    if (!tbody) return;

    const canMove = motionAllowed(true);
    const canEdit = MS.online && !MS.pending && !MS.payload?.busy;

    tbody.innerHTML = entries.map(([code, slot]) => {
      const derived = slotStatus(slot);
      const productName = slot.product_name || "EMPTY";
      const canDispense = derived !== "empty" && canMove;
      const draft = MS.slotDrafts[code] || slot;
      return `
        <tr>
          <td class="mono">${esc(code)}</td>
          <td><span class="slot-badge ${derived}">${derived.toUpperCase()}</span></td>
          ${AXES.map((axis) => `<td><div class="slot-coordinate-input"><input type="number" min="0" step="0.1" value="${esc(draft[`${axis}_mm`] ?? 0)}" data-slot-coordinate="${esc(code)}" data-slot-axis="${axis}" ${canEdit ? "" : "disabled"}><span>mm</span></div></td>`).join("")}
          <td>
            <div class="slot-action-cell">
              <button class="btn-slot-save" data-slot-update="${esc(code)}" ${canEdit ? "" : "disabled"}>SAVE</button>
              <button class="btn-secondary" data-slot-teach="${esc(code)}" ${canMove ? "" : "disabled"}>CURRENT</button>
              <button class="btn-slot-goto" data-slot-goto="${esc(code)}"
                      ${canMove ? "" : "disabled"}
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

    $$('[data-slot-coordinate]').forEach((input) => {
      input.addEventListener("input", () => {
        const code = input.dataset.slotCoordinate;
        const slot = MS.slots[code] || {};
        MS.slotDrafts[code] ||= {
          x_mm: Number(slot.x_mm || 0),
          y_mm: Number(slot.y_mm || 0),
          z_mm: Number(slot.z_mm || 0),
        };
        MS.slotDrafts[code][`${input.dataset.slotAxis}_mm`] = Number(input.value);
      });
    });

    $$('[data-slot-update]').forEach((btn) => {
      btn.addEventListener("click", async () => {
        const code = btn.dataset.slotUpdate;
        const payload = slotPayloadFromValues(code, MS.slotDrafts[code] || MS.slots[code] || {});
        if (!payload) return;
        const result = await command(`Save slot ${code} position`, `/api/slots/${code}`, payload,
          { isStop: true, noCheck: true });
        if (result) delete MS.slotDrafts[code];
      });
    });

    // Bind slot action buttons
    $$("[data-slot-goto]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const code = btn.dataset.slotGoto;
        MS.visualTargetSlot = code;
        command(`Go to slot ${code}`, `/api/slots/${code}/goto`, targetSpeedPayload(), { requireHome: true });
      });
    });
    $$("[data-slot-dispense]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const code = btn.dataset.slotDispense;
        MS.visualTargetSlot = code;
        command(`Dispense slot ${code}`, "/api/start",
          { slot: code, ...targetSpeedPayload() }, { requireHome: true });
      });
    });
    $$("[data-slot-teach]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const code = btn.dataset.slotTeach;
        MS.selectedSlotCode = code;
        const result = await command(`Save current position to slot ${code}`, `/api/slots/${code}/save-current`, undefined,
          { requireHome: true });
        if (result) delete MS.slotDrafts[code];
      });
    });
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

  /* ── RENDER: ALARM SUMMARY ──────────────────────────────────── */
  function renderAlarmSummary() {
    const node = el("alarm-summary");
    if (!node) return;
    const active = alarmChannels().filter((channel) => channel.active && channel.level === "fault");
    if (!active.length) {
      node.className = "alarm-summary";
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
    if (estopNode) {
      estopNode.className = `safety-ind-value ${estopActive ? "fault" : "ok"}`;
      estopNode.textContent = estopActive ? "⚠ ACTIVE" : "CLEAR";
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

    // Motion
    const motionNode = el("strip-motion");
    if (motionNode) {
      const allowed = !reason;
      motionNode.className = `safety-ind-value ${allowed ? "ok" : "warn"}`;
      motionNode.textContent = allowed ? "ENABLED" : "INHIBITED";
    }

    // Reason
    const reasonNode = el("strip-motion-reason");
    if (reasonNode) {
      reasonNode.className = `motion-inhibit-reason ${reason ? "" : "clear"}`;
      reasonNode.textContent = reason || "Motion enabled — all conditions met";
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
    if (navAlarmCount) navAlarmCount.textContent = String(activeAlarmCount());
  }

  /* ── RENDER: HEADER ─────────────────────────────────────────── */
  function updateHeader() {
    const status  = getStatus();
    const op      = getOperation();
    const now     = new Date().toLocaleTimeString();

    // Connection
    const connNode = el("hdr-connection");
    if (connNode) {
      connNode.className = MS.online ? "online" : "offline";
      connNode.textContent = MS.online ? "ONLINE" : "OFFLINE";
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

    // Mode
    setText("hdr-mode", MS.payload?.busy ? "MANUAL ACTIVE" : "MANUAL");
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
    const canJog  = canJogAxis();
    const canHome = canHomeAxis();
    const inhibitReason = motionInhibitReason(false);

    // Jog buttons
    $$("[data-jog]").forEach((btn) => {
      btn.disabled = !canJog;
    });

    const selectedCode = selectedSlotCode();
    const selectedSlot = MS.slots[selectedCode] || {};
    const canUseSlot = motionAllowed(true);
    const selectedSlotReady = slotStatus(selectedSlot) === "ready";
    const armedSlotMatches = MS.validation.stage === "armed" && AXES.every((axis) => {
      const plannedTarget = MS.validation.plan?.axes?.[axis]?.target_mm;
      return plannedTarget != null && Math.abs(Number(plannedTarget) - Number(selectedSlot[`${axis}_mm`])) < 0.001;
    });
    el("selected-slot-load-target").disabled = !MS.online || !selectedSlotReady;
    el("selected-slot-validate").disabled = !canUseSlot || !selectedSlotReady;
    el("selected-slot-goto").disabled = !canUseSlot || !selectedSlotReady || !armedSlotMatches;
    if (document.getElementById("visual-load-preview")) updateVisualButtons();

    // Home buttons
    el("home-all").disabled = !canHome;
    $$(".home-axis").forEach((btn) => { btn.disabled = !canHome; });

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
    setText("fo-pct-display", String(MS.feedOverridePct));
    const overrideValue = document.getElementById("fo-override-val");
    if (overrideValue) overrideValue.textContent = `${MS.feedOverridePct} %`;

    // Programmed speed from the target speed field
    const progSpd = Number(el("target-speed")?.value || el("move-speed")?.value || 0);
    const effSpd  = progSpd * (MS.feedOverridePct / 100);
    setText("fo-prog-speed", progSpd > 0 ? `${fmtSpd(progSpd)} mm/s` : "-- mm/s");
    setText("fo-eff-speed",  progSpd > 0 ? `${fmtSpd(effSpd)} mm/s`  : "-- mm/s");

    // Highlight active preset
    $$(".fo-preset-btn").forEach((btn) => {
      btn.classList.toggle("active", Number(btn.dataset.fo) === MS.feedOverridePct);
    });
  }

  /* ── MASTER RENDER ──────────────────────────────────────────── */
  const VALID_VIEWS = new Set([
    "dashboard", "motion", "visualization", "diagnostics", "configuration",
    "slots", "alarms", "events", "flow",
  ]);

  function switchWorkspace(view, updateHash = true) {
    const nextView = VALID_VIEWS.has(view) ? view : "motion";
    MS.currentView = nextView;
    $$('[data-view-page]').forEach((page) => page.classList.toggle("active", page.dataset.viewPage === nextView));
    $$('[data-view-target]').forEach((button) => {
      const active = button.dataset.viewTarget === nextView;
      button.classList.toggle("active", active);
      button.setAttribute("aria-current", active ? "page" : "false");
    });
    const shell = $(".hmi-shell");
    if (shell) {
      shell.classList.toggle("view-wide", nextView !== "motion");
      shell.classList.toggle("view-dashboard", nextView === "dashboard");
    }
    if (updateHash && location.hash !== `#${nextView}`) history.replaceState(null, "", `#${nextView}`);
    renderWorkspacePages();
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
      return `<button type="button" class="${classes.join(" ")}" data-visual-slot="${code}" title="Select Slot ${code} for details only">
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
      return `<article class="visual-axis-row ${axisData.is_homed ? "ok" : "warn"}"><b>${axis.toUpperCase()}</b><div><span>Actual</span><strong>${Number.isFinite(actual) ? fmtPos(actual) : "UNKNOWN"}</strong></div><div><span>Target / Delta</span><strong>${Number.isFinite(target) ? `${fmtPos(target)} / ${fmtDelta(delta).text}` : "NO DATA"}</strong></div><div><span>Pulses</span><strong>${dataState.live ? fmtSteps(axisData.position_steps) : "UNKNOWN"}</strong></div><div><span>Speed Cmd / Eff</span><strong>${planned ? `${fmtSpd(Number(el("target-speed")?.value || 0))} / ${fmtSpd(planned.speed_mm_s)}` : "NO DATA"}</strong></div><div><span>Home / Limits</span><strong>${axisData.is_homed ? "HOMED" : "NOT HOMED"} · ${axisData.head_limit || axisData.tail_limit ? "ACTIVE" : "CLEAR"}</strong></div><div><span>Drive / Error</span><strong>NO DATA</strong></div></article>`;
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

  function updateVisualButtons() {
    const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
    const slot = MS.slots[code] || {};
    const validSlot = visualSlotIsValid(slot) && slotStatus(slot) === "ready";
    const idle = MS.online && !MS.pending && !MS.payload?.busy;
    el("visual-load-preview").disabled = !validSlot || !idle;
    el("visual-send-motion").disabled = !validSlot;
    el("visual-slot-goto").disabled = !validSlot || !idle || Boolean(motionInhibitReason(true));
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
        speed_mm_s: Number(el("target-speed")?.value || 10), timeout_s: Number(el("move-timeout")?.value || 30),
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
      speed_mm_s: Number(el("target-speed")?.value || 10) * (MS.feedOverridePct / 100),
      timeout_s: Number(el("move-timeout")?.value || 30),
      acceleration_mm_s2: Number(el("move-acceleration")?.value || 80),
      deceleration_mm_s2: Number(el("move-deceleration")?.value || 80),
    };

    try {
      const preview = await apiCall("/api/motion/preview", "POST", payload);
      MS.visualPreview = preview.plan;
      renderVisualizationV32();
      const duration = Number(preview.plan?.duration_s);
      const confirmation = [
        `Move machine to Slot ${code}?`,
        `X ${fmtPos(slot.x_mm)} mm · Y ${fmtPos(slot.y_mm)} mm · Z ${fmtPos(slot.z_mm)} mm`,
        `Speed ${fmt(payload.speed_mm_s, 1)} mm/s${Number.isFinite(duration) ? ` · Estimated ${fmtTime(duration)} s` : ""}`,
        "Confirm the travel area is clear before continuing.",
      ].join("\n");
      if (!window.confirm(confirmation)) {
        toast(`GOTO Slot ${code} cancelled. Preview remains available.`, "");
        log(`Visualization GOTO Slot ${code} cancelled after preview`, "info", "MOTION");
        return;
      }

      const armed = await apiCall("/api/motion/arm", "POST", payload);
      const requestId = globalThis.crypto?.randomUUID?.() || `visual-slot-${code}-${Date.now()}`;
      const result = await command(`GOTO Slot ${code}`, "/api/motion/execute", {
        arm_token: armed.arm_token,
        request_id: requestId,
      }, {
        requireHome: true,
        timeoutMs: Math.max(15000, (Number(payload.timeout_s) + 10) * 1000),
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
        <div><span>Cmd / Effective</span><strong>${fmtSpd(MS.selectedJogSpeed)} / ${fmtSpd(MS.selectedJogSpeed * MS.feedOverridePct / 100)}<small> mm/s</small></strong></div>
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
  }

  function renderWorkspacePages() {
    const status = getStatus();
    const operation = getOperation();
    const homed = allAxesHomed();
    const ready = MS.online && !status.estop && !MS.payload?.safety?.stop_requested && homed && !MS.payload?.busy && activeAlarmCount() === 0;
    const alarmCount = activeAlarmCount();
    const configuredSlots = Object.values(MS.slots || {}).filter((slot) => slotStatus(slot) === "ready").length;

    renderDashboard();

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
        ["Emergency Stop", status.estop ? "ACTIVE" : "CLEAR", "Hardware safety input", status.estop ? "fault" : "ok"],
        ["Homing", homed ? "COMPLETE" : "REQUIRED", AXES.map((a) => `${a.toUpperCase()}:${getAxis(a).is_homed ? "OK" : "--"}`).join("  "), homed ? "ok" : "warn"],
        ["Motion Queue", MS.payload?.busy ? "BUSY" : "IDLE", MS.payload?.active_command || "No pending command", MS.payload?.busy ? "warn" : "ok"],
        ["Active Alarms", String(alarmCount), MS.payload?.last_error || "No controller faults", alarmCount ? "fault" : "ok"],
        ["Slot Database", String(Object.keys(MS.slots || {}).length), `${configuredSlots} configured locations`, "ok"],
        ["Feed Override", `${MS.feedOverridePct}%`, `${fmtSpd(MS.selectedJogSpeed)} mm/s jog speed`, "ok"],
        ["Last Operation", operation.ok === false ? "FAILED" : "NORMAL", operation.message || "No operation message", operation.ok === false ? "fault" : "ok"],
      ];
      diagnostics.innerHTML = diagnosticItems.map(([label, value, detail, stateClass]) => `<article class="diagnostic-card ${stateClass}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></article>`).join("");
    }
    const diagHealth = document.getElementById("diag-health");
    if (diagHealth) {
      diagHealth.textContent = alarmCount ? "FAULT DETECTED" : (MS.online ? "SYSTEM HEALTHY" : "OFFLINE");
      diagHealth.className = `page-status-chip ${alarmCount || !MS.online ? "fault" : "ok"}`;
    }

    const configTable = document.getElementById("configuration-axis-table");
    if (configTable) configTable.innerHTML = AXES.map((axis) => {
      const cfg = MS.config?.axes?.[axis] || {};
      return `<tr><td>${axis.toUpperCase()}</td><td>${fmt(cfg.max_travel_mm, 1)} mm</td><td>${fmt(cfg.steps_per_mm, 1)}</td><td>${fmt(cfg.max_speed_mm_s, 1)} mm/s</td><td>${fmt(cfg.default_speed_mm_s, 1)} mm/s</td><td>${fmt(cfg.lead_screw_pitch_mm, 1)} mm</td></tr>`;
    }).join("");

    const hardware = MS.config?.hardware || {};
    setText("configuration-board-profile", `Board: ${hardware.board_profile || "--"}`);
    const pinRows = [];
    Object.entries(hardware.motors || {}).forEach(([axis, pins]) => {
      [["STEP", pins.step_pin], ["DIR", pins.dir_pin], ["ENABLE", pins.enable_pin]].forEach(([signal, pin]) => {
        pinRows.push([`${axis.toUpperCase()} ${signal}`, "Motor Output", pin, "--", pins.active_high ? "ACTIVE HIGH" : "ACTIVE LOW"]);
      });
    });
    Object.entries(hardware.digital_inputs || {}).forEach(([name, input]) => {
      pinRows.push([
        name.replaceAll("_", " ").toUpperCase(),
        name.includes("home") || name.includes("lim_") ? "Position Sensor" : "Safety Input",
        input.pin,
        input.pull_up ? "PULL-UP" : "NO PULL-UP",
        input.active_high ? "ACTIVE HIGH" : "ACTIVE LOW",
      ]);
    });
    Object.entries(hardware.digital_outputs || {}).forEach(([name, output]) => {
      pinRows.push([
        name.replaceAll("_", " ").toUpperCase(),
        "Digital Output",
        output.pin,
        output.initial_value ? "INITIAL ON" : "INITIAL OFF",
        output.active_high ? "ACTIVE HIGH" : "ACTIVE LOW",
      ]);
    });
    const pinTable = document.getElementById("configuration-pin-table");
    if (pinTable) pinTable.innerHTML = pinRows.map(([signal, category, pin, setup, logic]) =>
      `<tr><td>${esc(signal)}</td><td>${esc(category)}</td><td>GPIO ${esc(pin)}</td><td>${esc(setup)}</td><td>${esc(logic)}</td></tr>`
    ).join("");

    const alarmList = document.getElementById("alarm-page-list");
    if (alarmList) alarmList.innerHTML = alarmChannels().map((channel) => `
      <article class="alarm-page-item ${channel.active ? channel.level : "clear"}">
        <i class="alarm-point-light ${channel.active ? channel.level : "clear"}" aria-hidden="true"></i>
        <div><span>${esc(channel.code)}</span><strong>${esc(channel.label)}</strong><small>${esc(channel.detail)}</small></div>
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
    setFlow("flow-dispense", commandName === "dispense" ? "active" : (operationMessage.includes("completed dispense") ? "complete" : "pending"));
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
    const liveDiagnostics = $(".rpz-log");
    if (motionPage && axisPanel) {
      axisPanel.classList.add("motion-axis-panel");
      motionPage.prepend(axisPanel);
    }
    if (diagnosticsPage && liveDiagnostics) {
      liveDiagnostics.classList.add("diagnostics-live-log");
      diagnosticsPage.append(liveDiagnostics);
    }
  }

  function bind() {

    /* --- Workspace navigation --- */
    $$('[data-view-target]').forEach((button) => {
      button.addEventListener("click", () => switchWorkspace(button.dataset.viewTarget));
    });
    window.addEventListener("hashchange", () => switchWorkspace(location.hash.slice(1), false));

    /* --- Emergency Stop --- */
    el("stop-button").addEventListener("click", () => {
      command("Emergency stop", "/api/stop", undefined, { isStop: true, noCheck: true });
    });

    /* --- Reset Alarm --- */
    el("clear-alarm").addEventListener("click", () => {
      command("Reset alarms", "/api/clear-alarm", undefined, { isStop: true, noCheck: true });
    });
    el("page-clear-alarm").addEventListener("click", () => {
      command("Reset alarms", "/api/clear-alarm", undefined, { isStop: true, noCheck: true });
    });

    /* --- Jog directional buttons --- */
    $$("[data-jog]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const [axis, dir] = btn.dataset.jog.split(":");
        command(`Jog ${axis.toUpperCase()} ${dir === "1" ? "+" : "-"}${MS.selectedJogStep} mm`,
          "/api/jog", buildJogPayload(axis, dir), { silent: true });
      });
    });

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
        MS.selectedJogSpeed = Number(btn.dataset.speed);
        $$(".speed-preset").forEach((b) => b.classList.toggle("active", b === btn));
        setText("jog-speed-display", `${fmtSpd(MS.selectedJogSpeed)}`);
        if (el("move-speed")) el("move-speed").value = MS.selectedJogSpeed;
        updateFeedOverride();
        // Also save to controller
        command(`Set jog speed ${MS.selectedJogSpeed} mm/s`, "/api/speed",
          { speed_mm_s: MS.selectedJogSpeed }, { isStop: true, noCheck: true });
      });
    });

    el("jog-keyboard-enable").addEventListener("change", (event) => {
      MS.keyboardJogEnabled = event.target.checked;
      toast(`Keyboard jog ${MS.keyboardJogEnabled ? "enabled" : "disabled"}.`, MS.keyboardJogEnabled ? "ok" : "");
    });
    document.addEventListener("keydown", (event) => {
      if (!MS.keyboardJogEnabled || MS.currentView !== "motion" || event.repeat) return;
      const tagName = document.activeElement?.tagName?.toLowerCase();
      if (["input", "select", "textarea", "button"].includes(tagName) || document.activeElement?.isContentEditable) return;
      const keyMap = {
        ArrowLeft: ["x", -1], ArrowRight: ["x", 1],
        ArrowDown: ["y", -1], ArrowUp: ["y", 1],
        PageDown: ["z", -1], PageUp: ["z", 1],
      };
      const move = keyMap[event.key];
      if (!move) return;
      event.preventDefault();
      const [axis, direction] = move;
      command(`Keyboard jog ${axis.toUpperCase()} ${direction > 0 ? "+" : "−"}`,
        "/api/jog", buildJogPayload(axis, direction), { silent: true });
    });

    /* --- Feed override presets --- */
    $$(".fo-preset-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        MS.feedOverridePct = Number(btn.dataset.fo);
        if (MS.validation.stage !== "idle") invalidateMotionWorkflow("Feed override changed — validate again.");
        updateFeedOverride();
      });
    });

    /* --- Homing --- */
    el("home-all").addEventListener("click", () => {
      command("Home all axes", "/api/home/all");
    });
    $$(".home-axis").forEach((btn) => {
      btn.addEventListener("click", () => {
        const axis = btn.dataset.axis;
        command(`Home axis ${axis.toUpperCase()}`, `/api/home/${axis}`);
      });
    });

    /* --- Target positioning workflow --- */
    el("validate-move").addEventListener("click", () => validateMove(true));

    el("plan-move").addEventListener("click", () => previewMove(true));
    el("arm-move").addEventListener("click", () => armMove(true));

    el("absolute-move").addEventListener("click", () => executeArmedMotion("Execute validated move"));
    el("controlled-stop").addEventListener("click", () => {
      command("Controlled stop", "/api/motion/controlled-stop", undefined, { isStop: true, noCheck: true });
    });
    el("abort-motion").addEventListener("click", () => {
      command("Abort motion", "/api/motion/abort", undefined, { isStop: true, noCheck: true });
    });

    ["move-x", "move-y", "move-z", "target-speed", "target-duration", "move-timeout", "move-acceleration", "move-deceleration"]
      .forEach((id) => el(id).addEventListener("input", () => {
        if (MS.validation.stage !== "idle") invalidateMotionWorkflow();
        updateFeedOverride();
      }));

    /* --- Slot search / filter --- */
    el("slot-search").addEventListener("input", renderSlotTable);
    el("slot-filter").addEventListener("change", renderSlotTable);

    /* --- Selected slot direct controls --- */
    el("selected-slot-code").addEventListener("change", (event) => {
      MS.selectedSlotCode = event.target.value;
      MS.visualTargetSlot = event.target.value;
      MS.slotEditorDirty = false;
      loadSelectedSlotEditor(true);
      invalidateMotionWorkflow("Slot changed — load and validate the target.");
      updateButtonStates();
    });
    el("selected-slot-load-target").addEventListener("click", () => {
      const code = selectedSlotCode();
      const slot = MS.slots[code] || {};
      AXES.forEach((axis) => { el(`move-${axis}`).value = Number(slot[`${axis}_mm`] || 0).toFixed(3); });
      invalidateMotionWorkflow(`Slot ${code} loaded — validate before movement.`);
      toast(`Slot ${code} coordinates loaded into Target Positioning.`, "ok");
    });
    el("selected-slot-validate").addEventListener("click", async () => {
      el("selected-slot-load-target").click();
      const plan = await validateMove(true);
      if (plan) await previewMove(true);
    });
    el("selected-slot-goto").addEventListener("click", () => {
      const code = selectedSlotCode();
      if (code) executeArmedMotion(`Go to validated slot ${code}`);
    });

    /* --- Visualization slot click selects only; GOTO requires an explicit button press. --- */
    el("visual-slot-grid").addEventListener("click", (event) => {
      const slotButton = event.target.closest("[data-visual-slot]");
      if (!slotButton) return;
      const code = slotButton.dataset.visualSlot;
      MS.selectedSlotCode = code;
      MS.visualTargetSlot = code;
      MS.visualEditorDirty = false;
      MS.visualPreview = null;
      MS.visualEditMode = false;
      loadSelectedSlotEditor(true);
      renderVisualizationV32();
    });
    AXES.forEach((axis) => el(`visual-slot-${axis}`).addEventListener("input", () => {
      MS.visualEditorDirty = true;
      MS.visualPreview = null;
      const values = visualSlotValues();
      const original = MS.visualOriginalSlot || {};
      setText("visual-edit-comparison", AXES.map((item) => `${item.toUpperCase()} ${fmtPos(original[`${item}_mm`])} → ${fmtPos(values[`${item}_mm`])}`).join(" · "));
      updateVisualButtons();
    }));
    el("visual-slot-load-current").addEventListener("click", loadCurrentIntoVisualSlot);
    el("visual-slot-save").addEventListener("click", saveVisualSlotV32);
    el("visual-slot-goto").addEventListener("click", gotoVisualSlot);
    el("visual-load-preview").addEventListener("click", previewVisualSlot);
    el("visual-send-motion").addEventListener("click", sendVisualTargetToMotion);
    el("visual-edit-enable").addEventListener("click", () => setVisualEditMode(true));
    el("visual-edit-cancel").addEventListener("click", () => setVisualEditMode(false));

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

    /* --- Target speed input change — update feed override display --- */
    el("target-speed").addEventListener("input", updateFeedOverride);

  }

  /* ── INIT ───────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", () => {
    organizeWorkspacePanels();
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
