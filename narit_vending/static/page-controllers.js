/* NARIT HMI page lifecycle registry — prevents page-scoped timer/listener leaks. */
(() => {
  "use strict";

  function createRegistry(options = {}) {
    const controllers = new Map();
    let activeView = null;
    let activeCleanup = null;

    function report(error, phase, view) {
      if (typeof options.onError === "function") options.onError(error, { phase, view });
    }

    function register(view, controller) {
      if (!view || !controller || typeof controller.mount !== "function") {
        throw new TypeError("Page controller requires a view and mount function");
      }
      if (controllers.has(view)) throw new Error(`Page controller already registered: ${view}`);
      controllers.set(view, controller);
    }

    function deactivate() {
      const previousView = activeView;
      try {
        if (typeof activeCleanup === "function") activeCleanup();
      } catch (error) {
        report(error, "unmount", previousView);
      }
      activeCleanup = null;
      activeView = null;
    }

    function activate(view) {
      if (activeView === view) return;
      deactivate();
      activeView = view;
      const controller = controllers.get(view);
      if (!controller) return;
      try {
        const cleanup = controller.mount();
        activeCleanup = typeof cleanup === "function"
          ? cleanup
          : (typeof controller.unmount === "function" ? () => controller.unmount() : null);
      } catch (error) {
        activeCleanup = null;
        report(error, "mount", view);
      }
    }

    function dispose() {
      deactivate();
      controllers.clear();
    }

    return Object.freeze({ activate, deactivate, dispose, register });
  }

  Object.defineProperty(window, "NaritPageControllers", {
    value: Object.freeze({ createRegistry }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
