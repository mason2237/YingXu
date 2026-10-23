import {el, iconNode, badge, language} from './icons.js';
import {stateOf} from '../model.js';

export const ROW_HEIGHT = 84;
export class VirtualFileList {
  constructor(store, viewport, spacer, items) {
    Object.assign(this, {store, viewport, spacer, items}); this.generation = 0; this.range = ''; this.raf = 0; this.renderMs = 0;
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
    this.draw(true);
  }
  async draw(force = false) {
    if (this.store.busy) return;
    if (this.store.error || !this.store.view.total) {this.generation++; this.items.replaceChildren(); this.viewport.removeAttribute('aria-activedescendant'); return;}
    const started = performance.now();
    const start = Math.max(0, Math.floor(this.viewport.scrollTop / ROW_HEIGHT) - 3);
    const count = Math.min(60, Math.ceil(this.viewport.clientHeight / ROW_HEIGHT) + 7);
    const range = `${start}:${count}:${this.store.summary.revision}:${this.store.selectedId}:${this.store.view.total}`;
    if (!force && range === this.range) return;
    this.range = range;
    const generation = ++this.generation;
    let rows;
    try {rows = await this.store.rows(start,count);}
    catch (error) {this.range = '';if (generation === this.generation && !this.store.busy) this.store.dispatchEvent(new CustomEvent('error',{detail:error.message}));return;}
    if (generation !== this.generation || this.store.busy) {this.range = '';return;}
    const fragment = document.createDocumentFragment();
    rows.forEach((row, index) => {
      const item = el('div', 'file-row'); item.dataset.rowId = row.rowId; item.id = `row-${row.rowId}`;
      item.setAttribute('role', 'row'); item.setAttribute('aria-rowindex', start + index + 1); item.setAttribute('aria-selected', row.rowId === this.store.selectedId);
      const copy = el('div', 'file-copy'); copy.setAttribute('role', 'gridcell');
      const names = el('div', 'file-names'); const title = el('div', 'file-name'); title.title = row.video.name;
      const dot = row.video.name.lastIndexOf('.'); title.append(el('span', 'file-stem', row.video.name.slice(0, dot)), el('span', 'file-extension', row.video.name.slice(dot)));
      const subtitle = el('div', 'file-subtitle');
      if (row.subtitles.length) {
        row.subtitles.forEach(sub => subtitle.append(language(sub.language)));
        subtitle.append(el('span', 'subtitle-summary', row.subtitles.length > 1 ? `${row.subtitles.length} 份字幕 · 多语言匹配` : row.subtitles[0].name));
      } else subtitle.append(el('span', 'subtitle-summary', '尚未关联字幕'));
      names.append(title, subtitle); copy.append(iconNode('video', 'file-icon'), names);
      const score = el('div', 'match-score'); score.setAttribute('role', 'gridcell');
      if (row.subtitles.length) {const value = Math.round(row.subtitles[0].score * 100); score.textContent = `${value}%`; const meter = el('div', 'score-meter'); const bar = el('i'); bar.style.width = `${value}%`; meter.append(bar); score.append(meter);} else score.textContent = '—';
      const status = el('div'); status.setAttribute('role', 'gridcell'); status.append(badge(stateOf(row)));
      item.append(copy, score, status, iconNode('arrow', 'row-arrow')); fragment.append(item);
    });
    this.items.style.transform = `translateY(${start * ROW_HEIGHT}px)`;
    this.items.replaceChildren(fragment);
    if (document.getElementById(`row-${this.store.selectedId}`)) this.viewport.setAttribute('aria-activedescendant', `row-${this.store.selectedId}`);
    else this.viewport.removeAttribute('aria-activedescendant');
    this.renderMs = performance.now() - started;
  }
  ensureVisible(index) {
    const top = index * ROW_HEIGHT, bottom = top + ROW_HEIGHT;
    if (top < this.viewport.scrollTop) this.viewport.scrollTop = top;
    else if (bottom > this.viewport.scrollTop + this.viewport.clientHeight) this.viewport.scrollTop = bottom - this.viewport.clientHeight;
    this.draw(true);
  }
}
