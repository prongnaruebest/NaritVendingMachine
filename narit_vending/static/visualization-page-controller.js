/* Machine Visualization controls — lifecycle-scoped and callback-injected. */
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
      grid: (event) => {
        const button = event.target.closest?.("[data-visual-slot]");
        if (button) invoke(options.onSelect, button.dataset.visualSlot);
      },
      select: (event) => invoke(options.onSelect, String(event.currentTarget.value || "1")),
      coordinate: (event) => invoke(options.onCoordinateInput, event.currentTarget.dataset.visualAxis),
      loadCurrent: () => invoke(options.onLoadCurrent),
      save: () => invoke(options.onSave),
      loadTarget: () => invoke(options.onLoadTarget),
      homeAll: () => invoke(options.onHomeAll),
      goto: () => invoke(options.onGoto),
      preview: () => invoke(options.onPreview),
      sendToMotion: () => invoke(options.onSendToMotion),
      edit: () => invoke(options.onEdit),
      cancelEdit: () => invoke(options.onCancelEdit),
    };

    function mount() {
      const bindings = [
        [document.getElementById("visual-slot-grid"), "click", handlers.grid],
        [document.getElementById("visual-command-slot"), "change", handlers.select],
        [document.getElementById("visual-slot-load-current"), "click", handlers.loadCurrent],
        [document.getElementById("visual-slot-save"), "click", handlers.save],
        [document.getElementById("visual-command-load"), "click", handlers.loadTarget],
        [document.getElementById("visual-home-all"), "click", handlers.homeAll],
        [document.getElementById("visual-slot-goto"), "click", handlers.goto],
        [document.getElementById("visual-load-preview"), "click", handlers.preview],
        [document.getElementById("visual-send-motion"), "click", handlers.sendToMotion],
        [document.getElementById("visual-edit-enable"), "click", handlers.edit],
        [document.getElementById("visual-edit-cancel"), "click", handlers.cancelEdit],
      ];
      ["x", "y", "z"].forEach((axis) => {
        const input = document.getElementById(`visual-slot-${axis}`);
        if (input) input.dataset.visualAxis = axis;
        bindings.push([input, "input", handlers.coordinate]);
      });
      bindings.forEach(([node, eventName, handler]) => node?.addEventListener(eventName, handler));
      return () => bindings.forEach(([node, eventName, handler]) => node?.removeEventListener(eventName, handler));
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritVisualizationPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
