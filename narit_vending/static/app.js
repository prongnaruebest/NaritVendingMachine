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
    validation: { valid: false, message: "Target not validated.", plan: null },

    // UI state
    feedOverridePct: 100,   // 0–100, displayed
    selectedJogStep: 1.0,
    selectedJogSpeed: 15.0,
    selectedSlotCode: "",
    visualTargetSlot: "",
    slotEditorDirty: false,
    visualEditorDirty: false,
    slotDrafts: {},
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
  function canExecuteMove() { return MS.validation.valid && motionInhibitReason(true) === ""; }
  function canHomeAxis() { return motionInhibitReason(false) === ""; }

  /* ── SLOT STATUS ────────────────────────────────────────────── */
  function slotStatus(slot) {
    const hasProduct = Boolean(slot.product_name);
    const hasCoords = [slot.x_mm, slot.y_mm, slot.z_mm].some((v) => Number(v) !== 0);
    if (!hasProduct && !hasCoords) return "empty";
    return "ready";
  }

  /* ── API LAYER ──────────────────────────────────────────────── */
  async function apiCall(path, method = "GET", body) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
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
      const data = await apiCall(path, "POST", body);
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
    const time = el("move-time")?.value;
    if (spd) body.speed_mm_s = Number(spd);
    if (time) body.time_s = Number(time);
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
    const time = el("move-time")?.value;
    if (spd) body.speed_mm_s = Number(spd) * (MS.feedOverridePct / 100);
    if (time) body.time_s = Number(time);
    return body;
  }

  /* ── VALIDATE MOVE ──────────────────────────────────────────── */
  async function validateMove(showToast = true) {
    const payload = buildMovePayload();
    if (!Object.keys(payload).some((k) => k.endsWith("_mm"))) {
      setValidation(false, "TARGET INVALID — enter at least one axis coordinate.");
      if (showToast) toast("Enter at least one target coordinate.", "error");
      return null;
    }
    try {
      const data = await apiCall("/api/plan/move", "POST", payload);
      const plan = data.plan;
      setValidation(true, "TARGET VALID — move may execute safely.", plan);
      renderPreview(plan);
      renderPlan(plan);
      if (showToast) toast("Target validated — ready to execute.", "ok");
      log("Target validation passed", "info", "MOTION");
      return plan;
    } catch (err) {
      const msg = `TARGET INVALID — ${humanizeError(err.message)}`;
      setValidation(false, msg);
      renderPreview(null);
      if (showToast) toast(msg, "error");
      log(msg, "error", "MOTION");
      return null;
    }
  }

  function setValidation(valid, message, plan = null) {
    MS.validation = { valid, message, plan };
    const box = el("validation-box");
    if (box) {
      box.className = `validation-message ${valid ? "valid" : message !== "Target not validated." ? "invalid" : ""}`;
      box.textContent = message;
    }
    updateExecuteButton();
  }

  function updateExecuteButton() {
    const btn = el("absolute-move");
    if (!btn) return;
    btn.disabled = !canExecuteMove();
    btn.textContent = MS.payload?.busy ? "MOVING..." : "EXECUTE MOVE";
    btn.className = MS.payload?.busy ? "btn-execute btn-executing" : "btn-execute";
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
      setText("prev-speed", "--- mm/s");
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
    const firstAxis = Object.values(plan.axes || {})[0];
    setText("prev-speed", firstAxis ? `${fmtSpd(firstAxis.speed_mm_s)} mm/s` : "--- mm/s");
  }

  /* ── RENDER: PLAN READOUT ───────────────────────────────────── */
  function renderPlan(plan) {
    const node = el("move-plan");
    if (!node) return;
    if (!plan) { node.textContent = "Preview not generated."; return; }
    const mode = String(plan.mode || "speed").toUpperCase();
    const lines = Object.values(plan.axes || {}).map((item) =>
      `${item.axis.toUpperCase()}: ${fmtPos(item.distance_mm)} mm · ${fmtSteps(item.steps)} steps · ${fmtSpd(item.speed_mm_s)} mm/s · ${fmtTime(item.duration_s)} s`
    ).join("\n");
    node.innerHTML = `<strong>${esc(mode)} PLAN</strong>` +
      `<br>Dist: ${fmtPos(plan.total_distance_mm)} mm · Time: ${fmtTime(plan.duration_s)} s · Steps: ${fmtSteps(plan.master_steps)}`+
      (lines ? `<br><small style="color:var(--text-3)">${esc(lines)}</small>` : "");
  }

  /* ── RENDER: AXIS CARDS ─────────────────────────────────────── */
  function renderAxisCards() {
    const axisCfg = MS.config?.axes || {};
    AXES.forEach((a) => {
      const data = getAxis(a);
      const cfg  = axisCfg[a] || {};
      const pos  = Number(data.position_mm ?? 0);
      const tgt  = MS.validation.plan?.axes?.[a]?.target_mm ?? pos;
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
        effectivePhase === "homing"    ? "HOMING..." :
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
    const ctrlNode = el("strip-controller");
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
    const canConfigureSlot = MS.online && !MS.pending && !MS.payload?.busy;
    const canUseSlot = motionAllowed(true);
    const selectedSlotReady = slotStatus(selectedSlot) === "ready";
    if (el("selected-slot-load-current")) el("selected-slot-load-current").disabled = !MS.online;
    if (el("selected-slot-save")) el("selected-slot-save").disabled = !canConfigureSlot;
    if (el("selected-slot-goto")) el("selected-slot-goto").disabled = !canUseSlot;
    if (el("selected-slot-dispense")) el("selected-slot-dispense").disabled = !canUseSlot || !selectedSlotReady;
    if (el("visual-slot-load-current")) el("visual-slot-load-current").disabled = !canUseSlot;
    if (el("visual-slot-save")) el("visual-slot-save").disabled = !canConfigureSlot;
    if (el("visual-slot-goto")) el("visual-slot-goto").disabled = !canUseSlot || slotStatus(MS.slots[MS.visualTargetSlot || MS.selectedSlotCode || "1"] || {}) !== "ready";

    // Jog inhibit banner
    const banner = el("jog-inhibit-banner");
    if (banner) {
      const showInhibit = !canJog && inhibitReason !== "Another command is executing";
      if (showInhibit) {
        banner.classList.add("active");
        setText("jog-inhibit-text", inhibitReason || "Motion inhibited");
      } else {
        banner.classList.remove("active");
      }
    }

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
    setText("fo-override-val", `${MS.feedOverridePct} %`);

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
    if (shell) shell.classList.toggle("view-wide", nextView !== "motion");
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
    const current = getStatus().current_position || {};
    AXES.forEach((axis) => {
      el(`visual-slot-${axis}`).value = Number(current[`${axis}_mm`] || 0).toFixed(3);
    });
    MS.visualEditorDirty = true;
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

  function renderWorkspacePages() {
    const status = getStatus();
    const operation = getOperation();
    const homed = allAxesHomed();
    const ready = MS.online && !status.estop && homed && !MS.payload?.busy;
    const alarmCount = activeAlarmCount();
    const configuredSlots = Object.values(MS.slots || {}).filter((slot) => slotStatus(slot) === "ready").length;

    setText("dashboard-controller", MS.online ? "ONLINE" : "OFFLINE");
    setText("dashboard-state", ready ? "READY" : "NOT READY");
    setText("dashboard-state-detail", operation.message || motionInhibitReason(true) || "Controller ready");
    setText("dashboard-command", MS.payload?.active_command || "NONE");
    setText("dashboard-slots", configuredSlots);
    const dashboardHealth = document.getElementById("dashboard-health");
    if (dashboardHealth) {
      dashboardHealth.textContent = ready ? "SYSTEM READY" : (MS.online ? "ATTENTION" : "OFFLINE");
      dashboardHealth.className = `page-status-chip ${ready ? "ok" : (MS.online ? "" : "fault")}`;
    }

    const dashboardAxes = document.getElementById("dashboard-axis-grid");
    if (dashboardAxes) dashboardAxes.innerHTML = AXES.map((axis) => {
      const data = getAxis(axis);
      return `<article class="dashboard-axis-card"><span>${axis.toUpperCase()} AXIS</span><strong>${fmtPos(data.position_mm)} mm</strong><small>${data.is_homed ? "HOMED" : "NOT HOMED"} · ${fmtSteps(data.position_steps)} steps</small></article>`;
    }).join("");

    renderVisualization();

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
    renderWorkspacePages();
  }

  function render(payload) {
    MS.payload = payload;
    MS.slots   = payload.slots || {};

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

    /* --- Feed override presets --- */
    $$(".fo-preset-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        MS.feedOverridePct = Number(btn.dataset.fo);
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

    el("plan-move").addEventListener("click", async () => {
      const plan = await validateMove(false);
      if (plan) {
        toast("Move preview updated.", "ok");
        log("Move preview generated", "info", "MOTION");
      } else {
        toast(MS.validation.message, "error");
      }
    });

    el("absolute-move").addEventListener("click", async () => {
      if (!MS.validation.valid) {
        const plan = await validateMove(true);
        if (!plan) return;
      }
      command("Execute move", "/api/move", buildMovePayload(), { requireHome: true });
    });

    /* --- Save speed to controller --- */
    el("apply-speed").addEventListener("click", () => {
      const v = el("target-speed")?.value || el("move-speed")?.value;
      if (!v) { toast("Enter travel speed first.", "error"); return; }
      const eff = Number(v) * (MS.feedOverridePct / 100);
      if (el("move-speed")) el("move-speed").value = v;
      updateFeedOverride();
      command(`Save travel speed ${eff} mm/s`, "/api/speed",
        { speed_mm_s: eff }, { isStop: true, noCheck: true });
    });

    /* --- Save timeout to controller --- */
    el("apply-time").addEventListener("click", () => {
      const v = el("move-time")?.value;
      if (!v) { toast("Enter move timeout first.", "error"); return; }
      command(`Save move timeout ${v} s`, "/api/timer",
        { duration_s: Number(v) }, { isStop: true, noCheck: true });
    });

    /* --- Slot search / filter --- */
    el("slot-search").addEventListener("input", renderSlotTable);
    el("slot-filter").addEventListener("change", renderSlotTable);

    /* --- Selected slot direct controls --- */
    el("selected-slot-code").addEventListener("change", (event) => {
      MS.selectedSlotCode = event.target.value;
      MS.visualTargetSlot = event.target.value;
      MS.slotEditorDirty = false;
      loadSelectedSlotEditor(true);
      updateButtonStates();
    });
    ["selected-slot-x", "selected-slot-y", "selected-slot-z"]
      .forEach((id) => el(id).addEventListener("input", () => { MS.slotEditorDirty = true; }));
    el("selected-slot-load-current").addEventListener("click", loadCurrentIntoSelectedSlot);
    el("selected-slot-save").addEventListener("click", saveSelectedSlot);
    el("selected-slot-goto").addEventListener("click", () => {
      const code = selectedSlotCode();
      if (code) {
        MS.visualTargetSlot = code;
        command(`Go to slot ${code}`, `/api/slots/${code}/goto`, targetSpeedPayload(), { requireHome: true });
      }
    });
    el("selected-slot-dispense").addEventListener("click", () => {
      const code = selectedSlotCode();
      if (code) {
        MS.visualTargetSlot = code;
        command(`Dispense slot ${code}`, "/api/start", { slot: code, ...targetSpeedPayload() }, { requireHome: true });
      }
    });

    /* --- Visualization slot map: select, edit, save, then move explicitly --- */
    el("visual-slot-grid").addEventListener("click", (event) => {
      const slotButton = event.target.closest("[data-visual-slot]");
      if (!slotButton) return;
      const code = slotButton.dataset.visualSlot;
      MS.selectedSlotCode = code;
      MS.visualTargetSlot = code;
      MS.visualEditorDirty = false;
      loadSelectedSlotEditor(true);
      renderVisualization();
    });
    AXES.forEach((axis) => el(`visual-slot-${axis}`).addEventListener("input", () => { MS.visualEditorDirty = true; }));
    el("visual-slot-load-current").addEventListener("click", loadCurrentIntoVisualSlot);
    el("visual-slot-save").addEventListener("click", saveVisualSlot);
    el("visual-slot-goto").addEventListener("click", () => {
      const code = MS.visualTargetSlot || MS.selectedSlotCode || "1";
      command(`Go to slot ${code}`, `/api/slots/${code}/goto`, targetSpeedPayload(), { requireHome: true });
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
