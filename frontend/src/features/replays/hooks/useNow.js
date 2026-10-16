import { useEffect, useState } from "react";

// Current time in ms, re-rendering every `intervalMs` (drives live game timers).
export function useNow(intervalMs = 1000) {
  const [nowMs, setNowMs] = useState(Date.now());

  useEffect(() => {
    const timerId = setInterval(() => setNowMs(Date.now()), intervalMs);
    return () => clearInterval(timerId);
  }, [intervalMs]);

  return nowMs;
}
