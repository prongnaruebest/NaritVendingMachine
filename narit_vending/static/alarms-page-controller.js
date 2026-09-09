/* Alarms page control — delegates reset request to the Controller command path. */
(() => {
  "use strict";

  function create(options) {
    const onReset = () => options.reset();

    function mount() {
      const resetButton = document.getElementById("page-clear-alarm");
      resetButton?.addEventListener("click", onReset);
      return () => resetButton?.removeEventListener("click", onReset);
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritAlarmsPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
