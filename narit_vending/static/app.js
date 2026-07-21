(() => {
  "use strict";
  const state = { online: false, pending: false, payload: null, slots: {}, events: [], lastError: "" };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const axes = ["x", "y", "z"];

  function escape(value) { return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character])); }
  function log(message, level = "info") {
    state.events.unshift({ at: new Date(), message, level }); state.events = state.events.slice(0, 40);
    $("#event-log").innerHTML = state.events.map((entry) => `<li class="${entry.level}"><time>${entry.at.toLocaleTimeString()}</time>${escape(entry.message)}</li>`).join("");
  }
  function toast(message, error = false) { const element = $("#toast"); element.textContent = message; element.className = `toast show${error ? " error" : ""}`; window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => element.className = "toast", 3600); }
  async function api(path, method = "GET", body) {
    const abort = new AbortController(); const timer = setTimeout(() => abort.abort(), 8000);
    try { const response = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined, signal: abort.signal }); const data = await response.json(); if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`); return data; } finally { clearTimeout(timer); }
  }
  function interlocks() { const status = state.payload?.status || {}; const homed = axes.every((axis) => status[axis]?.is_homed); return { estop: Boolean(status.estop), busy: Boolean(state.payload?.busy), homed }; }
  function motionEnabled(requireHome = false) { const locks = interlocks(); return state.online && !state.pending && !locks.estop && !locks.busy && (!requireHome || locks.homed); }
  async function command(label, path, body, options = {}) {
    if (!options.stop && !motionEnabled(options.requireHome)) { toast("Command blocked by controller state or safety interlock.", true); log(`${label} blocked by an interlock.`, "error"); return; }
    state.pending = !options.stop; updateInterlocks(); log(`${label} requested.`);
    try { await api(path, "POST", body); toast(`${label} accepted.`); log(`${label} accepted.`); await refresh(); } catch (error) { toast(`${label}: ${error.message}`, true); log(`${label} failed: ${error.message}`, "error"); } finally { state.pending = false; updateInterlocks(); }
  }
  function updateConnection() { const element = $(".connection"); element.className = `connection ${state.online ? "online" : "offline"}`; $("#connection-state").textContent = state.online ? "CONTROLLER ONLINE" : "CONTROLLER OFFLINE"; }
  function updateHoming(operation, status) {
    axes.forEach((axis) => {
      const phase = operation.homing?.[axis] || (status[axis]?.is_homed ? "passed" : "not_homed");
      const card = $(`.home-step[data-axis="${axis}"]`); card.className = `home-step ${phase}`;
      $(`#home-${axis}`).textContent = phase.toUpperCase().replace("_", " ");
      const detail = phase === "waiting" ? "Waiting for earlier axis" : phase === "homing" ? `Searching home sensor on axis ${axis.toUpperCase()}` : phase === "passed" ? "Home sensor reached; reference accepted" : phase === "failed" ? operation.message : "Axis must be homed before automatic movement";
      $(`#home-${axis}-detail`).textContent = detail;
    });
  }
  function badge(element, active, activeText, idleText, alarm = false) { element.textContent = active ? activeText : idleText; element.className = active ? (alarm ? "alarm" : "active") : ""; }
  function render(payload) {
    state.payload = payload; const status = payload.status || {}; const operation = payload.operation || {}; const locks = interlocks();
    const visualState = status.estop ? "E-STOP ACTIVE" : payload.busy ? "MOTION ACTIVE" : (operation.phase || status.state || "ready").toUpperCase();
    $("#machine-state").textContent = visualState; $("#estop-state").textContent = status.estop ? "E-STOP ACTIVE" : "E-STOP CLEAR";
    const opCard = $("#operation-card"); opCard.className = `operation-card ${operation.phase || "ready"}`;
    $("#operation-message").textContent = operation.message || "No operation in progress"; $("#operation-phase").textContent = (operation.phase || "ready").toUpperCase();
    $("#operation-detail").textContent = operation.active_axis ? `Active axis: ${operation.active_axis.toUpperCase()}. Home order: Z → X → Y.` : (payload.active_command ? `Active command: ${payload.active_command}` : "Controller is standing by.");
    updateHoming(operation, status);
    axes.forEach((axis) => { const axisStatus = status[axis] || {}; $(`#position-${axis}`).textContent = `${Number(axisStatus.position_mm || 0).toFixed(2)} mm`; badge($(`#${axis}-homed`), axisStatus.is_homed, "HOMED", "NOT HOMED"); badge($(`#${axis}-min`), axisStatus.head_limit, "MIN ACTIVE", "MIN", true); badge($(`#${axis}-max`), axisStatus.tail_limit, "MAX ACTIVE", "MAX", true); });
    $("#updated-at").textContent = payload.timestamp ? `Updated ${new Date(payload.timestamp).toLocaleTimeString()}` : "Updated now";
    $("#diag-command").textContent = payload.active_command || "None"; $("#diag-error").textContent = payload.last_error || "None"; $("#diag-state").textContent = status.state || "unknown";
    const sensorRows = [["Emergency stop", status.estop], ...axes.flatMap((axis) => [[`Axis ${axis.toUpperCase()} home/min`, status[axis]?.head_limit], [`Axis ${axis.toUpperCase()} max`, status[axis]?.tail_limit]])];
    $("#sensor-table").innerHTML = sensorRows.map(([name, active]) => `<tr><td>${name}</td><td class="${active ? "sensor-alarm" : "sensor-ok"}">${active ? "ACTIVE" : "NORMAL"}</td></tr>`).join("");
    if (payload.last_error && payload.last_error !== state.lastError) { log(`Controller error: ${payload.last_error}`, "error"); toast(payload.last_error, true); } state.lastError = payload.last_error || "";
    renderSlots(); updateInterlocks();
  }
  function updateInterlocks() {
    const locks = interlocks(); const reason = !state.online ? "CONTROLLER OFFLINE" : locks.estop ? "E-STOP ACTIVE" : locks.busy || state.pending ? "COMMAND IN PROGRESS" : locks.homed ? "READY" : "HOME ALL AXES BEFORE AUTO MOVE";
    $("#manual-interlock").textContent = reason;
    $$('[data-command="jog"],[data-command="home"],[data-command="move"]').forEach((button) => button.disabled = !motionEnabled(false));
    $$('[data-command="slot"]').forEach((button) => button.disabled = !motionEnabled(true));
    $("#clear-alarm").disabled = !state.online || locks.estop || locks.busy;
    $("#stop-button").disabled = !state.online;
  }
  function renderSlots() {
    const query = $("#slot-search").value.trim().toLowerCase(); const container = $("#slot-grid");
    container.innerHTML = Object.entries(state.slots).sort(([a], [b]) => Number(a) - Number(b)).filter(([code, slot]) => !query || code.includes(query) || String(slot.product_name || "").toLowerCase().includes(query)).map(([code, slot]) => `<article class="slot"><div class="slot-top"><small>SLOT ${escape(code)}</small><span>${slot.product_name ? "CONFIGURED" : "UNASSIGNED"}</span></div><h2>${escape(slot.product_name || `Slot ${code}`)}</h2><p>X ${Number(slot.x_mm).toFixed(1)} · Y ${Number(slot.y_mm).toFixed(1)} · Z ${Number(slot.z_mm).toFixed(1)} mm</p><div class="slot-actions"><button data-command="slot" data-goto="${escape(code)}">GO TO</button><button class="primary" data-command="slot" data-dispense="${escape(code)}">DISPENSE</button></div></article>`).join("");
    $$('[data-goto]').forEach((button) => button.addEventListener("click", () => command(`Go to slot ${button.dataset.goto}`, `/api/slots/${button.dataset.goto}/goto`, undefined, { requireHome: true })));
    $$('[data-dispense]').forEach((button) => button.addEventListener("click", () => command(`Dispense slot ${button.dataset.dispense}`, "/api/start", { slot: button.dataset.dispense }, { requireHome: true })));
  }
  async function refresh() { try { const payload = await api("/api/status"); if (!state.online) log("Controller connection established."); state.online = true; render(payload); } catch (error) { if (state.online) log(`Controller connection lost: ${error.message}`, "error"); state.online = false; updateConnection(); updateInterlocks(); } finally { updateConnection(); } }
  function bind() {
    $$(".nav").forEach((button) => button.addEventListener("click", () => { $$(".nav").forEach((node) => node.classList.toggle("active", node === button)); $$(".page").forEach((page) => page.classList.toggle("active", page.id === button.dataset.page)); }));
    $("#home-all").dataset.command = "home"; $("#home-all").addEventListener("click", () => command("Home all axes", "/api/home/all"));
    $$(".home-axis").forEach((button) => { button.dataset.command = "home"; button.addEventListener("click", () => command(`Home axis ${button.dataset.axis.toUpperCase()}`, `/api/home/${button.dataset.axis}`)); });
    $$("[data-jog]").forEach((button) => { button.dataset.command = "jog"; button.addEventListener("click", () => { const [axis, direction] = button.dataset.jog.split(":"); command(`Jog ${axis.toUpperCase()}`, "/api/jog", { axis, distance_mm: Number($("#jog-step").value) * Number(direction) }); }); });
    $("#absolute-move").dataset.command = "move"; $("#absolute-move").addEventListener("click", () => { const body = {}; axes.forEach((axis) => { const value = $(`#move-${axis}`).value; if (value !== "") body[`${axis}_mm`] = Number(value); }); if (!Object.keys(body).length) return toast("Enter at least one target position.", true); command("Absolute move", "/api/move", body, { requireHome: true }); });
    $("#stop-button").addEventListener("click", () => command("Stop motion", "/api/stop", undefined, { stop: true })); $("#clear-alarm").addEventListener("click", () => command("Clear alarm", "/api/clear-alarm", undefined, { stop: true })); $("#slot-search").addEventListener("input", renderSlots);
  }
  document.addEventListener("DOMContentLoaded", () => { bind(); log("HMI started; waiting for controller status."); refresh(); setInterval(refresh, 500); setInterval(() => $("#system-time").textContent = new Date().toLocaleTimeString(), 1000); });
})();
