/* Positions & Slots table lifecycle — delegation over dynamically rendered rows. */
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
    const onSearch = () => options.render();
    const onCoordinate = (event) => {
      const input = event.target.closest?.("[data-slot-coordinate]");
      if (input) invoke(options.onCoordinate, input.dataset.slotCoordinate, input.dataset.slotAxis, input.value);
    };
    const onTableClick = (event) => {
      const button = event.target.closest?.("button");
      if (!button || button.disabled) return;
      if (button.dataset.slotUpdate) invoke(options.onSave, button.dataset.slotUpdate);
      else if (button.dataset.slotSelect) invoke(options.onSelect, button.dataset.slotSelect);
      else if (button.dataset.slotGoto) invoke(options.onGoto, button.dataset.slotGoto);
      else if (button.dataset.slotDispense) invoke(options.onDispense, button.dataset.slotDispense);
      else if (button.dataset.slotTeach) invoke(options.onTeach, button.dataset.slotTeach);
    };

    function mount() {
      const search = document.getElementById("slot-search");
      const filter = document.getElementById("slot-filter");
      const table = document.getElementById("slot-grid");
      search?.addEventListener("input", onSearch);
      filter?.addEventListener("change", onSearch);
      table?.addEventListener("input", onCoordinate);
      table?.addEventListener("click", onTableClick);
      options.render();
      return () => {
        search?.removeEventListener("input", onSearch);
        filter?.removeEventListener("change", onSearch);
        table?.removeEventListener("input", onCoordinate);
        table?.removeEventListener("click", onTableClick);
      };
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritSlotsPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
