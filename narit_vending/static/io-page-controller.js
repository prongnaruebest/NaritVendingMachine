/* I/O Status page interactions — read-only filters, search, and refresh lifecycle. */
(() => {
  "use strict";

  function create(options) {
    const filterButtons = () => [...document.querySelectorAll(".io-filter-btn")];
    const searchInput = () => document.getElementById("io-search-input");
    const refreshButton = () => document.getElementById("btn-io-refresh");

    const onFilter = (event) => {
      const selected = event.currentTarget;
      options.state.ioFilter = selected.dataset.ioFilter || "all";
      filterButtons().forEach((button) => button.classList.toggle("active", button === selected));
      options.render();
    };
    const onSearch = (event) => {
      options.state.ioSearch = (event.currentTarget.value || "").toLowerCase().trim();
      options.render();
    };
    const onRefresh = () => {
      Promise.resolve(options.refresh()).catch((error) => options.onError?.(error));
      options.toast("I/O Status refreshed", "ok");
    };

    function mount() {
      const buttons = filterButtons();
      const search = searchInput();
      const refresh = refreshButton();
      buttons.forEach((button) => button.addEventListener("click", onFilter));
      search?.addEventListener("input", onSearch);
      refresh?.addEventListener("click", onRefresh);
      buttons.forEach((button) => {
        button.classList.toggle("active", button.dataset.ioFilter === options.state.ioFilter);
      });
      if (search && search.value !== options.state.ioSearch) search.value = options.state.ioSearch;
      options.render();
      return () => {
        buttons.forEach((button) => button.removeEventListener("click", onFilter));
        search?.removeEventListener("input", onSearch);
        refresh?.removeEventListener("click", onRefresh);
      };
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritIOPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
