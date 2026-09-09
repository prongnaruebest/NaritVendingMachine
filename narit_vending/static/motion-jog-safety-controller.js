/* Manual Jog fail-safe lifecycle — stop on blur, hidden page and unmount. */
(() => {
  "use strict";
  function create(options) {
    const stop = () => options.onStop?.();
    const visibility = () => { if (document.hidden) stop(); };
    const changed = () => options.onAllowUnhomedChanged?.();
    const keyMap = { ArrowLeft:["x","-1"], ArrowRight:["x","1"], ArrowDown:["y","-1"], ArrowUp:["y","1"], PageDown:["z","-1"], PageUp:["z","1"] };
    const keydown = (event) => {
      if (!options.isKeyboardEnabled?.() || event.repeat) return;
      const active = document.activeElement;
      if (["input","select","textarea","button"].includes(active?.tagName?.toLowerCase()) || active?.isContentEditable) return;
      const move = keyMap[event.key]; if (!move) return;
      event.preventDefault();
      options.onBegin?.(move[0], move[1], document.querySelector(`[data-jog="${move[0]}:${move[1]}"]`), event);
    };
    const keyup = (event) => { const move=keyMap[event.key]; if (move && options.isKeyboardEnabled?.()) options.onEnd?.(move[0],move[1],document.querySelector(`[data-jog="${move[0]}:${move[1]}"]`)); };
    function mount() {
      const allow = document.getElementById("jog-allow-unhomed");
      const keyboard = document.getElementById("jog-keyboard-enable");
      const buttons = [...document.querySelectorAll("[data-jog]")];
      const directional = buttons.map((button) => {
        const [axis, direction] = button.dataset.jog.split(":");
        const down=(event)=>{event.preventDefault(); options.onBegin?.(axis,direction,button,event);};
        const up=(event)=>{event.preventDefault(); options.onEnd?.(axis,direction,button);};
        const cancel=()=>stop(); const prevent=(event)=>event.preventDefault();
        [["pointerdown",down],["pointerup",up],["pointercancel",cancel],["lostpointercapture",cancel],["contextmenu",prevent],["click",prevent]].forEach(([name,handler])=>button.addEventListener(name,handler));
        return [button, [["pointerdown",down],["pointerup",up],["pointercancel",cancel],["lostpointercapture",cancel],["contextmenu",prevent],["click",prevent]]];
      });
      const keyboardChanged=()=>options.onKeyboardToggle?.(Boolean(keyboard?.checked));
      window.addEventListener("blur", stop);
      document.addEventListener("visibilitychange", visibility);
      allow?.addEventListener("change", changed);
      keyboard?.addEventListener("change", keyboardChanged);
      document.addEventListener("keydown", keydown);
      document.addEventListener("keyup", keyup);
      return () => {
        stop();
        window.removeEventListener("blur", stop);
        document.removeEventListener("visibilitychange", visibility);
        allow?.removeEventListener("change", changed);
        keyboard?.removeEventListener("change", keyboardChanged);
        document.removeEventListener("keydown", keydown);
        document.removeEventListener("keyup", keyup);
        directional.forEach(([button, events])=>events.forEach(([name,handler])=>button.removeEventListener(name,handler)));
      };
    }
    return Object.freeze({ mount });
  }
  Object.defineProperty(window, "NaritMotionJogSafetyController", {
    value: Object.freeze({ create }), configurable: false, enumerable: false, writable: false,
  });
})();
