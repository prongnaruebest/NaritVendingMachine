/* Manual Jog fail-safe lifecycle — stop on blur, hidden page and unmount. */
(() => {
  "use strict";
  function create(options) {
    const stop = () => options.onStop?.();
    const visibility = () => { if (document.hidden) stop(); };
    const changed = () => options.onAllowUnhomedChanged?.();
    function mount() {
      const allow = document.getElementById("jog-allow-unhomed");
      window.addEventListener("blur", stop);
      document.addEventListener("visibilitychange", visibility);
      allow?.addEventListener("change", changed);
      return () => {
        stop();
        window.removeEventListener("blur", stop);
        document.removeEventListener("visibilitychange", visibility);
        allow?.removeEventListener("change", changed);
      };
    }
    return Object.freeze({ mount });
  }
  Object.defineProperty(window, "NaritMotionJogSafetyController", {
    value: Object.freeze({ create }), configurable: false, enumerable: false, writable: false,
  });
})();
