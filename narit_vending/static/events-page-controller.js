/* Event Log page interactions — read-only filtering, detail selection, and export. */
(() => {
  "use strict";

  function create(options) {
    const inputDefinitions = Object.freeze({
      search: "event-search",
      severity: "event-severity-filter",
      category: "event-category-filter",
      outcome: "event-outcome-filter",
    });
    const inputs = () => Object.fromEntries(
      Object.entries(inputDefinitions).map(([key, id]) => [key, document.getElementById(id)]),
    );
    const quickButtons = () => [...document.querySelectorAll("[data-event-quick]")];

    function syncInputs() {
      Object.entries(inputs()).forEach(([key, input]) => {
        if (input && input.value !== options.state.eventFilters[key]) {
          input.value = options.state.eventFilters[key];
        }
      });
    }

    const onInput = (event) => {
      const key = event.currentTarget.dataset.eventFilterKey;
      options.state.eventFilters[key] = event.currentTarget.value;
      options.render();
    };
    const onClear = () => {
      options.state.eventFilters = { search: "", severity: "all", category: "all", outcome: "all" };
      syncInputs();
      quickButtons().forEach((button) => {
        button.classList.toggle("active", button.dataset.eventQuick === "all");
      });
      options.render();
    };
    const onQuickFilter = (event) => {
      const selected = event.currentTarget;
      const quick = selected.dataset.eventQuick;
      options.state.eventFilters = { search: "", severity: "all", category: "all", outcome: "all" };
      if (["fault", "warn"].includes(quick)) options.state.eventFilters.severity = quick;
      else if (quick !== "all") options.state.eventFilters.category = quick;
      syncInputs();
      quickButtons().forEach((button) => button.classList.toggle("active", button === selected));
      options.render();
    };
    const onDetail = (event) => {
      const button = event.target.closest?.("[data-event-detail]");
      if (!button) return;
      options.state.selectedEventId = button.dataset.eventDetail;
      options.render();
    };
    const onExport = () => options.exportCsv();

    function mount() {
      const filterInputs = inputs();
      const buttons = quickButtons();
      const clear = document.getElementById("event-clear-filters");
      const exportButton = document.getElementById("event-export-csv");
      const eventPage = document.getElementById("event-log-page");
      Object.entries(filterInputs).forEach(([key, input]) => {
        if (!input) return;
        input.dataset.eventFilterKey = key;
        input.addEventListener("input", onInput);
      });
      buttons.forEach((button) => button.addEventListener("click", onQuickFilter));
      clear?.addEventListener("click", onClear);
      exportButton?.addEventListener("click", onExport);
      eventPage?.addEventListener("click", onDetail);
      syncInputs();
      options.render();

      return () => {
        Object.values(filterInputs).forEach((input) => input?.removeEventListener("input", onInput));
        buttons.forEach((button) => button.removeEventListener("click", onQuickFilter));
        clear?.removeEventListener("click", onClear);
        exportButton?.removeEventListener("click", onExport);
        eventPage?.removeEventListener("click", onDetail);
      };
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritEventsPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
