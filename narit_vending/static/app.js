const state = {
  slots: {},
  busy: false,
  liveUpdate: true,
  monitorUpdate: true,
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.last_error || "Request failed");
  }
  return payload;
}

function byId(id) {
  return document.getElementById(id);
}

function updateAxis(axisName, axis) {
  byId(`${axisName}-pos`).textContent = `${axis.position_mm.toFixed(3)} mm`;
  byId(`${axisName}-flags`).textContent =
    `Home: ${axis.is_homed ? "yes" : "no"} | Min: ${axis.head_limit ? 1 : 0} | Max: ${axis.tail_limit ? 1 : 0}`;
}

function renderSlots() {
  const grid = byId("slot-grid");
  grid.innerHTML = "";
  Object.entries(state.slots).forEach(([code, slot]) => {
    const button = document.createElement("button");
    button.className = "slot-button";
    button.innerHTML = `<strong>Slot ${code}</strong><span>X ${slot.x_mm.toFixed(1)} | Y ${slot.y_mm.toFixed(1)} | Z ${slot.z_mm.toFixed(1)}</span>`;
    button.addEventListener("click", () => loadSlotIntoEditor(code));
    grid.appendChild(button);
  });
}

function loadSlotIntoEditor(code) {
  const slot = state.slots[code];
  byId("slot-code").value = code;
  byId("slot-x").value = slot.x_mm;
  byId("slot-y").value = slot.y_mm;
  byId("slot-z").value = slot.z_mm;
}

function updateView(payload) {
  const { busy, last_error, status, slots } = payload;
  state.slots = slots;
  state.busy = busy;
  byId("machine-state").textContent = busy ? "Busy" : "Idle";
  byId("estop-state").textContent = status.estop ? "ACTIVE" : "Clear";
  byId("last-error").textContent = last_error || "None";
  updateAxis("x", status.x);
  updateAxis("y", status.y);
  updateAxis("z", status.z);
  renderSlots();
  if (state.monitorUpdate) {
    updateMonitor(payload);
  }
}

function updateMonitor(payload) {
  const { busy, last_error, status } = payload;
  const stateStr = busy ? "BUSY" : "IDLE";
  const estopStr = status.estop ? "ACTIVE" : "Clear";
  const errorStr = last_error || "None";

  const pad = (str, len) => str.toString().padEnd(len);

  const text = `=== NARIT VENDING MACHINE STATUS ===
State     : ${stateStr}
E-Stop    : ${estopStr}
Last Error: ${errorStr}

Axis  Position (mm)  Steps     Is Homed  Limit Min (Head)  Limit Max (Tail)
----  -------------  -----     --------  ----------------  ----------------
X     ${pad(status.x.position_mm.toFixed(3), 13)}  ${pad(status.x.position_steps, 9)} ${pad(status.x.is_homed ? "True" : "False", 9)} ${pad(status.x.head_limit ? "True" : "False", 17)} ${status.x.tail_limit ? "True" : "False"}
Y     ${pad(status.y.position_mm.toFixed(3), 13)}  ${pad(status.y.position_steps, 9)} ${pad(status.y.is_homed ? "True" : "False", 9)} ${pad(status.y.head_limit ? "True" : "False", 17)} ${status.y.tail_limit ? "True" : "False"}
Z     ${pad(status.z.position_mm.toFixed(3), 13)}  ${pad(status.z.position_steps, 9)} ${pad(status.z.is_homed ? "True" : "False", 9)} ${pad(status.z.head_limit ? "True" : "False", 17)} ${status.z.tail_limit ? "True" : "False"}`;

  byId("monitor-text").textContent = text;
}

async function refreshStatus() {
  if (!state.liveUpdate) return;
  try {
    const payload = await requestJson("/api/status");
    updateView(payload);
  } catch (error) {
    byId("last-error").textContent = error.message;
  }
}

async function postAction(url, body = null) {
  state.busy = true;
  byId("machine-state").textContent = "Busy";
  const options = { method: "POST" };
  if (body) {
    options.body = JSON.stringify(body);
  }
  try {
    const payload = await requestJson(url, options);
    updateView(payload);
  } catch (error) {
    state.busy = false;
    byId("machine-state").textContent = "Idle";
    throw error;
  }
}

function wireActions() {
  document.querySelectorAll("[data-home]").forEach((button) => {
    button.addEventListener("click", async () => {
      await postAction(`/api/home/${button.dataset.home}`);
    });
  });

  document.querySelectorAll("[data-jog-axis]").forEach((button) => {
    button.addEventListener("click", async () => {
      const step = parseFloat(byId("jog-step").value || "0");
      const distance = step * parseFloat(button.dataset.jogSign);
      await postAction("/api/jog", {
        axis: button.dataset.jogAxis,
        distance_mm: distance,
      });
    });
  });

  byId("stop-motion").addEventListener("click", async () => {
    await postAction("/api/stop");
  });

  byId("load-slot").addEventListener("click", () => {
    loadSlotIntoEditor(byId("slot-code").value);
  });

  byId("save-slot").addEventListener("click", async () => {
    const code = byId("slot-code").value;
    await postAction(`/api/slots/${code}`, {
      x_mm: parseFloat(byId("slot-x").value || "0"),
      y_mm: parseFloat(byId("slot-y").value || "0"),
      z_mm: parseFloat(byId("slot-z").value || "0"),
    });
  });

  byId("save-current").addEventListener("click", async () => {
    const code = byId("slot-code").value;
    await postAction(`/api/slots/${code}/save-current`);
    loadSlotIntoEditor(code);
  });

  byId("goto-slot").addEventListener("click", async () => {
    const code = byId("slot-code").value;
    await postAction(`/api/slots/${code}/goto`);
  });

  byId("live-toggle").addEventListener("click", () => {
    state.liveUpdate = !state.liveUpdate;
    const btn = byId("live-toggle");
    const container = byId("axes-container");
    if (state.liveUpdate) {
      btn.textContent = "Live Status: ON";
      btn.className = "small toggle-active";
      container.style.display = "grid";
      refreshStatus();
    } else {
      btn.textContent = "Live Status: OFF";
      btn.className = "small toggle-inactive";
      container.style.display = "none";
    }
  });

  byId("monitor-toggle").addEventListener("click", () => {
    state.monitorUpdate = !state.monitorUpdate;
    const btn = byId("monitor-toggle");
    const container = byId("monitor-container");
    if (state.monitorUpdate) {
      btn.textContent = "Monitor: ON";
      btn.className = "small toggle-active";
      container.style.display = "block";
      if (state.liveUpdate) {
        refreshStatus();
      }
    } else {
      btn.textContent = "Monitor: OFF";
      btn.className = "small toggle-inactive";
      container.style.display = "none";
    }
  });
}

wireActions();
refreshStatus();
setInterval(refreshStatus, 1000);
