/* NARIT HMI hash router — navigation lifecycle only; no machine commands. */
(() => {
  "use strict";

  function createRouter(options) {
    const validViews = new Set(options.validViews || []);
    const fallbackView = options.fallbackView || "motion";
    const groups = options.groups || [];
    let started = false;

    const normalize = (view) => validViews.has(view) ? view : fallbackView;

    function render(view, updateHash) {
      const nextView = normalize(view);
      const previousView = options.state.currentView;
      if (previousView !== nextView) options.beforeNavigate?.(previousView, nextView);
      options.state.currentView = nextView;

      document.querySelectorAll("[data-view-page]").forEach((page) => {
        page.classList.toggle("active", page.dataset.viewPage === nextView);
      });
      document.querySelectorAll("[data-view-target]").forEach((button) => {
        const grouped = groups.some((group) => (
          button.id === group.primaryId
          && (typeof group.views?.has === "function"
            ? group.views.has(nextView)
            : group.views?.includes(nextView))
        ));
        const active = button.dataset.viewTarget === nextView || grouped;
        button.classList.toggle("active", active);
        if (active) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
      });

      const shell = document.querySelector(".hmi-shell");
      if (shell) {
        shell.classList.toggle("view-wide", nextView !== "motion");
        shell.classList.toggle("view-dashboard", nextView === "dashboard");
      }
      if (updateHash && window.location.hash !== `#${nextView}`) {
        window.history.replaceState(null, "", `#${nextView}`);
      }
      options.afterNavigate?.(nextView, previousView);
      return nextView;
    }

    const onTargetClick = (event) => {
      const button = event.currentTarget;
      render(button.dataset.viewTarget, true);
    };
    const onHashChange = () => render(window.location.hash.slice(1), false);

    function start() {
      if (started) return;
      started = true;
      document.querySelectorAll("[data-view-target]").forEach((button) => {
        button.addEventListener("click", onTargetClick);
      });
      window.addEventListener("hashchange", onHashChange);
    }

    function stop() {
      if (!started) return;
      started = false;
      document.querySelectorAll("[data-view-target]").forEach((button) => {
        button.removeEventListener("click", onTargetClick);
      });
      window.removeEventListener("hashchange", onHashChange);
    }

    return Object.freeze({ navigate: render, normalize, start, stop });
  }

  Object.defineProperty(window, "NaritRouter", {
    value: Object.freeze({ create: createRouter }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
