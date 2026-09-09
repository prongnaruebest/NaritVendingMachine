/* Selected Slot panel lifecycle — the panel is mounted inside Motion Control. */
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
    const onSelectedChange = (event) => invoke(options.onSelectedChange, event.currentTarget.value);
    const onLoadTarget = () => invoke(options.onLoadTarget);
    const onValidate = () => invoke(options.onValidate);
    const onSequenceToggle = (event) => invoke(options.onSequenceToggle, event.currentTarget.checked);
    const onSelectedGoto = () => invoke(options.onSelectedGoto);

    function mount() {
      const selected = document.getElementById("selected-slot-code");
      const loadTarget = document.getElementById("selected-slot-load-target");
      const validate = document.getElementById("selected-slot-validate");
      const sequenceToggle = document.getElementById("slot-sequence-toggle");
      const selectedGoto = document.getElementById("selected-slot-goto");
      selected?.addEventListener("change", onSelectedChange);
      loadTarget?.addEventListener("click", onLoadTarget);
      validate?.addEventListener("click", onValidate);
      sequenceToggle?.addEventListener("change", onSequenceToggle);
      selectedGoto?.addEventListener("click", onSelectedGoto);
      return () => {
        selected?.removeEventListener("change", onSelectedChange);
        loadTarget?.removeEventListener("click", onLoadTarget);
        validate?.removeEventListener("click", onValidate);
        sequenceToggle?.removeEventListener("change", onSequenceToggle);
        selectedGoto?.removeEventListener("click", onSelectedGoto);
      };
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritSelectedSlotController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
