(() => {
  "use strict";

  const axes = ["x", "y", "z"];
  const state = {
    online: false,
    pending: false,
    payload: null,
    config: null,
    slots: {},
    events: [],
    lastError: "",
    validation: { valid: false, message: "Target not validated.", plan: null },
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;",
    }[character]));
  }

  function formatNumber(value, digits = 2) {
    return Number(value || 0).toFixed(digits);
  }

  function formatPosition(value) {
    return `${formatNumber(value, 3)} mm`;
  }

  function setValidation(valid, message, plan = null) {
    state.validation = { valid, message, plan };
    const box = $("#validation-box");
    box.className = `validation-box ${valid ? "valid" : "invalid"}`;
    box.textContent = message;
    $("#absolute-move").disabled = !valid || !motionAllowed(true);
  }

  function log(message, level = "info", subsystem = "SYSTEM") {
    state.events.unshift({ at: new Date(), message, level, subsystem });
    state.events = state.events.slice(0, 120);
    $("#event-log").innerHTML = state.events.map((entry) => `
      <li class="${entry.level}">
        <time>${entry.at.toLocaleTimeString()} · ${escapeHtml(entry.subsystem)}</time>
        <span>${escapeHtml(entry.message)}</span>
      </li>
    `).join("");
  }

  function toast(message, error = false) {
    const element = $("#toast");
    element.textContent = message;
    element.className = `toast show${error ? " error" : ""}`;
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => {
      element.className = "toast";
    }, 3200);
  }

  async function api(path, method = "GET", body) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      return data;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function getStatus() {
    return state.payload?.status || {};
  }

  function getOperation() {
    return state.payload?.operation || {};
  }

  function getAxis(axis) {
    return getStatus()[axis] || {};
  }

  function allAxesHomed() {
    return axes.every((axis) => Boolean(getAxis(axis).is_homed));
  }

  function activeAlarmCount() {
    return state.payload?.last_error ? 1 : 0;
  }

  function motionInhibitReason(requireHome = false) {
    const status = getStatus();
    if (!state.online) return "Controller offline";
    if (status.estop) return "Emergency stop active";
    if (state.payload?.busy || state.pending) return "Another command is executing";
    if (requireHome && !allAxesHomed()) {
      const first = axes.find((axis) => !getAxis(axis).is_homed);
      return `${first?.toUpperCase() || "Axis"} axis not homed`;
    }
    return "";
  }

  function motionAllowed(requireHome = false) {
    return motionInhibitReason(requireHome) === "";
  }

  function buildMovePayload() {
    const payload = {};
    const speedValue = $("#target-speed").value || $("#move-speed").value;
    const timeValue = $("#move-time").value;
    axes.forEach((axis) => {
      const value = $(`#move-${axis}`).value;
      if (value !== "") payload[`${axis}_mm`] = Number(value);
    });
    if (speedValue !== "") payload.speed_mm_s = Number(speedValue);
    if (timeValue !== "") payload.time_s = Number(timeValue);
    return payload;
  }

  function buildJogPayload(axis, direction) {
    const body = {
      axis,
      distance_mm: Number($("#jog-step").value) * Number(direction),
    };
    const jogTime = $("#jog-time").value;
    const speedValue = $("#move-speed").value;
    if (jogTime !== "") body.time_s = Number(jogTime);
    if (speedValue !== "") body.speed_mm_s = Number(speedValue);
    return body;
  }

  function slotDerivedStatus(slot) {
    const configured = Boolean(slot.product_name) || [slot.x_mm, slot.y_mm, slot.z_mm].some((value) => Number(value) !== 0);
    if (!configured) return "empty";
    return "ready";
  }

  async function command(label, path, body, options = {}) {
    if (!options.stop && !motionAllowed(options.requireHome)) {
      const reason = motionInhibitReason(options.requireHome);
      toast(reason, true);
      log(`${label} blocked: ${reason}`, "error", "INTERLOCK");
      return;
    }

    state.pending = !options.stop;
    updateDerivedState();
    log(`${label} requested`, "info", "COMMAND");

    try {
      const response = await api(path, "POST", body);
      toast(`${label} accepted`);
      log(`${label} accepted`, "info", "COMMAND");
      if (response.plan) renderPlan(response.plan);
      await refresh();
    } catch (error) {
      const message = humanizeError(error.message);
      toast(message, true);
      log(`${label} failed: ${message}`, "error", "COMMAND");
    } finally {
      state.pending = false;
      updateDerivedState();
    }
  }

  function humanizeError(message) {
    if (message.includes("outside")) return `Move rejected: ${message}`;
    if (message.includes("not homed")) return `Move rejected: ${message}`;
    if (message.includes("Emergency")) return `Motion locked: ${message}`;
    return message;
  }

  async function validateMove(showToast = true) {
    const payload = buildMovePayload();
    if (!Object.keys(payload).some((key) => key.endsWith("_mm"))) {
      setValidation(false, "Target invalid: enter at least one axis target.");
      if (showToast) toast("Enter at least one axis target.", true);
      return null;
    }

    try {
      const response = await api("/api/plan/move", "POST", payload);
      const plan = response.plan;
      setValidation(true, "TARGET VALID. Move may execute safely.", plan);
      renderPreview(plan);
      renderPlan(plan);
      if (showToast) toast("Target validated.");
      log("Target validation succeeded", "info", "MOTION");
      return plan;
    } catch (error) {
      const message = `TARGET INVALID. ${humanizeError(error.message)}`;
      setValidation(false, message);
      renderPreview(null);
      if (showToast) toast(message, true);
      log(message, "error", "MOTION");
      return null;
    }
  }

  function renderPreview(plan) {
    const current = getStatus().current_position || {};
    const currentText = `X ${formatNumber(current.x_mm, 3)}\nY ${formatNumber(current.y_mm, 3)}\nZ ${formatNumber(current.z_mm, 3)}`;
    $("#preview-current").textContent = currentText;

    if (!plan) {
      $("#preview-target").textContent = "X --\nY --\nZ --";
      $("#preview-delta").textContent = "ΔX --\nΔY --\nΔZ --";
      return;
    }

    const targetLines = [];
    const deltaLines = [];
    axes.forEach((axis) => {
      const axisPlan = plan.axes?.[axis];
      if (axisPlan) {
        targetLines.push(`${axis.toUpperCase()} ${formatNumber(axisPlan.target_mm, 3)}`);
        deltaLines.push(`Δ${axis.toUpperCase()} ${axisPlan.distance_mm >= 0 ? "+" : ""}${formatNumber(axisPlan.distance_mm, 3)}`);
      } else {
        targetLines.push(`${axis.toUpperCase()} ${formatNumber(current[`${axis}_mm`], 3)}`);
        deltaLines.push(`Δ${axis.toUpperCase()} +0.000`);
      }
    });
    $("#preview-target").textContent = targetLines.join("\n");
    $("#preview-delta").textContent = deltaLines.join("\n");
  }

  function renderAxisCards() {
    const config = state.config?.axes || {};
    $("#axis-grid").innerHTML = axes.map((axis) => {
      const data = getAxis(axis);
      const axisCfg = config[axis] || {};
      const position = Number(data.position_mm || 0);
      const target = state.validation.plan?.axes?.[axis]?.target_mm ?? position;
      const trackPercent = axisCfg.max_travel_mm ? Math.max(0, Math.min((position / axisCfg.max_travel_mm) * 100, 100)) : 0;
      const badgeClass = data.estop ? "badge-red" : data.is_homed ? "badge-green" : "badge-amber";
      const stateLabel = data.estop
        ? "FAULT"
        : data.head_limit
          ? "LIMIT MIN"
          : data.tail_limit
            ? "LIMIT MAX"
            : data.is_homed
              ? "HOMED / IDLE"
              : "NOT HOMED";

      return `
        <article class="axis-card">
          <div class="axis-top">
            <h3>${axis.toUpperCase()} AXIS</h3>
            <span class="axis-badge ${badgeClass}">${data.is_homed ? "HOMED" : "NOT HOMED"}</span>
          </div>
          <div class="axis-main">
            <div class="axis-pos">${formatNumber(position, 3)}<span class="axis-unit">mm</span></div>
            <div class="axis-state">${stateLabel}</div>
            <div class="axis-track"><div class="axis-track-fill" style="width:${trackPercent}%"></div></div>
          </div>
          <div class="axis-meta">
            <div class="kv"><span>Target</span><strong>${formatNumber(target, 3)}</strong></div>
            <div class="kv"><span>Steps</span><strong>${Number(data.position_steps || 0).toLocaleString()}</strong></div>
            <div class="kv"><span>Min</span><strong>${data.head_limit ? "ACTIVE" : "CLEAR"}</strong></div>
            <div class="kv"><span>Max</span><strong>${data.tail_limit ? "ACTIVE" : "CLEAR"}</strong></div>
          </div>
        </article>
      `;
    }).join("");
  }

  function renderMechanicsSidebar() {
    $("#nav-alarm-count").textContent = String(activeAlarmCount());
  }

  function renderHomeStatus() {
    const homing = getOperation().homing || {};
    $("#home-status").innerHTML = axes.map((axis) => {
      const phase = homing[axis] || "not_homed";
      const badgeClass = phase === "passed" ? "badge-green" : phase === "failed" ? "badge-red" : phase === "homing" || phase === "waiting" ? "badge-amber" : "badge-gray";
      return `<span class="status-pill ${badgeClass}">${axis.toUpperCase()} ${phase.replaceAll("_", " ").toUpperCase()}</span>`;
    }).join("");
  }

  function renderPlan(plan) {
    if (!plan) {
      $("#move-plan").textContent = "Preview not generated.";
      return;
    }
    const lines = Object.values(plan.axes || {}).map((item) =>
      `<li>${item.axis.toUpperCase()}: ${formatNumber(item.distance_mm, 3)} mm · ${item.steps.toLocaleString()} steps · ${formatNumber(item.speed_mm_s, 1)} mm/s · ${formatNumber(item.duration_s, 2)} s</li>`
    ).join("");
    $("#move-plan").innerHTML = `
      <strong>${escapeHtml(String(plan.mode || "speed").toUpperCase())} PREVIEW</strong>
      <div>Estimated distance ${formatNumber(plan.total_distance_mm, 3)} mm · Estimated time ${formatNumber(plan.duration_s, 2)} s · Master steps ${Number(plan.master_steps || 0).toLocaleString()}</div>
      <ul>${lines || "<li>No movement planned.</li>"}</ul>
    `;
  }

  function renderSlotTable() {
    const search = $("#slot-search").value.trim().toLowerCase();
    const filter = $("#slot-filter").value;
    const entries = Object.entries(state.slots)
      .sort(([a], [b]) => Number(a) - Number(b))
      .filter(([code, slot]) => {
        const derived = slotDerivedStatus(slot);
        const matchFilter = filter === "all" || filter === derived || (filter === "configured" && derived !== "empty");
        const matchSearch = !search || code.includes(search) || String(slot.product_name || "").toLowerCase().includes(search);
        return matchFilter && matchSearch;
      });

    $("#slot-grid").innerHTML = entries.map(([code, slot]) => {
      const derived = slotDerivedStatus(slot);
      const badgeClass = derived === "ready" ? "badge-green" : derived === "empty" ? "badge-gray" : "badge-amber";
      return `
        <tr>
          <td>${escapeHtml(code)}</td>
          <td>${escapeHtml(slot.product_name || "EMPTY")}</td>
          <td><span class="slot-status ${badgeClass}">${derived.toUpperCase()}</span></td>
          <td>${formatNumber(slot.x_mm, 1)}</td>
          <td>${formatNumber(slot.y_mm, 1)}</td>
          <td>${formatNumber(slot.z_mm, 1)}</td>
          <td>
            <button data-slot-goto="${escapeHtml(code)}">GO TO POSITION</button>
            <button class="primary" data-slot-dispense="${escapeHtml(code)}" ${derived === "empty" ? "disabled" : ""}>DISPENSE</button>
            <button class="ghost" data-slot-save="${escapeHtml(code)}">SAVE POSITION</button>
          </td>
        </tr>
      `;
    }).join("");

    $$("[data-slot-goto]").forEach((button) => {
      button.disabled = !motionAllowed(true);
      button.addEventListener("click", () => command(`Move to slot ${button.dataset.slotGoto}`, `/api/slots/${button.dataset.slotGoto}/goto`, targetSpeedPayload(), { requireHome: true }));
    });
    $$("[data-slot-dispense]").forEach((button) => {
      button.disabled = button.disabled || !motionAllowed(true);
      button.addEventListener("click", () => command(`Dispense slot ${button.dataset.slotDispense}`, "/api/start", { slot: button.dataset.slotDispense, ...targetSpeedPayload() }, { requireHome: true }));
    });
    $$("[data-slot-save]").forEach((button) => {
      button.disabled = !motionAllowed(true);
      button.addEventListener("click", async () => {
        const current = getStatus().current_position || {};
        const confirmed = confirm(`Save current machine position to Slot ${button.dataset.slotSave}?\nX = ${formatNumber(current.x_mm, 3)} mm\nY = ${formatNumber(current.y_mm, 3)} mm\nZ = ${formatNumber(current.z_mm, 3)} mm`);
        if (!confirmed) return;
        command(`Save slot ${button.dataset.slotSave}`, `/api/slots/${button.dataset.slotSave}/save-current`, undefined, { requireHome: true });
      });
    });
  }

  function targetSpeedPayload() {
    const body = {};
    const speedValue = $("#target-speed").value || $("#move-speed").value;
    const timeValue = $("#move-time").value;
    if (speedValue !== "") body.speed_mm_s = Number(speedValue);
    if (timeValue !== "") body.time_s = Number(timeValue);
    return body;
  }

  function renderAlarmSummary() {
    const status = getStatus();
    const error = state.payload?.last_error;
    if (!error) {
      $("#alarm-summary").innerHTML = "<strong>NO ACTIVE ALARMS</strong><p>Machine operation normal.</p>";
      return;
    }
    const effect = status.estop ? "Motion inhibited by emergency stop." : "Motion inhibited until the condition is cleared.";
    $("#alarm-summary").innerHTML = `
      <strong>1 ACTIVE ALARM</strong>
      <p>${escapeHtml(error)}</p>
      <p><b>Severity:</b> ${status.estop ? "CRITICAL" : "WARNING"}<br><b>Effect:</b> ${effect}<br><b>Recommended action:</b> Clear alarm cause and re-home if required.</p>
    `;
  }

  function updateReadinessStrip() {
    const status = getStatus();
    const homed = allAxesHomed();
    const reason = motionInhibitReason(true);

    $("#strip-controller").textContent = state.online ? "ONLINE" : "OFFLINE";
    $("#strip-estop").textContent = status.estop ? "ACTIVE" : "CLEAR";
    $("#strip-homing").textContent = homed ? "ALL HOMED" : "NOT READY";
    $("#strip-homing-detail").textContent = homed ? "X ✓  Y ✓  Z ✓" : axes.map((axis) => `${axis.toUpperCase()} ${getAxis(axis).is_homed ? "✓" : "!"}`).join("  ");
    $("#strip-motion").textContent = reason ? "INHIBITED" : "ENABLED";
    $("#strip-motion-reason").textContent = reason || "Motion allowed";
    $("#strip-alarms").textContent = String(activeAlarmCount());
    $("#strip-alarm-detail").textContent = activeAlarmCount() ? (state.payload?.last_error || "Alarm active") : "No active alarms";
  }

  function updatePositionBanner() {
    const current = getStatus().current_position || {};
    $("#position-summary").innerHTML = `
      <div><span>X</span><strong>${formatNumber(current.x_mm, 3)}</strong><small>mm</small></div>
      <div><span>Y</span><strong>${formatNumber(current.y_mm, 3)}</strong><small>mm</small></div>
      <div><span>Z</span><strong>${formatNumber(current.z_mm, 3)}</strong><small>mm</small></div>
    `;
  }

  function updateSummaryPanels() {
    const status = getStatus();
    const operation = getOperation();
    const activeCommand = state.payload?.active_command || "None";
    $("#summary-controller").textContent = state.online ? "ONLINE" : "OFFLINE";
    $("#summary-motion").textContent = state.payload?.busy ? "EXECUTING" : "IDLE";
    $("#summary-mode").textContent = state.payload?.busy ? "MANUAL ACTIVE" : "MANUAL";
    $("#active-command").textContent = activeCommand;
    const duplicate = document.querySelector("#active-command-duplicate");
    if (duplicate) duplicate.textContent = activeCommand;
    $("#jog-inhibit-reason").textContent = motionInhibitReason(false) || "Manual motion ready";
    $("#operation-message").textContent = operation.message || "Controller ready";
    $("#connection-state").textContent = state.online ? "ONLINE" : "OFFLINE";
    $("#machine-state").textContent = status.estop
      ? "E-STOP"
      : state.payload?.busy
        ? String(operation.phase || "MOVING").toUpperCase()
        : allAxesHomed()
          ? "READY"
          : "NOT READY";
  }

  function updateFooter() {
    const status = getStatus();
    const now = new Date().toLocaleTimeString();
    const ready = motionInhibitReason(true) ? "NOT READY" : "READY";
    $("#footer-connection").textContent = state.online ? "ONLINE" : "OFFLINE";
    $("#footer-ready").textContent = ready;
    $("#footer-estop").textContent = status.estop ? "E-STOP ACTIVE" : "E-STOP CLEAR";
    $("#footer-status-text").textContent = `Command: ${state.payload?.active_command || "None"} | Motion: ${state.payload?.busy ? "Executing" : "Idle"} | Controller: ${getOperation().message || "Ready"}`;
    $("#footer-status-time").textContent = now;
  }

  function updateDerivedState() {
    updateReadinessStrip();
    updateSummaryPanels();
    updateFooter();
    renderAlarmSummary();
    renderMechanicsSidebar();
    $("#absolute-move").disabled = !state.validation.valid || !motionAllowed(true);
    const disableJog = !motionAllowed(false);
    $$("[data-jog]").forEach((button) => {
      button.disabled = disableJog;
    });
    $$(".home-axis").forEach((button) => {
      button.disabled = !motionAllowed(false);
    });
    $("#home-all").disabled = !motionAllowed(false);
    $("#stop-button").disabled = !state.online;
    $("#clear-alarm").disabled = !state.online || Boolean(state.payload?.busy);
  }

  function render(payload) {
    state.payload = payload;
    state.slots = payload.slots || {};
    updatePositionBanner();
    renderAxisCards();
    renderHomeStatus();
    renderSlotTable();
    updateDerivedState();

    if (payload.last_error && payload.last_error !== state.lastError) {
      log(humanizeError(payload.last_error), "error", "ALARM");
      toast(humanizeError(payload.last_error), true);
    }
    state.lastError = payload.last_error || "";
  }

  async function refresh() {
    try {
      const payload = await api("/api/status");
      if (!state.online) log("Controller connection established", "info", "CONTROLLER");
      state.online = true;
      render(payload);
    } catch (error) {
      if (state.online) log(`Controller connection lost: ${error.message}`, "error", "CONTROLLER");
      state.online = false;
      updateDerivedState();
      $("#connection-state").textContent = "OFFLINE";
      $("#machine-state").textContent = "OFFLINE";
      $("#strip-controller").textContent = "OFFLINE";
    }
  }

  async function loadConfig() {
    try {
      state.config = await api("/api/config");
      const order = state.config.home_order?.map((axis) => axis.toUpperCase()).join(" → ");
      if (order) $("#home-sequence").textContent = `Sequence: ${order}`;
      renderMechanicsSidebar();
    } catch (error) {
      log(`Config load failed: ${error.message}`, "error", "SYSTEM");
    }
  }

  function bind() {
    $("#home-all").addEventListener("click", () => command("Home all axes", "/api/home/all"));
    $$(".home-axis").forEach((button) => {
      button.addEventListener("click", () => command(`Home axis ${button.dataset.axis.toUpperCase()}`, `/api/home/${button.dataset.axis}`));
    });
    $$("[data-jog]").forEach((button) => {
      button.addEventListener("click", () => {
        const [axis, direction] = button.dataset.jog.split(":");
        command(`Jog ${axis.toUpperCase()}`, "/api/jog", buildJogPayload(axis, direction));
      });
    });
    $("#validate-move").addEventListener("click", () => {
      validateMove(true);
    });
    $("#plan-move").addEventListener("click", async () => {
      const plan = await validateMove(false);
      if (plan) {
        toast("Move preview updated.");
        log("Move preview generated", "info", "MOTION");
      } else {
        toast(state.validation.message, true);
      }
    });
    $("#absolute-move").addEventListener("click", async () => {
      if (!state.validation.valid) {
        const plan = await validateMove(true);
        if (!plan) return;
      }
      command("Execute move", "/api/move", buildMovePayload(), { requireHome: true });
    });
    $("#apply-speed").addEventListener("click", () => {
      const value = $("#target-speed").value || $("#move-speed").value;
      if (value === "") return toast("Enter travel speed first.", true);
      $("#move-speed").value = value;
      $("#target-speed").value = value;
      command("Save travel speed", "/api/speed", { speed_mm_s: Number(value) }, { stop: true });
    });
    $("#apply-time").addEventListener("click", () => {
      const value = $("#move-time").value;
      if (value === "") return toast("Enter move timeout first.", true);
      command("Save move timeout", "/api/timer", { duration_s: Number(value) }, { stop: true });
    });
    $$(".preset").forEach((button) => {
      button.addEventListener("click", () => {
        const value = button.dataset.speed;
        $("#move-speed").value = value;
        $("#target-speed").value = value;
        command(`Set travel speed ${value} mm/s`, "/api/speed", { speed_mm_s: Number(value) }, { stop: true });
      });
    });
    $("#stop-button").addEventListener("click", () => command("Emergency stop", "/api/stop", undefined, { stop: true }));
    $("#clear-alarm").addEventListener("click", () => command("Reset alarms", "/api/clear-alarm", undefined, { stop: true }));
    $("#slot-search").addEventListener("input", renderSlotTable);
    $("#slot-filter").addEventListener("change", renderSlotTable);
  }

  document.addEventListener("DOMContentLoaded", () => {
    bind();
    log("Industrial motion HMI started", "info", "SYSTEM");
    loadConfig();
    refresh();
    window.setInterval(refresh, 1000);
    window.setInterval(updateFooter, 1000);
  });
})();
