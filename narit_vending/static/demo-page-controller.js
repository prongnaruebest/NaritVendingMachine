/* Demo Slot Sampling controls — lifecycle-scoped and callback-injected. */
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
    const handlers = {
      configure: () => invoke(options.onConfigure),
      validate: () => invoke(options.onValidate),
      arm: () => invoke(options.onArm),
      start: () => invoke(options.onStart),
      pause: () => invoke(options.onPause),
      resume: () => invoke(options.onResume),
      stop: () => invoke(options.onStop),
      refresh: () => invoke(options.onRefresh),
      parameters: () => invoke(options.onParametersChanged),
    };

    function mount() {
      const bindings = [
        [document.getElementById("demo-configure"), "click", handlers.configure],
        [document.getElementById("demo-validate"), "click", handlers.validate],
        [document.getElementById("demo-arm"), "click", handlers.arm],
        [document.getElementById("demo-start"), "click", handlers.start],
        [document.getElementById("demo-pause"), "click", handlers.pause],
        [document.getElementById("demo-resume"), "click", handlers.resume],
        [document.getElementById("demo-stop"), "click", handlers.stop],
        [document.getElementById("demo-history-refresh"), "click", handlers.refresh],
        [document.getElementById("demo-mode"), "input", handlers.parameters],
        [document.getElementById("demo-max-cycles"), "input", handlers.parameters],
        [document.getElementById("demo-dwell"), "input", handlers.parameters],
      ];
      bindings.forEach(([node, eventName, handler]) => node?.addEventListener(eventName, handler));
      return () => bindings.forEach(([node, eventName, handler]) => node?.removeEventListener(eventName, handler));
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritDemoPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
