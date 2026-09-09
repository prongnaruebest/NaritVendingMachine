/* NARIT HMI API client — transport only; never owns machine state or hardware authority. */
(() => {
  "use strict";

  const DEFAULT_TIMEOUT_MS = 8000;

  async function request(path, method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS) {
    const controller = new AbortController();
    const boundedTimeout = Number.isFinite(Number(timeoutMs)) && Number(timeoutMs) > 0
      ? Number(timeoutMs)
      : DEFAULT_TIMEOUT_MS;
    const timer = window.setTimeout(() => controller.abort(), boundedTimeout);

    try {
      const response = await window.fetch(path, {
        method,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
      const responseText = await response.text();
      let data = {};
      if (responseText) {
        try {
          data = JSON.parse(responseText);
        } catch {
          throw new Error(
            response.ok ? "Controller returned an invalid response" : `HTTP ${response.status}`,
          );
        }
      }
      if (!response.ok || data.ok === false) {
        throw new Error(
          data.error
          || data.reason
          || data.message
          || (response.ok
            ? "Controller rejected the command without a reason"
            : `HTTP ${response.status}`),
        );
      }
      return data;
    } finally {
      window.clearTimeout(timer);
    }
  }

  Object.defineProperty(window, "NaritApiClient", {
    value: Object.freeze({ request }),
    configurable: false,
    enumerable: false,
    writable: false,
  });
})();
