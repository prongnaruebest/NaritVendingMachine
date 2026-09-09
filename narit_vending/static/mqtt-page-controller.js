/* MQTT Monitor page controls — lifecycle-scoped user requests only. */
(() => {
  "use strict";

  function create(options) {
    const connect = () => options.control("connect");
    const disconnect = () => options.control("disconnect");

    function mount() {
      const connectButton = document.getElementById("mqtt-connect");
      const disconnectButton = document.getElementById("mqtt-disconnect");
      connectButton?.addEventListener("click", connect);
      disconnectButton?.addEventListener("click", disconnect);
      options.render();
      return () => {
        connectButton?.removeEventListener("click", connect);
        disconnectButton?.removeEventListener("click", disconnect);
      };
    }

    return Object.freeze({ mount });
  }

  Object.defineProperty(window, "NaritMqttPageController", {
    value: Object.freeze({ create }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
