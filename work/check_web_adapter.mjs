// Stage 6 fixture adapter checks. Run with Node 22+ (ES module syntax detection).
import test from 'node:test';
import assert from 'node:assert/strict';
import {PreviewAdapter} from '../frontend/js/preview/adapter.js';
import {WorkspaceStore} from '../frontend/js/store.js';

const params = (adapter, rowId, extra = {}) => ({scanId: adapter.scanId, revision: adapter.revision, rowId, ...extra});
const setup = async () => {const adapter = new PreviewAdapter(); await adapter.load(); return adapter;};

test('fixture paths and DTO clones remain consistent', async () => {
  const adapter = await setup();
  const {rows} = await adapter.request('review.query', {limit: 200});
  assert.equal(rows.length, 12);
  assert.equal(rows[0].rowId, 'video-1');
  for (const row of rows) {
    assert.ok(row.video.displayPath.endsWith(row.video.name));
    for (const sub of row.subtitles) {
      assert.ok(sub.displayPath.endsWith(sub.name));
      assert.ok(sub.targetPath.endsWith(sub.targetName));
    }
    const candidates = await adapter.request('review.candidates', params(adapter, row.rowId));
    for (const sub of candidates.rows) assert.ok(sub.displayPath.endsWith(sub.name));
  }
  rows[0].video.name = 'changed outside adapter';
  assert.notEqual((await adapter.request('review.details', params(adapter, 'video-1'))).video.name, rows[0].video.name);
});

test('manual assignment keeps confidence and requires explicit confirmation', async () => {
  const adapter = await setup(), rowId = 'video-3';
  const original = params(adapter, rowId);
  await adapter.request('review.assign', {...original, subtitleId: 'candidate-3-A', replaceId: 'sub-3-chs'});
  await assert.rejects(adapter.request('review.confirm', original), /版本已变化/);
  let row = await adapter.request('review.details', params(adapter, rowId));
  assert.equal(row.state, '需确认');
  assert.equal(row.subtitles[0].score, .82);
  assert.equal(row.subtitles[0].manual, true);
  assert.equal(row.subtitles[0].confirmed, false);
  const preview = await adapter.request('preview.create', params(adapter));
  assert.ok(preview.items.some(item => item.rowId === rowId && item.action === 'pending'));
  await adapter.request('review.confirm', params(adapter, rowId));
  assert.equal(adapter.plan, null);
  row = await adapter.request('review.details', params(adapter, rowId));
  assert.equal(row.state, '待整理');
  assert.equal(row.subtitles[0].score, .82);
});

test('duplicate language assignment and empty confirmation are rejected', async () => {
  const adapter = await setup();
  await assert.rejects(adapter.request('review.assign', params(adapter, 'video-2', {subtitleId: 'candidate-2-A'})), /同语言/);
  await assert.rejects(adapter.request('review.confirm', params(adapter, 'video-4')), /先选择字幕/);
  const before = adapter.revision;
  await assert.rejects(adapter.request('review.assign', params(adapter, 'video-2', {subtitleId: 'missing'})), /候选已失效/);
  assert.equal(adapter.revision, before);
});

test('skip and restore preserve unchanged and pending states', async () => {
  const adapter = await setup();
  for (const [rowId, state] of [['video-6', '已符合'], ['video-3', '需确认']]) {
    await adapter.request('review.skip', params(adapter, rowId, {skipped: true}));
    assert.equal((await adapter.request('review.details', params(adapter, rowId))).state, '已跳过');
    await adapter.request('review.skip', params(adapter, rowId, {skipped: false}));
    assert.equal((await adapter.request('review.details', params(adapter, rowId))).state, state);
  }
});

test('preview copies are isolated; mutations and failed reload invalidate authority', async () => {
  const adapter = await setup();
  const preview = await adapter.request('preview.create', params(adapter));
  assert.equal(preview.conflictCount, 1);
  assert.equal(preview.unmatchedCount, 2);
  assert.ok(preview.items.some(item => item.action === 'blocked'));
  assert.ok(preview.items.some(item => item.action === 'unchanged'));
  preview.items.length = 0;
  assert.ok(adapter.plan.items.length > 0);
  const old = params(adapter, 'video-1');
  await assert.rejects(adapter.load('error'), /不可读取/);
  assert.equal(adapter.plan, null);
  assert.equal(adapter.rows.length, 0);
  await assert.rejects(adapter.request('review.skip', {...old, skipped: true}), /版本已变化/);
});

test('no preview action grants filesystem or execution access', async () => {
  const adapter = await setup();
  for (const action of ['organize.confirm', 'organize.execute', 'file.openLocation', 'file.rename']) {
    await assert.rejects(adapter.request(action, params(adapter, 'video-1')), /不能访问或修改真实文件/);
  }
});

test('large fixture query supports source/target search, sorting and bounded slices', async () => {
  const adapter = new PreviewAdapter();
  let events = 0;
  adapter.addEventListener('loading', () => {events++;});
  await adapter.load('large');
  assert.equal(adapter.rows.length, 10000);
  assert.ok(events >= 20);
  let view = await adapter.request('review.query', {limit: 10000});
  assert.equal(view.rows.length, 200);
  assert.equal(view.total, 10000);
  assert.equal(new Set(view.ids).size, 10000);
  view = await adapter.request('review.query', {search: 'S01E9999'});
  assert.equal(view.total, 1);
  assert.equal(view.rows[0].rowId, 'video-9999');
  assert.equal((await adapter.request('review.query', {fileType: '.mp4'})).total, 3333);
  assert.equal((await adapter.request('review.query', {status: '存在冲突'})).total, 1);
  const descending = await adapter.request('review.query', {sortKey: 'name', sortDir: 'desc', limit: 1});
  assert.equal(descending.rows[0].rowId, 'video-10000');
});

test('store preserves stable selection through sort, handles empty and failed loads', async () => {
  const adapter = new PreviewAdapter(), store = new WorkspaceStore(adapter);
  await store.load('matched');
  await store.select('video-8');
  await store.filter({sortKey: 'score'});
  assert.equal(store.selectedId, 'video-8');
  await store.filter({search: 'no-such-name'});
  assert.equal(store.selectedId, null);
  assert.equal(store.details, null);
  await store.load('no-subs');
  assert.equal(store.summary.subtitleCount, 0);
  await store.load('empty');
  assert.equal(store.view.total, 0);
  await store.load('error');
  assert.match(store.error, /不可读取/);
  assert.equal(store.details, null);
  assert.equal(store.loading, false);
});
