export function createStreamStatusRefreshScheduler({
  delayMs = 250,
  setTimeoutImpl = setTimeout,
  clearTimeoutImpl = clearTimeout,
  onRefresh,
} = {}) {
  let timeoutId = null;
  let isPending = false;

  function cancel() {
    if (timeoutId !== null) {
      clearTimeoutImpl(timeoutId);
      timeoutId = null;
    }
    isPending = false;
  }

  function schedule() {
    if (isPending) {
      return;
    }

    isPending = true;
    timeoutId = setTimeoutImpl(async () => {
      timeoutId = null;
      isPending = false;

      if (typeof onRefresh === "function") {
        await onRefresh();
      }
    }, delayMs);
  }

  return {
    cancel,
    schedule,
  };
}