/* Motion target workflow controls — lifecycle-scoped and callback-injected. */
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
    const clickBindings = [
      ["target-load-current", options.onLoadCurrent],
      ["target-load-selected-slot", options.onLoadSelectedSlot],
      ["validate-move", options.onValidate],
      ["plan-move", options.onPreview],
      ["arm-move", options.onArm],
      ["absolute-move", options.onExecute],
      ["controlled-stop", options.onControlledStop],
      ["abort-motion", options.onAbort],
    ];

    function mount() {
      const mountedClicks = clickBindings.map(([id, callback]) => {
        const node = document.getElementById(id);
        const handler = () => invoke(callback);
        node?.addEventListener("click", handler);
        return [node, handler];
      });
      const targetInputs = ["move-x", "move-y", "move-z"]
        .map((id) => document.getElementById(id))
        .filter(Boolean);
      const onTargetInput = () => invoke(options.onTargetChanged);
      targetInputs.forEach((node) => node.addEventListener("input", onTargetInput));
      return () => {
        mountedClicks.forEach(([node, handler]) => node?.removeEventListener("click", handler));
        targetInputs.forEach((node) => node.removeEventListener("input", onTargetInput));
      };
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritMotionTargetController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
