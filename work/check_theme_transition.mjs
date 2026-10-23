import test from 'node:test';
import assert from 'node:assert/strict';
import {transitionTheme, cancelThemeTransition} from '../frontend/vendor/design-systems/theme-transition.js';

function page() {
  const classes = new Set(), calls = [];
  const root = {dataset: {}, classList: {add: value => classes.add(value), remove: value => classes.delete(value)},
    getBoundingClientRect: () => ({left: 0, top: 0, width: 1000, height: 700}),
    animate(frames, options) {calls.push({frames, options}); return {finished: Promise.resolve()};}};
  globalThis.document = {documentElement: root, hidden: false};
  globalThis.innerWidth = 1000; globalThis.innerHeight = 700;
  return {root, classes, calls};
}

test('unsupported WebEngine applies once without animation', async () => {
  const state = page(); let applied = 0;
  assert.equal(await transitionTheme(() => applied++, {origin: [20, 30]}), 'instant');
  assert.equal(applied, 1); assert.equal(state.classes.size, 0);
});

test('reduced, hidden and native system changes never start a spatial transition', async () => {
  for (const mode of ['reduced', 'hidden', 'system']) {
    page(); document.startViewTransition = () => {throw new Error('must not animate');};
    document.hidden = mode === 'hidden'; let applied = false;
    assert.equal(await transitionTheme(() => {applied = true;}, {origin: mode === 'system' ? null : [20, 30], reduced: mode === 'reduced'}), 'instant');
    assert.ok(applied);
  }
});

test('adapted Overture iris uses trigger center, 180ms, and removes its class', async () => {
  const state = page(); let applied = false;
  document.startViewTransition = apply => {const ready = Promise.resolve().then(apply); return {ready, finished: ready, updateCallbackDone: ready, skipTransition() {}};};
  const origin = {getBoundingClientRect: () => ({left: 10, top: 20, width: 40, height: 30})};
  assert.equal(await transitionTheme(() => {applied = true;}, {origin}), 'iris');
  assert.ok(applied); assert.equal(state.calls[0].options.duration, 180);
  assert.equal(state.calls[0].options.pseudoElement, '::view-transition-new(root)');
  assert.equal(state.calls[0].frames.clipPath[0], 'circle(0px at 30px 35px)');
  assert.equal(state.classes.size, 0);
});

test('snapshot failure preserves the applied theme and cleans up', async () => {
  const state = page(); let applied = false;
  document.startViewTransition = apply => {apply(); return {ready: Promise.reject(new Error('snapshot unavailable')), finished: Promise.resolve(), updateCallbackDone: Promise.resolve(), skipTransition() {}};};
  assert.equal(await transitionTheme(() => {applied = true;}, {origin: [0, 0]}), 'instant');
  assert.ok(applied); assert.equal(state.classes.size, 0);
});

test('cancelling a transition clears the class even without a following theme change', async () => {
  const state = page(); let rejectReady, skipped = false;
  document.startViewTransition = apply => {apply(); return {ready: new Promise((_, reject) => {rejectReady = reject;}), finished: Promise.resolve(), updateCallbackDone: Promise.resolve(), skipTransition() {skipped = true; rejectReady(new Error('cancelled'));}};};
  const running = transitionTheme(() => {}, {origin: [20, 30]});
  assert.ok(state.classes.has('ov-vt'));
  cancelThemeTransition();
  assert.ok(skipped); assert.equal(state.classes.size, 0);
  assert.equal(await running, 'instant');
});
