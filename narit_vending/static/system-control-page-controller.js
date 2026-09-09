/* System Control & Health actions — lifecycle-scoped and callback-injected. */
(() => {
  "use strict";

  function create(options) {
    const invoke = (callback) => {
      try {
        Promise.resolve(callback?.()).catch((error) => options.onError?.(error));
      } catch (error) {
        options.onError?.(error);
      }
    };
    const bindings = [
      ["system-motion-disable", () => invoke(options.onDisableMotion)],
      ["system-motion-enable", () => invoke(options.onEnableMotion)],
      ["system-nucleo-reset", () => invoke(options.onResetNucleoLink)],
      ["system-drive-power-reset", () => invoke(options.onResetDrivePower)],
      ["system-drive-power-cut", () => invoke(options.onCutDrivePower)],
      ["system-drive-power-restore", () => invoke(options.onRestoreDrivePower)],
    ];

    function mount() {
      const mounted = bindings.map(([id, handler]) => [document.getElementById(id), handler]);
      mounted.forEach(([node, handler]) => node?.addEventListener("click", handler));
      return () => mounted.forEach(([node, handler]) => node?.removeEventListener("click", handler));
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritSystemControlPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
