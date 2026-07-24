import test from "node:test";
import assert from "node:assert/strict";

import { createStreamStatusRefreshScheduler } from "./homeStreamRefresh.js";

function createTimerHarness() {
  let nextId = 1;
  const scheduled = new Map();

  return {
    setTimeoutImpl(callback, delayMs) {
      const id = nextId++;
      scheduled.set(id, { callback, delayMs });
      return id;
    },
    clearTimeoutImpl(id) {
      scheduled.delete(id);
    },
    runTimer(id) {
      const entry = scheduled.get(id);
      if (!entry) {
        return false;
      }
      scheduled.delete(id);
      return Promise.resolve(entry.callback());
    },
    scheduledCount() {
      return scheduled.size;
    },
    firstTimerId() {
      return scheduled.keys().next().value;
    },
  };
}

test("schedules only one refresh while pending", async () => {
  const timerHarness = createTimerHarness();
  let refreshCount = 0;

  const scheduler = createStreamStatusRefreshScheduler({
    delayMs: 250,
    setTimeoutImpl: timerHarness.setTimeoutImpl,
    clearTimeoutImpl: timerHarness.clearTimeoutImpl,
    onRefresh: async () => {
      refreshCount += 1;
    },
  });

  scheduler.schedule();
  scheduler.schedule();
  scheduler.schedule();

  assert.equal(timerHarness.scheduledCount(), 1);

  await timerHarness.runTimer(timerHarness.firstTimerId());

  assert.equal(refreshCount, 1);
});

test("allows a new refresh after the previous one completes", async () => {
  const timerHarness = createTimerHarness();
  let refreshCount = 0;

  const scheduler = createStreamStatusRefreshScheduler({
    delayMs: 250,
    setTimeoutImpl: timerHarness.setTimeoutImpl,
    clearTimeoutImpl: timerHarness.clearTimeoutImpl,
    onRefresh: async () => {
      refreshCount += 1;
    },
  });

  scheduler.schedule();
  await timerHarness.runTimer(timerHarness.firstTimerId());
  scheduler.schedule();

  assert.equal(timerHarness.scheduledCount(), 1);

  await timerHarness.runTimer(timerHarness.firstTimerId());

  assert.equal(refreshCount, 2);
});

test("cancel clears a pending refresh", () => {
  const timerHarness = createTimerHarness();
  const scheduler = createStreamStatusRefreshScheduler({
    delayMs: 250,
    setTimeoutImpl: timerHarness.setTimeoutImpl,
    clearTimeoutImpl: timerHarness.clearTimeoutImpl,
    onRefresh: async () => {},
  });

  scheduler.schedule();
  assert.equal(timerHarness.scheduledCount(), 1);

  scheduler.cancel();
  assert.equal(timerHarness.scheduledCount(), 0);
});