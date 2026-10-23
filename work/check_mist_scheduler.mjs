import test from 'node:test';
import assert from 'node:assert/strict';
import {ListMist} from '../frontend/js/components/list-mist.js';

function harness(overrides={}) {
  let serial=0,draws=0;const queue=new Map();
  globalThis.document={hidden:false};
  globalThis.requestAnimationFrame=callback=>{queue.set(++serial,callback);return serial;};
  globalThis.cancelAnimationFrame=id=>queue.delete(id);
  const mist=Object.assign(Object.create(ListMist.prototype),{raf:0,last:0,nextFrame:0,clock:0,deadline:2000,
    destroyed:false,enabled:true,reduced:false,mode:'webgl2',viewport:{hidden:false},hover:0,hoverTarget:1,
    draw(){draws++;},...overrides});
  return {mist,queue,get draws(){return draws;},advance(time){const callbacks=[...queue.values()];queue.clear();callbacks.forEach(callback=>callback(time));}};
}

test('60/120/144/240Hz timestamps keep vapor GPU draws near 60 per second',()=>{
  for(const hz of [60,120,144,240]) {
    const h=harness();h.mist.tick(1000);
    for(let frame=1;frame<=hz;frame++)h.advance(1000+frame*1000/hz);
    assert.ok(h.draws>=58&&h.draws<=62,{hz,draws:h.draws});
  }
});

test('idle deadline drains the frame queue and later refresh ticks do no work',()=>{
  const h=harness();h.mist.tick(1000);
  for(let frame=1;frame<=90;frame++)h.advance(1000+frame*1000/60);
  assert.equal(h.queue.size,0);assert.equal(h.mist.last,0);
  const count=h.draws;h.advance(5000);assert.equal(h.draws,count);
});

test('hidden, disabled, reduced, destroyed and unavailable states stop immediately',()=>{
  for(const patch of [{enabled:false},{suspended:true},{reduced:true},{destroyed:true},{mode:'fallback'},{viewport:{hidden:true}}]) {
    const h=harness(patch);h.mist.tick(1000);assert.equal(h.draws,0);assert.equal(h.queue.size,0);
  }
  const h=harness();document.hidden=true;h.mist.tick(1000);assert.equal(h.draws,0);assert.equal(h.queue.size,0);
});

test('a delayed browser frame advances vapor time by at most 60ms',()=>{
  const h=harness({deadline:10000});h.mist.tick(1000);h.advance(2016);
  assert.ok(Math.abs(h.mist.clock-.06)<1e-8);
});
