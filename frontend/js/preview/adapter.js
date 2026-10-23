import {makeRow, candidatesFor, ROOT, historyFixture} from './fixtures.js';
import {stateOf} from '../model.js';

const copy = value => structuredClone(value);
const collator = new Intl.Collator('zh-CN', {numeric: true});
const reviewState = row => !row.subtitles.length ? '未匹配' : row.subtitles.some(sub => !sub.confirmed && (sub.manual || sub.score < .76)) ? '需确认' : row.subtitles.every(sub => sub.name === sub.targetName) ? '已符合' : '待整理';

// Same action/DTO boundary as the planned Python adapter; no filesystem bridge.
export class PreviewAdapter extends EventTarget {
  constructor() {super(); this.mode = 'preview'; this.rows = []; this.revision = 0; this.scanId = ''; this.scenario = 'matched'; this.plan = null; this.loading = false;}
  emit(type, payload) {this.dispatchEvent(new CustomEvent(type, {detail: payload}));}
  async load(scenario = 'matched') {
    if (this.loading) throw new Error('示例数据仍在准备中。');
    this.loading = true; this.scenario = scenario;
    this.rows = []; this.byId = new Map(); this.queryCache = null; this.plan = null;
    this.scanId = crypto.randomUUID(); this.revision++;
    const started = performance.now();
    try {
      this.emit('loading', {message: '正在准备示例数据…', done: 0, total: scenario === 'error' ? null : scenario === 'empty' ? 0 : scenario === 'large' ? 10000 : 12});
      await new Promise(resolve => setTimeout(resolve, 30));
      if (scenario === 'error') throw new Error('示例路径不可读取。实际接入时，这里会显示 Python 返回的错误原因。');
      const rows = [];
      const count = scenario === 'empty' ? 0 : scenario === 'large' ? 10000 : 12;
      for (let start = 0; start < count; start += 500) {
        for (let i = start + 1; i <= Math.min(count, start + 500); i++) {
          const row = makeRow(i);
          if (scenario === 'no-subs') {row.subtitles = []; row.state = '未匹配'; row.basis = ['示例目录中没有字幕文件']; row.warnings = [];}
          rows.push(row);
        }
        this.emit('loading', {message: `正在准备 ${count.toLocaleString()} 条示例…`, done: rows.length, total: count});
        if (count > 500) await new Promise(resolve => setTimeout(resolve, 0));
      }
      this.rows = rows; this.byId = new Map(rows.map(row => [row.rowId, row]));
      this.loadMs = performance.now() - started;
      return this.summary();
    } finally {this.loading = false;}
  }
  summary() {
    const counts = {all: this.rows.length};
    for (const row of this.rows) counts[stateOf(row)] = (counts[stateOf(row)] || 0) + 1;
    return {mode: this.mode, scanId: this.scanId, revision: this.revision, counts,
      subtitleCount: this.rows.reduce((sum, row) => sum + row.subtitles.length, 0), folderName: '山海之间 · 第一季', displayPath: ROOT};
  }
  row(params) {
    if (params.scanId !== this.scanId || params.revision !== this.revision) throw new Error('审阅版本已变化，请重新检查。');
    const row = this.byId.get(params.rowId);
    if (!row) throw new Error('该视频不属于当前示例。');
    return row;
  }
  changed() {this.revision++; this.plan = null; this.queryCache = null; return {revision: this.revision};}
  query(params) {
    const term = (params.search || '').trim().toLocaleLowerCase();
    const cacheKey = JSON.stringify([this.revision, term, params.status, params.fileType, params.sortKey, params.sortDir]);
    let rows = this.queryCache?.key === cacheKey ? this.queryCache.rows : null;
    if (!rows) {
    rows = this.rows.filter(row => (!params.status || params.status === 'all' || stateOf(row) === params.status)
      && (!params.fileType || row.video.extension === params.fileType)
      && (!term || [row.video.name, ...row.subtitles.flatMap(sub => [sub.name, sub.targetName])].join('\n').toLocaleLowerCase().includes(term)));
    const direction = params.sortDir === 'desc' ? -1 : 1;
    const key = params.sortKey || 'name';
    rows = [...rows].sort((a, b) => direction * (key === 'score' ? (b.subtitles[0]?.score || 0) - (a.subtitles[0]?.score || 0)
      : key === 'state' ? collator.compare(stateOf(a), stateOf(b)) : collator.compare(a.video.name, b.video.name)));
    this.queryCache = {key: cacheKey, rows};
    }
    const offset = Math.max(0, params.offset || 0), limit = Math.min(200, Math.max(1, params.limit || 100));
    return {rows: copy(rows.slice(offset, offset + limit)), total: rows.length, counts: this.summary().counts,
      revision: this.revision, ids: rows.map(row => row.rowId)};
  }
  async request(action, params = {}) {
    if (action === 'app.state') return this.summary();
    if (action === 'review.query') return this.query(params);
    if (action === 'history.list') return copy(historyFixture);
    if (action === 'history.get') return copy(historyFixture[0]);
    if (action === 'preview.create') {
      if (params.revision !== this.revision || params.scanId !== this.scanId) throw new Error('预览已过期。');
      const items = this.rows.flatMap(row => row.subtitles.map(sub => ({rowId: row.rowId, videoName: row.video.name,
        sourceName: sub.name, sourcePath: sub.displayPath, targetName: sub.targetName, targetPath: sub.targetPath,
        action: stateOf(row) === '已跳过' ? 'skipped' : stateOf(row) === '需确认' ? 'pending' : row.warnings.length ? 'blocked' : sub.name === sub.targetName ? 'unchanged' : 'rename'})));
      this.plan = {snapshotId: crypto.randomUUID(), revision: this.revision, items,
        pendingCount: this.rows.filter(row => row.state === '需确认').length,
        conflictCount: this.rows.filter(row => row.warnings.length && row.state !== '已跳过').length,
        unmatchedCount: this.rows.filter(row => row.state === '未匹配').length,
        changeCount: items.filter(item => item.action === 'rename').length};
      return copy(this.plan);
    }
    if (action === 'preview.discard') {this.plan = null; return {};}
    if (action.startsWith('organize.') || action.startsWith('file.')) throw new Error('界面预览不能访问或修改真实文件。');
    const row = this.row(params);
    if (action === 'review.details') return copy(row);
    if (action === 'review.candidates') return {rows: candidatesFor(row)};
    if (action === 'review.skip') {row.state = params.skipped ? '已跳过' : reviewState(row); return this.changed();}
    if (action === 'review.confirm') {
      if (!row.subtitles.length) throw new Error('请先选择字幕。');
      row.subtitles.forEach(sub => {sub.confirmed = true;}); row.state = reviewState(row); return this.changed();
    }
    if (action === 'review.remove') {
      row.subtitles = row.subtitles.filter(sub => sub.subtitleId !== params.subtitleId);
      row.state = reviewState(row); return this.changed();
    }
    if (action === 'review.assign') {
      const sub = candidatesFor(row).find(candidate => candidate.subtitleId === params.subtitleId);
      if (!sub) throw new Error('候选已失效。');
      if (this.rows.some(item => item.rowId !== row.rowId && item.subtitles.some(other => other.subtitleId === sub.subtitleId))) throw new Error('字幕已分配给其他视频。');
      if (row.subtitles.some(item => item.language === sub.language && item.subtitleId !== params.replaceId)) throw new Error('同语言已有关联，请选择替换。');
      if (params.replaceId && !row.subtitles.some(item => item.subtitleId === params.replaceId)) throw new Error('替换对象已失效。');
      row.subtitles = row.subtitles.filter(item => item.subtitleId !== params.replaceId);
      row.subtitles.push({...sub, manual: true, confirmed: false}); row.state = '需确认';
      row.basis = [sub.reason, `候选集数 · ${sub.episode}`, '人工指定保留原评分，需确认后继续'];
      return this.changed();
    }
    throw new Error('未提供该预览操作。');
  }
}
