import {el, iconNode, badge, language, button} from './icons.js';
import {stateOf} from '../model.js';

const actionViews = new WeakMap();
// Keep real buttons stable so Lens bodies/focus survive selection and review.
function renderActions(host, row, handlers) {
  let view = actionViews.get(host);
  if (!view) {
    view = {row, handlers};
    const actions = el('div', 'detail-actions');
    view.main = button('', 'secondary', () => view.row?.state === '需确认' ? view.handlers.mutate('review.confirm') : view.handlers.candidates());
    view.skip = button('', 'secondary', () => view.handlers.mutate('review.skip', {skipped: view.row?.state !== '已跳过'}));
    actions.append(view.main, view.skip); host.replaceChildren(actions); actionViews.set(host, view);
  }
  view.row = row; view.handlers = handlers; host.hidden = !row;
  for (const control of [view.main, view.skip]) control.disabled = !row;
  if (!row) return;
  const pending = row.state === '需确认', skipped = row.state === '已跳过';
  view.main.classList.toggle('primary', pending); view.main.classList.toggle('secondary', !pending);
  for (const [control, label, symbol] of [[view.main, pending ? '确认匹配' : '更换字幕', pending ? 'check' : 'compare'], [view.skip, skipped ? '恢复审阅' : '跳过', skipped ? 'refresh' : 'minus']]) {
    if (control.dataset.actionLabel !== label) {
      control.dataset.actionLabel = label; control.replaceChildren(iconNode(symbol), document.createTextNode(label));
    }
  }
}

export function renderInspector(host, row, {mutate, candidates, copy, reveal, actionsHost}) {
  host.replaceChildren();
  renderActions(actionsHost, row, {mutate, candidates});
  if (!row) {host.append(el('p', 'subtle-text', '选择一个视频，查看字幕和目标名称。')); return;}
  const header = el('section'); header.append(el('span', 'detail-label', `视频 · ${row.video.extension.slice(1).toUpperCase()}`), el('h3', 'detail-video', row.video.name));
  const state = el('div', 'detail-status'); state.append(badge(stateOf(row)), el('span', '', row.episode)); header.append(state); host.append(header);
  if (row.warnings.length) {const warning = el('div', 'notice warning'); warning.style.marginTop = '17px'; warning.append(iconNode('alert'), document.createTextNode(row.warnings[0].message)); host.append(warning);}
  const subtitles = el('section', 'detail-section'); const heading = el('div', 'detail-section-title');
  heading.append(el('h3', '', `关联字幕${row.subtitles.length ? ` · ${row.subtitles.length}` : ''}`), button('选择字幕', '', candidates, 'compare')); subtitles.append(heading);
  if (!row.subtitles.length) subtitles.append(el('p', 'subtle-text', '还没有找到合适的字幕。你可以从候选中人工选择。'));
  for (const sub of row.subtitles) {
    const item = el('article', 'subtitle-detail'); const title = el('header');
    title.append(language(sub.language), el('span', '', sub.manual ? '人工指定' : '自动匹配'));
    const remove = button('', 'icon-button small', () => mutate('review.remove', {subtitleId: sub.subtitleId}), 'x');
    remove.setAttribute('aria-label', `移除${sub.language}字幕关联`); remove.title = '仅移除本次关联，不删除文件'; title.append(remove);
    item.append(title, el('p', '', sub.name));
    const target = el('div', 'target-block'); const label = el('span'); label.append(iconNode('arrow'), document.createTextNode('整理后'));
    target.append(label, el('p', '', sub.targetName)); item.append(target); subtitles.append(item);
  }
  host.append(subtitles);
  const basis = el('section', 'detail-section'); basis.append(el('div', 'detail-section-title')); basis.firstChild.append(el('h3', '', '匹配依据'));
  const list = el('ul', 'basis-list');
  for (const text of row.basis) {const li = el('li'); li.append(iconNode(row.state === '需确认' ? 'alert' : 'check'), document.createTextNode(text)); list.append(li);}
  if (row.subtitles.some(sub => sub.manual)) {const li = el('li'); li.append(iconNode('compare'), document.createTextNode('人工指定保留原评分，确认后才纳入整理计划')); list.append(li);}
  basis.append(list); host.append(basis);
  const details = el('details', 'path-details'); details.append(el('summary', '', '完整路径与名称'));
  details.append(el('p', '', row.video.displayPath));
  const copyName = button('复制视频名称', 'subtle-button', () => copy(row.video.name,row.video.fileId), 'copy'); details.append(copyName);
  if (reveal) details.append(button('打开文件位置','subtle-button',() => reveal(row.video.fileId),'folder'));
  for (const sub of row.subtitles) {details.append(el('p', '', `原位置：${sub.displayPath}`), el('p', '', `目标位置：${sub.targetPath}`));}
  host.append(details);
}
