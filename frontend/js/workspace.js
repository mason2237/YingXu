import {WorkspaceStore} from './store.js';
import {VirtualFileList, ROW_HEIGHT} from './components/file-list.js';
import {renderInspector} from './components/inspector.js';
import {WorkspaceDialogs} from './components/dialogs.js';
import {Effects} from './components/upstream-effects.js';
import {icons, el} from './components/icons.js';
import {bindKeyboardFocus} from '../vendor/design-systems/lens/focus.js';
import {appearance, bindThemeControls} from './appearance.js';
import {WorkspaceFeedback, InspectorDrawer} from './components/workspace-feedback.js';
import {prepareLocalWorkspace, LocalWorkspace} from './components/local-workspace.js';

const $ = id => document.getElementById(id);
const isLocal = globalThis.__yingxuWorkspaceMode === 'local';
const Adapter = isLocal ? (await import('./local-adapter.js')).LocalAdapter : (await import('./preview/adapter.js')).PreviewAdapter;
const Dialogs = isLocal ? (await import('./components/local-dialogs.js')).LocalWorkspaceDialogs : WorkspaceDialogs;
if (isLocal) prepareLocalWorkspace();
icons(); bindKeyboardFocus(); bindThemeControls();
const adapter = new Adapter(), store = new WorkspaceStore(adapter);
const effects = new Effects($('glass-toolbar'), $('particles'));
const feedback = new WorkspaceFeedback(effects), drawer = new InspectorDrawer(effects);
const list = new VirtualFileList(store, $('file-list'), $('list-spacer'), $('list-items'));
let searchTimer, composing = false, lastScenario = isLocal ? 'scan' : 'matched',localWorkspace = null;
function toast(message, options) {feedback.toast(message, options);}
appearance.addEventListener('error', event => toast(event.detail,{tone:'error'}));
async function copyName(text,fileId) {
  if (isLocal) {try {await adapter.request('file.copyName',{fileId});toast('视频名称已复制',{tone:'success'});} catch (error) {toast(error.message,{tone:'error'});}return;}
  const focused = document.activeElement;
  const field = document.createElement('textarea'); field.value = text; field.className = 'sr-only'; document.body.append(field); field.select();
  try {if (!document.execCommand('copy')) throw new Error('copy denied'); toast('视频名称已复制',{tone:'success'});}
  catch {toast('复制不可用，可在完整名称中选中文字并按 Ctrl+C',{tone:'error'});}
  finally {field.remove(); if (focused?.isConnected) focused.focus();}
}
async function mutate(action, params = {}) {
  try {await store.mutate(action, params); toast(action === 'review.confirm' ? isLocal ? '已确认匹配，文件尚未修改' : '已确认此匹配 · 仅更新示例计划' : action === 'review.assign' ? '已更换字幕，请核对后确认' : action === 'review.remove' ? '已移除关联，保留原文件' : params.skipped ? '已跳过此视频' : '已恢复审阅',{tone:'success'});}
  catch (error) {toast(error.message,{tone:'error'}); throw error;}
}
const dialogs = new Dialogs(store, effects, {load: scenario => load(scenario), toast, mutate, feedback});
dialogs.commandActions = () => [
  {label:'搜索文件',symbol:'search',shortcut:'Ctrl F',keywords:'查找 视频 名称',run:() => $('search-input').focus(),disabled:store.busy},
  {label:'显示全部匹配',symbol:'video',keywords:'筛选 全部',run:() => filter({search:'',status:'all',fileType:''}),disabled:store.busy},
  {label:'只看待确认',symbol:'alert',keywords:'筛选 人工 匹配 字幕',run:() => filter({status:'需确认'}),disabled:store.busy},
  {label:'只看未匹配',symbol:'video',keywords:'筛选 缺少 字幕',run:() => filter({status:'未匹配'}),disabled:store.busy},
  {label:'只看目标冲突',symbol:'alert',keywords:'筛选 重名 异常',run:() => filter({status:'存在冲突'}),disabled:store.busy},
  {label:'选择候选字幕',symbol:'compare',keywords:'人工 调整 更换',run:() => dialogs.candidates(),disabled:store.busy || !store.details},
  {label:store.details?.state === '已跳过' ? '恢复当前视频' : '跳过当前视频',symbol:'minus',keywords:'忽略 审阅',run:() => mutate('review.skip',{skipped:store.details.state !== '已跳过'}),disabled:store.busy || !store.details},
  {label:'预览变更',symbol:'preview',shortcut:'Ctrl Enter',keywords:'整理 名称 目标',run:() => dialogs.preview(),disabled:$('preview-button').disabled},
  {label:'操作记录',symbol:'history',keywords:'结果 成功 跳过 异常',run:() => dialogs.history(),disabled:store.busy},
  {label:'外观与动效',symbol:'settings',keywords:'主题 明暗 玻璃 烟雾 粒子',run:() => dialogs.open('appearance')},
  {label:isLocal ? '选择文件夹' : '切换示例',symbol:'folder',keywords:'目录 场景',run:() => isLocal ? load('choose') : dialogs.open('dataset'),disabled:store.busy},
  {label:isLocal ? '重新扫描文件' : '重新加载示例',symbol:'refresh',keywords:'刷新 扫描',run:() => load(),disabled:store.busy || (isLocal && !store.summary.folderId)},
  ...(isLocal ? [{label:'扫描选项',symbol:'settings',keywords:'子文件夹 移动 字幕',run:() => dialogs.open('scan-options'),disabled:store.busy}] : []),
];
function renderDetails() {
  renderInspector($('inspector-content'), store.details, {mutate: (action, params) => mutate(action, params).catch(() => {}), candidates: () => dialogs.candidates().catch(error => toast(error.message,{tone:'error'})), copy: copyName,reveal:isLocal ? fileId => adapter.request('file.reveal',{fileId}).catch(error => toast(error.message,{tone:'error'})) : null, actionsHost: $('inspector-actions')});
  if (store.busy) for (const control of document.querySelectorAll('#inspector button')) control.disabled = true;
}
function updateSummary() {
  const {counts = {}, subtitleCount = 0} = store.summary;
  $('overview').replaceChildren();
  for (const [value, label, attention] of [[counts.all || 0,'个视频'], [subtitleCount,isLocal ? '份关联字幕' : '份字幕'], [counts['需确认'] || 0,'项待确认', true]]) {const part = el('span', attention ? 'attention' : ''); part.append(el('strong', '', value.toLocaleString()), document.createTextNode(label)); $('overview').append(part);}
  for (const [id, state] of [['count-all','all'], ['count-ready','待整理'], ['count-review','需确认'], ['count-unmatched','未匹配']]) $(id).textContent = counts[state] || 0;
  const folder = isLocal ? adapter.state?.summary || store.summary : store.summary;
  $('folder-path').textContent = folder.displayPath || (isLocal ? '可拖入一个本地文件夹' : '示例文件夹');
  $('folder-path').title = folder.displayPath || '';
  $('folder-name').textContent = isLocal ? folder.folderName || '选择包含视频与字幕的文件夹' : adapter.scenario === 'large' ? '大列表示例 · 10,000 条' : adapter.scenario === 'empty' ? '空文件夹示例' : adapter.scenario === 'no-subs' ? '没有字幕的示例' : '山海之间 · 第一季';
  $('preview-count').textContent = subtitleCount;
  $('preview-button').disabled = store.busy || Boolean(store.error) || !subtitleCount;
  $('scan-button').disabled = store.busy || (isLocal && !folder.folderId); $('dataset-button').disabled = store.busy;
  for (const control of document.querySelectorAll('.collection-tools input,.collection-tools button,.collection-tools select,.list-heading button,.list-heading select')) control.disabled = store.busy;
  $('inspector').inert = store.busy;
  $('file-list').setAttribute('aria-busy',String(store.busy));
  for (const control of document.querySelectorAll('#inspector button')) control.disabled = store.busy;
  $('list-count').textContent = `${store.view.total.toLocaleString()} / ${(counts.all || 0).toLocaleString()} 个视频`;
  $('footer-status').textContent = store.error ? '读取失败，请检查目录后重新扫描' : store.loading ? isLocal ? '正在处理本地任务…' : '正在准备示例…' : isLocal && !folder.folderId ? '选择文件夹，开始扫描' : isLocal && folder.needsScan ? folder.finished ? '本批整理已结束，重新扫描可核对文件' : '选项已更新，请重新扫描' : `${counts['需确认'] || 0} 项待确认 · ${counts['存在冲突'] || 0} 项冲突`;
  $('search-input').value = store.filters.search;
  $('file-type').value = store.filters.fileType;
  document.querySelectorAll('[data-filter]').forEach(button => {const chosen = button.dataset.filter === store.filters.status; button.classList.toggle('selected', chosen); button.setAttribute('aria-pressed', chosen);});
  effects.syncFilter(store.filters.status);
  $('extra-filter').value = ['存在冲突','已跳过','已符合'].includes(store.filters.status) ? store.filters.status : '';
  if (isLocal) {
    const notice = $('scan-warnings'),warnings = folder.scanWarnings || [],signature = JSON.stringify([folder.scanWarningCount,warnings]);
    notice.hidden = !folder.scanWarningCount;
    if (notice.dataset.signature !== signature) {
      notice.dataset.signature = signature;notice.firstChild.textContent = `扫描提示 · ${folder.scanWarningCount || 0} 项路径未读取`;
      const items = $('scan-warning-items');items.replaceChildren();for (const message of warnings) items.append(el('li','',message));
      if (folder.scanWarningCount > warnings.length) items.append(el('li','',`另有 ${folder.scanWarningCount-warnings.length} 项；请核对目录权限和文件来源后重扫。`));
    }
  }
  localWorkspace?.sync();dialogs.syncExecution?.();
}
function emptyState() {
  const empty = store.error || !store.view.total;
  $('empty-state').hidden = !empty; $('file-list').hidden = Boolean(empty);
  if (!empty) return;
  const filtered = store.summary.counts.all && !store.error;
  $('empty-title').textContent = store.error ? '暂时无法读取这个目录' : filtered ? '没有符合条件的文件' : '这个文件夹还没有视频';
  $('empty-message').textContent = store.error || (filtered ? '试试其他名称，或清除筛选条件。' : '选择包含视频与字幕的文件夹后，匹配关系会显示在这里。');
  $('empty-action').textContent = store.error ? '重新加载示例' : filtered ? '清除搜索与筛选' : '载入匹配示例';
  if (isLocal && !filtered) {
    const summary = adapter.state?.summary || store.summary;
    $('empty-title').textContent = store.error ? '暂时无法读取这个目录' : summary.finished ? '本批整理已结束' : summary.needsScan ? '扫描文件，建立匹配关系' : summary.folderId ? '这个目录还没有视频' : '从一个文件夹开始';
    $('empty-message').textContent = store.error || (summary.finished ? '实际结果已保存在操作记录中。重新扫描可核对当前文件。' : summary.needsScan ? '扫描只读取文件；核对预览并确认后才会整理字幕。' : '选择或拖入包含视频与字幕的目录。所有文件均在本机处理。');
    $('empty-action').textContent = summary.folderId ? '重新扫描' : '选择文件夹';
  }
  $('empty-action').disabled = store.busy;
  $('empty-state').dataset.state = store.error ? 'error' : filtered ? 'filtered' : 'empty';
  $('empty-icon').innerHTML = '';
  const symbol = document.createElement('span'); symbol.dataset.icon = store.error ? 'alert' : filtered ? 'search' : 'folder'; $('empty-icon').append(symbol);icons($('empty-icon'));
}
store.addEventListener('change', event => {
  updateSummary(); emptyState(); renderDetails(); list.update(event.detail?.reset);
  document.documentElement.dataset.ready = 'true'; document.documentElement.dataset.loading = 'false';
  if (!store.busy) {feedback.endLoading();feedback.workflow(2);}
});
store.addEventListener('selection', () => {renderDetails(); list.draw(true);});
store.addEventListener('error',event => toast(event.detail,{tone:'error'}));
store.addEventListener('busy', () => {clearTimeout(searchTimer);updateSummary();feedback.startLoading();feedback.workflow(1);$('file-list').setAttribute('aria-busy','true');document.documentElement.dataset.loading = 'true';});
store.addEventListener('loading', event => {$('footer-status').textContent = event.detail.message;feedback.setLoading(event.detail);});
async function load(scenario = lastScenario) {
  if (!isLocal) lastScenario = scenario;
  try {
    await store.load(scenario);localWorkspace?.restoreOptions();
    if (store.error) toast(store.error,{tone:'error'});
    else if (!store.cancelled) {if (scenario !== 'restore') effects.burst(document.querySelector('.folder-symbol'));if (isLocal && ['scan','choose'].includes(scenario)) toast(`扫描完成 · ${store.view.total.toLocaleString()} 个视频`,{tone:'success'});else if (!isLocal && scenario !== 'matched') toast(`${store.view.total.toLocaleString()} 条示例已载入`,{tone:'success'});}
  } finally {$('file-list').setAttribute('aria-busy','false');if (!store.busy) feedback.endLoading();}
}
const filter = patch => store.filter(patch).catch(error => toast(error.message));
$('search-input').addEventListener('compositionstart', () => {composing = true; clearTimeout(searchTimer);});
$('search-input').addEventListener('compositionend', () => {composing = false; filter({search: $('search-input').value});});
$('search-input').addEventListener('input', () => {clearTimeout(searchTimer); if (!composing) searchTimer = setTimeout(() => filter({search: $('search-input').value}), 100);});
effects.onFilter = status => filter({status});
$('extra-filter').addEventListener('change', event => filter({status: event.target.value || 'all'}));
$('file-type').addEventListener('change', event => filter({fileType: event.target.value}));
$('sort-name').addEventListener('click', () => filter({sortKey: 'name', sortDir: store.filters.sortKey === 'name' && store.filters.sortDir === 'asc' ? 'desc' : 'asc'}));
$('sort-score').addEventListener('click', () => filter({sortKey: 'score', sortDir: store.filters.sortKey === 'score' && store.filters.sortDir === 'asc' ? 'desc' : 'asc'}));
$('dataset-button').addEventListener('click', () => isLocal ? load('choose') : dialogs.open('dataset'));
$('appearance-button').addEventListener('click', () => dialogs.open('appearance'));
$('command-button').addEventListener('click', () => dialogs.open('command'));
$('history-button').addEventListener('click', () => dialogs.history().catch(error => toast(error.message)));
$('preview-button').addEventListener('click', () => dialogs.preview().catch(error => toast(error.message)));
$('scan-button').addEventListener('click', () => load());
$('empty-action').addEventListener('click', () => {if (store.error) load(isLocal && !store.summary.folderId ? 'choose' : undefined);else if (store.summary.counts.all) filter({search:'',status:'all',fileType:''});else load(isLocal ? store.summary.folderId ? 'scan' : 'choose' : 'matched');});
function toggleDetails(show) {drawer.toggle(show);}
$('detail-toggle').addEventListener('click', () => toggleDetails());
$('close-details').addEventListener('click', () => {drawer.toggle(false);if(innerWidth>1120) $('file-list').focus();});
$('list-items').addEventListener('dblclick', () => toggleDetails(true));
document.addEventListener('keydown', event => {
  if (event.isComposing || composing) return;
  const activeDialog = document.querySelector('dialog[open]');
  if (event.ctrlKey && event.key.toLowerCase() === 'k') {if (activeDialog && activeDialog.id !== 'command-dialog') return;event.preventDefault();if (activeDialog) dialogs.modals.command.close();else dialogs.open('command');return;}
  if (activeDialog) return;
  if (event.ctrlKey && event.key.toLowerCase() === 'f') {event.preventDefault(); $('search-input').focus(); return;}
  if (event.ctrlKey && event.key === 'Enter') {event.preventDefault(); if (!$('preview-button').disabled) $('preview-button').click(); return;}
  if (event.key === 'Escape') {if (document.activeElement === $('search-input') && store.filters.search) filter({search:''});else if (innerWidth<=1120) drawer.toggle(false);return;}
  if (event.target.closest('input,select,textarea,button') || store.busy || !store.view.total) return;
  const current = store.view.ids.indexOf(store.selectedId); const step = Math.max(1,Math.floor($('file-list').clientHeight/ROW_HEIGHT));
  const positions = {ArrowDown: current+1, ArrowUp: current-1, Home: 0, End: store.view.total-1, PageDown: current+step, PageUp: current-step};
  if (event.key in positions) {event.preventDefault(); const index = Math.max(0,Math.min(store.view.total-1,positions[event.key])); store.select(store.view.ids[index]); list.ensureVisible(index);}
  else if (event.key === 'Enter') {event.preventDefault(); toggleDetails(true);}
});
// Read-only metrics for this explicitly marked preview, not a production API.
if (!isLocal) globalThis.yingxuPreview = Object.freeze({stats: () => ({mode:'preview',total:store.view.total,selectedId:store.selectedId,revision:store.summary.revision,renderedRows:$('list-items').children.length,renderMs:list.renderMs,loadMs:adapter.loadMs,effects:effects.stats(),notice:feedback.notice.stats()})});
else localWorkspace = new LocalWorkspace({adapter,store,dialogs,feedback,load,toast,update:updateSummary});
window.addEventListener('pagehide', () => {feedback.destroy();drawer.destroy();dialogs.command.destroy();}, {once:true});
await load(isLocal ? 'restore' : 'matched');
if (isLocal && !store.error && store.summary.lastResultId) await dialogs.showResult(store.summary.lastResultId).catch(error => toast(error.message,{tone:'error'}));
