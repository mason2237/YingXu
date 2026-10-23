// Pure original Lens functions. No DOM, Web Audio context or build scripts.
import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveMaterial, tokens} from '../frontend/vendor/design-systems/lens/tokens.js';
import {Spring, jellyMatrix} from '../frontend/vendor/design-systems/lens/internal/jelly-physics.js';
import {opticRange, opticXY, opticPoint, opticDropTarget} from '../frontend/vendor/design-systems/lens/internal/optics.js';
import {ContextBudget} from '../frontend/vendor/design-systems/lens/internal/context-budget.js';
import {soundCues, synthesizeCue, synthesizeFriction} from '../frontend/vendor/design-systems/lens/sound.js';

test('original material presets are immutable and range checked', () => {
  assert.ok(Object.isFrozen(tokens.materials.thick));
  assert.deepEqual(resolveMaterial('thick'), {refraction: .9, blur: .24, dispersion: .65});
  assert.deepEqual(resolveMaterial({refraction: 9, blur: -4}), {refraction: 1, blur: 0, dispersion: .65});
  assert.throws(() => resolveMaterial({refraction: NaN}), TypeError);
  assert.throws(() => resolveMaterial('unknown'), TypeError);
});
test('spring settles, accepts interrupted targets, and caps a long timestep', () => {
  const spring = new Spring(); spring.target = 100;
  for (let i = 0; i < 25; i++) spring.step(1 / 60);
  spring.target = 20;
  for (let i = 0; i < 180; i++) spring.step(1 / 60);
  assert.equal(spring.value, 20); assert.equal(spring.moving, false);
  spring.target = 900; assert.ok(Number.isFinite(spring.step(500)));
});
test('jelly deformation preserves area without lift', () => {
  const [a, b, c, d] = jellyMatrix(.3, .7);
  assert.ok(Math.abs(a * d - b * c - 1) < 1e-8);
});
test('optical controls clamp, snap and map pointer coordinates', () => {
  assert.equal(opticRange(27, 0, 100, 5), 25);
  assert.deepEqual(opticXY({x: -500, y: 500}, -100, 100, 1), {x: -100, y: 100});
  assert.deepEqual(opticPoint(50, 50, {left: 0, top: 0, width: 100, height: 100}, 10), {x: .5, y: .5});
  assert.throws(() => opticRange(0, 1, 1, 0), TypeError);
});
test('well attraction ignores disabled targets', () => {
  assert.equal(opticDropTarget({x: 0, y: 0}, [{value: 'blocked', x: 0, y: 0, disabled: true}, {value: 'a', x: 10, y: 1}, {value: 'b', x: 30, y: 0}]), 'a');
});
test('GPU budget releases departing leases before activating incoming ones', () => {
  const events = [], budget = new ContextBudget(1);
  let rankA = 2;
  const a = budget.add({priority: () => rankA, activate: () => events.push('a+'), suspend: () => events.push('a-')});
  const b = budget.add({priority: () => 1, activate: () => events.push('b+'), suspend: () => events.push('b-')});
  budget.update(); rankA = 0; budget.update();
  assert.deepEqual(events, ['a+', 'a-', 'b+']);
  a.destroy(); b.destroy(); assert.equal(budget.clients.size, 0);
});
test('13 original cues and friction synthesize finite bounded PCM without playback', () => {
  assert.equal(Object.keys(soundCues).length, 13);
  for (const name of Object.keys(soundCues)) {
    const pcm = synthesizeCue(name, 8000);
    assert.ok(pcm.length > 0 && pcm.length <= 8000);
    assert.ok(pcm.some(sample => sample !== 0));
    assert.ok(pcm.every(sample => Number.isFinite(sample) && Math.abs(sample) <= .801));
  }
  const friction = synthesizeFriction(8000);
  assert.equal(friction.length, 16000);
  assert.ok(friction.every(Number.isFinite));
  assert.throws(() => synthesizeCue({duration: 8, tones: []}), TypeError);
});
