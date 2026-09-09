/* System Flow page interaction — read-only inspection of Controller-derived state. */
(() => {
  "use strict";

  function create(options) {
    const nodes = () => [...document.querySelectorAll(".flow-node")];

    const onNodeClick = (event) => {
      const node = event.currentTarget;
      const detail = document.getElementById("flow-step-detail");
      if (!detail) return;
      const state = [...node.classList].find((name) => (
        ["complete", "active", "blocked", "pending"].includes(name)
      )) || "pending";
      const title = document.createElement("strong");
      title.textContent = node.querySelector("strong")?.textContent || "Step";
      const stateLine = document.createElement("p");
      stateLine.textContent = `State: ${state.toUpperCase()}`;
      const explanation = document.createElement("p");
      explanation.textContent = (
        "Preconditions and live state are evaluated by Controller safety interlocks. "
        + `Current command: ${options.state.payload?.active_command || "NONE"}. `
        + "No machine command is sent from this panel."
      );
      detail.replaceChildren(title, stateLine, explanation);
    };

    function mount() {
      const flowNodes = nodes();
      flowNodes.forEach((node) => node.addEventListener("click", onNodeClick));
      return () => flowNodes.forEach((node) => node.removeEventListener("click", onNodeClick));
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritFlowPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
