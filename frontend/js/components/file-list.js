import {el, iconNode, badge, language} from './icons.js';
import {stateOf} from '../model.js';

export const ROW_HEIGHT = 84;
export class VirtualFileList {
  constructor(store, viewport, spacer, items) {
    Object.assign(this, {store, viewport, spacer, items}); this.generation = 0; this.range = ''; this.raf = 0; this.renderMs = 0;
    this.nodes = new Map();this.cache = null;this.pending = null;
    viewport.addEventListener('scroll', () => {
      if (!this.raf) this.raf = requestAnimationFrame(() => {this.raf = 0; this.draw();});
    });
    items.addEventListener('click', event => {const row = event.target.closest('[data-row-id]'); if (row) {viewport.focus({preventScroll: true}); store.select(row.dataset.rowId);}});
    this.resize = new ResizeObserver(() => this.draw(true)); this.resize.observe(viewport);
  }
  update(reset = false) {
    this.spacer.style.height = `${this.store.view.total * ROW_HEIGHT}px`;
    this.viewport.setAttribute('aria-rowcount', this.store.view.total);
    if (reset) this.viewport.scrollTop = 0;
    return this.draw(true);
  }
  async draw(force = false) {
    if (this.store.busy) return;
    if (this.store.error || !this.store.view.total) {
      this.generation++;this.range = '';this.cache = this.pending = null;this.nodes.clear();
      this.items.replaceChildren();this.viewport.removeAttribute('aria-activedescendant');return;
    }
    const started = performance.now();
    const start = Math.min(this.store.view.total - 1, Math.max(0, Math.floor(this.viewport.scrollTop / ROW_HEIGHT) - 6));
    const count = Math.min(60, this.store.view.total - start, Math.ceil(this.viewport.clientHeight / ROW_HEIGHT) + 13);
    const key = JSON.stringify([this.store.summary.scanId,this.store.summary.revision,this.store.filters]);
    const range = `${key}:${start}:${count}:${this.store.selectedId}:${this.store.view.total}`;
    if (!force && range === this.range) return;
    this.range = range;
    const generation = ++this.generation;
    let rows;
    try {
      const covers = entry => entry?.key === key && entry.start <= start && entry.end >= start + count;
      let cached = this.cache;
      if (!covers(cached)) {
        if (!covers(this.pending)) {
          const limit = Math.min(60, this.store.view.total - start);
          this.pending = {key,start,end:start+limit,promise:this.store.rows(start,limit)};
        }
        const pending = this.pending;
        try {cached = {key,start:pending.start,rows:await pending.promise};}
        finally {if (this.pending === pending) this.pending = null;}
        cached.end = cached.start + cached.rows.length;
      }
      if (generation !== this.generation) return;
      this.cache = cached;
      rows = cached.rows.slice(start-cached.start,start-cached.start+count);
    }
    catch (error) {
      if (generation === this.generation) {this.range = '';if (!this.store.busy) this.store.dispatchEvent(new CustomEvent('error',{detail:error.message}));}
      return;
    }
    if (this.store.busy) {this.range = '';return;}
    const visible = new Map();
    rows.forEach((row, index) => {
      const signature = JSON.stringify(row);
      const previous = this.nodes.get(row.rowId);
      const item = previous?.signature === signature ? previous.item : this.createRow(row);
      const set = (name,value) => {if (item.getAttribute(name) !== String(value)) item.setAttribute(name,value);};
      set('aria-rowindex',start + index + 1);set('aria-selected',row.rowId === this.store.selectedId);
      visible.set(row.rowId,{item,signature});
    });
    for (const child of [...this.items.children]) if (visible.get(child.dataset.rowId)?.item !== child) child.remove();
    let cursor = this.items.firstElementChild;
    for (const {item} of visible.values()) {
      if (item !== cursor) this.items.insertBefore(item,cursor);
      cursor = item.nextElementSibling;
    }
    this.nodes = visible;
    this.items.style.transform = `translateY(${start * ROW_HEIGHT}px)`;
    this.items.dataset.revision = String(this.store.summary.revision);
    if (visible.has(this.store.selectedId)) this.viewport.setAttribute('aria-activedescendant', `row-${this.store.selectedId}`);
    else this.viewport.removeAttribute('aria-activedescendant');
    this.renderMs = performance.now() - started;
  }
  createRow(row) {
      const item = el('div', 'file-row'); item.dataset.rowId = row.rowId; item.id = `row-${row.rowId}`;
      item.setAttribute('role', 'row');
      const copy = el('div', 'file-copy'); copy.setAttribute('role', 'gridcell');
      const names = el('div', 'file-names'); const title = el('div', 'file-name'); title.title = row.video.name;
      const dot = row.video.name.lastIndexOf('.'); title.append(el('span', 'file-stem', row.video.name.slice(0, dot)), el('span', 'file-extension', row.video.name.slice(dot)));
      const subtitle = el('div', 'file-subtitle');
      if (row.embeddedSatisfied) {
        const accepted = row.embedded.tracks.filter(track => row.embedded.acceptedTrackIds.includes(track.trackId));
        accepted.slice(0,2).forEach(track => subtitle.append(language(track.language)));
        subtitle.append(el('span','subtitle-summary','视频内字幕 · 已满足语言要求'));
      } else if (row.subtitles.length) {
        row.subtitles.forEach(sub => subtitle.append(language(sub.language)));
        subtitle.append(el('span', 'subtitle-summary', row.subtitles.length > 1 ? `${row.subtitles.length} 份字幕 · 多语言匹配` : row.subtitles[0].name));
      } else subtitle.append(el('span', 'subtitle-summary', '尚未关联字幕'));
      names.append(title, subtitle); copy.append(iconNode('video', 'file-icon'), names);
      const score = el('div', 'match-score'); score.setAttribute('role', 'gridcell');
      if (row.embeddedSatisfied) {score.textContent = '语言符合';score.title = '已有内嵌字幕，无需文件名匹配或外挂整理';}
      else if (row.subtitles.length) {const value = Math.round(row.subtitles[0].score * 100); score.textContent = `${value}%`; const meter = el('div', 'score-meter'); const bar = el('i'); bar.style.width = `${value}%`; meter.append(bar); score.append(meter);} else score.textContent = '—';
      const status = el('div'); status.setAttribute('role', 'gridcell'); status.append(badge(stateOf(row)));
      item.append(copy, score, status, iconNode('arrow', 'row-arrow'));
      return item;
  }
  ensureVisible(index) {
    const top = index * ROW_HEIGHT, bottom = top + ROW_HEIGHT;
    if (top < this.viewport.scrollTop) this.viewport.scrollTop = top;
    else if (bottom > this.viewport.scrollTop + this.viewport.clientHeight) this.viewport.scrollTop = bottom - this.viewport.clientHeight;
    this.draw(true);
  }
}
