(() => {
  "use strict";

  const state = {
    online: false,
    pending: false,
    payload: null,
    config: null,
    slots: {},
    events: [],
    lastError: "",
  };

  const axes = ["x", "y", "z"];
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

  function log(message, level = "info") {
    state.events.unshift({ at: new Date(), message, level });
    state.events = state.events.slice(0, 100);
    $("#event-log").innerHTML = state.events.map((entry) => `
      <li class="${entry.level}">
        <time>${entry.at.toLocaleTimeString()}</time>
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
    }, 3000);
  }

  async function api(path, method = "GET", body) {
    const abort = new AbortController();
    const timer = window.setTimeout(() => abort.abort(), 8000);
    try {
      const response = await fetch(path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: abort.signal,
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

  function interlocks() {
    const status = state.payload?.status || {};
    return {
      online: state.online,
      estop: Boolean(status.estop),
      busy: Boolean(state.payload?.busy),
      homed: axes.every((axis) => Boolean(status[axis]?.is_homed)),
    };
  }

  function motionEnabled(requireHome = false) {
    const locks = interlocks();
    return locks.online && !locks.estop && !locks.busy && !state.pending && (!requireHome || locks.homed);
  }

  function buildMovePayload() {
    const payload = {};
    axes.forEach((axis) => {
      const value = $(`#move-${axis}`).value;
      if (value !== "") payload[`${axis}_mm`] = Number(value);
    });
    if ($("#move-speed").value !== "") payload.speed_mm_s = Number($("#move-speed").value);
    if ($("#move-time").value !== "") payload.time_s = Number($("#move-time").value);
    return payload;
  }

  function buildMoveOptions() {
    const payload = {};
    if ($("#move-speed").value !== "") payload.speed_mm_s = Number($("#move-speed").value);
    if ($("#move-time").value !== "") payload.time_s = Number($("#move-time").value);
    return payload;
  }

  async function command(label, path, body, options = {}) {
    if (!options.stop && !motionEnabled(options.requireHome)) {
      toast("Command blocked by interlock.", true);
      log(`${label} blocked by interlock.`, "error");
      return;
    }
    state.pending = !options.stop;
    updateInterlocks();
    log(`${label} requested.`);
    try {
      const response = await api(path, "POST", body);
      if (response.plan) renderPlan(response.plan);
      toast(`${label} accepted.`);
      log(`${label} accepted.`);
      await refresh();
    } catch (error) {
      toast(`${label}: ${error.message}`, true);
      log(`${label} failed: ${error.message}`, "error");
    } finally {
      state.pending = false;
      updateInterlocks();
    }
  }

  function renderAxisCards() {
    const status = state.payload?.status || {};
    $("#axis-grid").innerHTML = axes.map((axis) => {
      const data = status[axis] || {};
      return `
        <article class="axis-card">
          <div class="axis-top">
            <h3>AXIS ${axis.toUpperCase()}</h3>
            <span class="axis-tag ${data.is_homed ? "ok" : "warn"}">${data.is_homed ? "HOMED" : "NOT HOMED"}</span>
          </div>
          <div class="axis-readout">
            <div class="axis-value">${formatNumber(data.position_mm)} <small>mm</small></div>
            <div class="axis-tag ${data.estop ? "warn" : "ok"}">${data.estop ? "SAFE HOLD" : "READY"}</div>
          </div>
          <div class="axis-sub">
            <div class="kv"><span>Target</span><strong>${formatNumber(data.position_mm)}</strong></div>
            <div class="kv"><span>Steps</span><strong>${data.position_steps || 0}</strong></div>
            <div class="kv"><span>Min</span><strong>${data.head_limit ? "ON" : "OFF"}</strong></div>
            <div class="kv"><span>Max</span><strong>${data.tail_limit ? "ON" : "OFF"}</strong></div>
          </div>
        </article>
      `;
    }).join("");
  }

  function renderMechanics() {
    if (!state.config) return;
    $("#mechanics-summary").innerHTML = axes.map((axis) => {
      const cfg = state.config.axes?.[axis];
      if (!cfg) return "";
      return `
        <article class="mechanic-row">
          <strong>${axis.toUpperCase()}</strong>
          <span>${formatNumber(cfg.steps_per_mm, 1)} step/mm</span>
          <span>${cfg.pulses_per_rev} pulse/rev</span>
          <span>Pitch ${cfg.lead_screw_pitch_mm} mm</span>
          <span>Vmax ${cfg.max_speed_mm_s} mm/s</span>
        </article>
      `;
    }).join("");
  }

  function renderHomeStatus() {
    const homing = state.payload?.operation?.homing || {};
    $("#home-status").innerHTML = axes.map((axis) => {
      const phase = homing[axis] || "not_homed";
      const css = phase === "passed" ? "ok" : phase === "failed" ? "warn" : "warn";
      return `<span class="status-pill ${css}">${axis.toUpperCase()} ${phase.replaceAll("_", " ").toUpperCase()}</span>`;
    }).join("");
  }

  function renderPlan(plan) {
    if (!plan) {
      $("#move-plan").textContent = "Planner idle.";
      return;
    }
    const axisLines = Object.values(plan.axes || {}).map((item) => `
      <li>${item.axis.toUpperCase()}: ${formatNumber(item.distance_mm)} mm / ${item.steps} pulses / ${formatNumber(item.speed_mm_s)} mm/s / ${formatNumber(item.duration_s)} s</li>
    `).join("");
    $("#move-plan").innerHTML = `
      <strong>${escapeHtml(String(plan.mode || "speed").toUpperCase())} PLAN</strong>
      <div>Total ${formatNumber(plan.duration_s)} s · Master ${plan.master_steps || 0} steps · Span ${formatNumber(plan.total_distance_mm)} mm</div>
      <ul>${axisLines || "<li>No movement planned</li>"}</ul>
    `;
  }

  function renderSlots() {
    const query = $("#slot-search").value.trim().toLowerCase();
    const entries = Object.entries(state.slots)
      .sort(([a], [b]) => Number(a) - Number(b))
      .filter(([code, slot]) => !query || code.includes(query) || String(slot.product_name || "").toLowerCase().includes(query));

    $("#slot-grid").innerHTML = entries.map(([code, slot]) => `
      <article class="slot-card">
        <div class="slot-head">
          <span>SLOT ${escapeHtml(code)}</span>
          <span>${slot.product_name ? "CONFIGURED" : "EMPTY"}</span>
        </div>
        <h3>${escapeHtml(slot.product_name || `Slot ${code}`)}</h3>
        <p>X ${formatNumber(slot.x_mm, 1)} · Y ${formatNumber(slot.y_mm, 1)} · Z ${formatNumber(slot.z_mm, 1)} mm</p>
        <div class="slot-actions">
          <button data-slot-goto="${escapeHtml(code)}">GO TO</button>
          <button class="primary" data-slot-dispense="${escapeHtml(code)}">START</button>
          <button class="ghost" data-slot-save="${escapeHtml(code)}">SAVE</button>
        </div>
      </article>
    `).join("");

    $$("[data-slot-goto]").forEach((button) => {
      button.disabled = !motionEnabled(true);
      button.addEventListener("click", () => {
        command(`Go to slot ${button.dataset.slotGoto}`, `/api/slots/${button.dataset.slotGoto}/goto`, buildMoveOptions(), { requireHome: true });
      });
    });
    $$("[data-slot-dispense]").forEach((button) => {
      button.disabled = !motionEnabled(true);
      button.addEventListener("click", () => {
        command(`Dispense slot ${button.dataset.slotDispense}`, "/api/start", { slot: button.dataset.slotDispense, ...buildMoveOptions() }, { requireHome: true });
      });
    });
    $$("[data-slot-save]").forEach((button) => {
      button.disabled = !motionEnabled(true);
      button.addEventListener("click", () => {
        command(`Save slot ${button.dataset.slotSave}`, `/api/slots/${button.dataset.slotSave}/save-current`, undefined, { requireHome: true });
      });
    });
  }

  function updateFooter() {
    const now = new Date();
    const status = state.payload?.status || {};
    const operation = state.payload?.operation || {};
    const connection = state.online ? "ONLINE" : "OFFLINE";
    const busy = state.payload?.busy ? "BUSY" : "IDLE";
    const estop = status.estop ? "E-STOP ACTIVE" : "E-STOP CLEAR";
    const active = state.payload?.active_command || "none";
    const message = operation.message || "Waiting for controller status";

    $("#footer-connection").textContent = connection;
    $("#footer-busy").textContent = busy;
    $("#footer-estop").textContent = estop;
    $("#footer-status-text").textContent = `Command: ${active} | Phase: ${operation.phase || "ready"} | Board: ${message}`;
    $("#footer-status-time").textContent = now.toLocaleTimeString();
  }

  function updateInterlocks() {
    const locks = interlocks();
    const reasons = [];
    if (!locks.online) reasons.push("Controller offline");
    if (locks.estop) reasons.push("Emergency stop active");
    if (locks.busy || state.pending) reasons.push("Command in progress");
    if (!locks.homed) reasons.push("Axes not fully homed");
    if (!reasons.length) reasons.push("Ready");

    $("#interlock-list").innerHTML = reasons.map((reason) => `<span>${escapeHtml(reason)}</span>`).join("");
    $("#stop-button").disabled = !locks.online;
    $("#clear-alarm").disabled = !locks.online || locks.busy;
    $("#home-all").disabled = !motionEnabled(false);
    $$(".home-axis").forEach((button) => button.disabled = !motionEnabled(false));
    $$("[data-jog]").forEach((button) => button.disabled = !motionEnabled(false));
    $("#absolute-move").disabled = !motionEnabled(true);
    $("#plan-move").disabled = !locks.online;
    renderSlots();
    updateFooter();
  }

  function render(payload) {
    state.payload = payload;
    state.slots = payload.slots || {};
    const status = payload.status || {};
    const current = status.current_position || {};
    $("#machine-state").textContent = status.estop
      ? "E-STOP ACTIVE"
      : payload.busy
        ? "MOTION ACTIVE"
        : String(payload.operation?.phase || status.state || "ready").toUpperCase();
    $("#operation-phase").textContent = String(payload.operation?.phase || "ready").toUpperCase();
    $("#connection-state").textContent = state.online ? "CONTROLLER ONLINE" : "CONTROLLER OFFLINE";
    $("#operation-message").textContent = payload.operation?.message || "Controller ready";
    $("#override-speed").textContent = status.speed_override ? `${formatNumber(status.speed_override, 1)} mm/s` : "--";
    $("#override-time").textContent = status.timer_seconds ? `${formatNumber(status.timer_seconds, 1)} s` : "--";
    $("#estop-state").textContent = status.estop ? "ACTIVE" : "CLEAR";
    $("#position-summary").innerHTML = `
      <div>X: ${formatNumber(current.x_mm)} mm</div>
      <div>Y: ${formatNumber(current.y_mm)} mm</div>
      <div>Z: ${formatNumber(current.z_mm)} mm</div>
    `;

    renderAxisCards();
    renderHomeStatus();
    renderPlan(status.last_plan);

    if (payload.last_error && payload.last_error !== state.lastError) {
      log(`Controller error: ${payload.last_error}`, "error");
      toast(payload.last_error, true);
    }
    state.lastError = payload.last_error || "";
    updateInterlocks();
  }

  async function refresh() {
    try {
      const payload = await api("/api/status");
      if (!state.online) log("Controller connection established.");
      state.online = true;
      render(payload);
    } catch (error) {
      if (state.online) log(`Controller connection lost: ${error.message}`, "error");
      state.online = false;
      updateFooter();
      updateInterlocks();
      $("#connection-state").textContent = "CONTROLLER OFFLINE";
    }
  }

  async function loadConfig() {
    try {
      state.config = await api("/api/config");
      renderMechanics();
    } catch (error) {
      log(`Config load failed: ${error.message}`, "error");
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
        const body = {
          axis,
          distance_mm: Number($("#jog-step").value) * Number(direction),
        };
        if ($("#jog-time").value !== "") body.time_s = Number($("#jog-time").value);
        command(`Jog ${axis.toUpperCase()}`, "/api/jog", body);
      });
    });
    $("#absolute-move").addEventListener("click", () => {
      const body = buildMovePayload();
      if (!Object.keys(body).some((key) => key.endsWith("_mm"))) {
        toast("Enter at least one target axis.", true);
        return;
      }
      command("Absolute move", "/api/move", body, { requireHome: true });
    });
    $("#plan-move").addEventListener("click", async () => {
      try {
        const response = await api("/api/plan/move", "POST", buildMovePayload());
        renderPlan(response.plan);
        log("Motion plan calculated.");
        toast("Motion plan updated.");
      } catch (error) {
        log(`Plan failed: ${error.message}`, "error");
        toast(`Plan failed: ${error.message}`, true);
      }
    });
    $("#apply-speed").addEventListener("click", () => {
      const value = $("#move-speed").value;
      if (value === "") return toast("Enter speed value first.", true);
      command("Save override speed", "/api/speed", { speed_mm_s: Number(value) }, { stop: true });
    });
    $("#apply-time").addEventListener("click", () => {
      const value = $("#move-time").value;
      if (value === "") return toast("Enter target time first.", true);
      command("Save target time", "/api/timer", { duration_s: Number(value) }, { stop: true });
    });
    $$(".preset").forEach((button) => {
      button.addEventListener("click", () => {
        $("#move-speed").value = button.dataset.speed;
        command(`Set speed ${button.dataset.speed} mm/s`, "/api/speed", { speed_mm_s: Number(button.dataset.speed) }, { stop: true });
      });
    });
    $("#stop-button").addEventListener("click", () => command("Stop motion", "/api/stop", undefined, { stop: true }));
    $("#clear-alarm").addEventListener("click", () => command("Clear alarm", "/api/clear-alarm", undefined, { stop: true }));
    $("#slot-search").addEventListener("input", renderSlots);
  }

  document.addEventListener("DOMContentLoaded", () => {
    bind();
    log("Compact motion console started.");
    loadConfig();
    refresh();
    window.setInterval(refresh, 1000);
    window.setInterval(() => {
      $("#system-time").textContent = new Date().toLocaleTimeString();
      updateFooter();
    }, 1000);
  });
})();
