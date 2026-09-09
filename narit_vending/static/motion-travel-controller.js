/* Motion homing and travel controls — lifecycle-scoped and callback-injected. */
(() => {
  "use strict";

  function create(options) {
    const invoke = (callback, ...args) => {
      try {
        Promise.resolve(callback?.(...args)).catch((error) => options.onError?.(error));
      } catch (error) {
        options.onError?.(error);
      }
    };

    function mount() {
      const bindings = [];
      const bind = (node, handler) => {
        if (!node) return;
        node.addEventListener("click", handler);
        bindings.push([node, handler]);
      };
      bind(document.getElementById("home-all"), () => invoke(options.onHomeAll));
      document.querySelectorAll(".home-axis").forEach((button) => {
        bind(button, () => invoke(options.onHomeAxis, button.dataset.axis));
      });
      bind(document.getElementById("operator-stop"), () => invoke(options.onStop));
      bind(document.getElementById("travel-reset-interlock"), () => invoke(options.onResetInterlock));
      document.querySelectorAll("[data-travel-axis]").forEach((button) => {
        bind(button, () => invoke(options.onMoveToLimit, button.dataset.travelAxis, button.dataset.travelLimit));
      });
      document.querySelectorAll("[data-axis-goto]").forEach((button) => {
        bind(button, () => invoke(options.onMoveToPosition, button.dataset.axisGoto));
      });
      return () => bindings.forEach(([node, handler]) => node.removeEventListener("click", handler));
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritMotionTravelController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
