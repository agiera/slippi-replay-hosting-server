// Minimal browser globals for exercising the API modules under `node --test`.
export function installBrowserGlobals() {
  const store = new Map();
  const localStorage = {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
    clear: () => store.clear(),
  };
  Object.defineProperty(globalThis, "localStorage", { value: localStorage, configurable: true, writable: true });
  Object.defineProperty(globalThis, "window", {
    value: { dispatchEvent: () => true, location: { origin: "https://replays.example" } },
    configurable: true,
    writable: true,
  });
  return localStorage;
}

// Replaces fetch with a stub that answers from `responses` in order and records calls.
export function stubFetch(responses) {
  const calls = [];
  const queue = [...responses];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, ...init });
    const next = queue.shift();
    if (!next) {
      throw new Error(`Unexpected fetch: ${url}`);
    }
    const { status = 200, body } = next;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => {
        if (body === undefined) {
          throw new SyntaxError("Unexpected end of JSON input");
        }
        return body;
      },
    };
  };
  return calls;
}
