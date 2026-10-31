// Runtime configuration read from Vite env vars. `import.meta.env` is undefined
// under plain `node --test`, so every read is optional-chained.
const env = import.meta.env ?? {};

export const API_BASE = env.VITE_API_BASE_URL || "/api/v1";

export const TAB_NAME = env.VITE_TAB_NAME || "Slippi Replay Hosting";

export const SLIPPILAB_URL = (() => {
  const configured = String(env.VITE_SLIPPILAB_URL || "").trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin.replace(/\/$/, "")}/slippilab`;
  }

  return "";
})();
