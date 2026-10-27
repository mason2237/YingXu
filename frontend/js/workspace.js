import {WorkspaceStore} from './store.js';
import {VirtualFileList, ROW_HEIGHT} from './components/file-list.js';
import {renderInspector} from './components/inspector.js';
import {Effects} from './components/upstream-effects.js';
import {icons, el, iconNode} from './components/icons.js';
import {bindKeyboardFocus} from '../vendor/design-systems/lens/focus.js';
import {appearance, bindThemeControls} from './appearance.js';
import {WorkspaceFeedback, InspectorDrawer} from './components/workspace-feedback.js';
import {prepareLocalWorkspace, LocalWorkspace} from './components/local-workspace.js';
import {applyPrototypeMode} from './components/prototype-mode.js';

const $ = id => document.getElementById(id);
const {LocalAdapter} = await import('./local-adapter.js');
const {LocalWorkspaceDialogs} = await import('./components/local-dialogs.js');
prepareLocalWorkspace();
icons(); bindKeyboardFocus(); bindThemeControls();
const adapter = new LocalAdapter(), store = new WorkspaceStore(adapter);
const electronHost = globalThis.yingxuHost;
if (electronHost?.kind === 'electron' && !electronHost.prototype) {
  const unsubscribe = electronHost.workspace.onNativeUi(identifier => {
    if (identifier === 'history-button' || identifier === 'appearance-button') document.getElementById(identifier)?.click();
  });
  window.addEventListener('pagehide', unsubscribe, {once:true});
  let depth = 0;
  const clearDrop = () => {depth = 0;document.documentElement.dataset.dragFolder = 'false';};
  window.addEventListener('dragenter', event => {
    if (event.dataTransfer?.types.includes('Files')) {event.preventDefault();depth++;document.documentElement.dataset.dragFolder = 'true';}
  });
  window.addEventListener('dragleave', () => {if (--depth <= 0) clearDrop();});
  window.addEventListener('dragover', event => {if (event.dataTransfer?.types.includes('Files')) {event.preventDefault();event.dataTransfer.dropEffect = 'copy';}});
  window.addEventListener('drop', async event => {
    event.preventDefault();clearDrop();
    if (store.busy) {toast('当前任务尚未结束，请稍候。',{tone:'error'});return;}
    const files = event.dataTransfer?.files;
    if (files?.length !== 1) {toast('请拖入一个文件夹。',{tone:'error'});return;}
    try {await electronHost.workspace.drop(files[0]);}
    catch {toast('未能读取该文件夹，请使用“选择文件夹”。',{tone:'error'});}
  });
}
const effects = new Effects($('glass-toolbar'), $('particles'));
const feedback = new WorkspaceFeedback(effects), drawer = new InspectorDrawer(effects);
const list = new VirtualFileList(store, $('file-list'), $('list-spacer'), $('list-items'));
let searchTimer, composing = false, lastScenario = 'scan',localWorkspace = null;
function toast(message, options) {feedback.toast(message, options);}
appearance.addEventListener('error', event => toast(event.detail,{tone:'error'}));
async function copyName(_text,fileId) {
  try {await adapter.request('file.copyName',{fileId});toast('视频名称已复制',{tone:'success'});}
  catch (error) {toast(error.message,{tone:'error'});}
}
async function mutate(action, params = {}) {
  try {await store.mutate(action, params); toast(action === 'review.confirm' ? '已确认匹配，文件尚未修改' : action === 'review.assign' ? '已更换字幕，请核对后确认' : action === 'review.remove' ? '已移除关联，保留原文件' : params.skipped ? '已跳过此视频' : '已恢复审阅',{tone:'success'});}
  catch (error) {toast(error.message,{tone:'error'}); throw error;}
}
const dialogs = new LocalWorkspaceDialogs(store, effects, {load: scenario => load(scenario), toast, mutate, feedback});
function renderDetails() {
  renderInspector($('inspector-content'), store.details, {error:store.detailsError,retry:() => store.select(store.selectedId),mutate: (action, params) => mutate(action, params).catch(() => {}), candidates: () => dialogs.candidates().catch(error => toast(error.message,{tone:'error'})), copy: copyName,reveal:fileId => adapter.request('file.reveal',{fileId}).catch(error => toast(error.message,{tone:'error'})), online:rowId => localWorkspace?.openSubtitles(rowId), actionsHost: $('inspector-actions')});
  if (store.busy) for (const control of document.querySelectorAll('#inspector button')) control.disabled = true;
  applyPrototypeMode(adapter.state);
}
function updateSummary() {
  const {counts = {}, subtitleCount = 0} = store.summary;
  $('overview').replaceChildren();
  for (const [value, label, symbol, attention] of [[counts.all || 0,'个视频','video'], [subtitleCount,'份关联字幕','brand'], [counts['需确认'] || 0,'项待确认','alert',true]]) {const part = el('span', attention ? 'attention' : ''); part.append(iconNode(symbol),el('strong', '', value.toLocaleString()), document.createTextNode(label)); $('overview').append(part);}
  if (store.summary.embeddedSatisfiedCount) {const part = el('span','');part.append(iconNode('check'),el('strong','',store.summary.embeddedSatisfiedCount.toLocaleString()),document.createTextNode('个内嵌已满足'));$('overview').append(part);}
  for (const [id, state] of [['count-all','all'], ['count-ready','待整理'], ['count-review','需确认'], ['count-unmatched','未匹配']]) $(id).textContent = counts[state] || 0;
  const folder = adapter.state?.summary || store.summary;
  $('folder-path').textContent = folder.displayPath || (adapter.state?.prototype ? '点击选择文件夹，开始只读扫描' : '可拖入一个本地文件夹');
  $('folder-path').title = folder.displayPath || '';
  $('folder-name').textContent = folder.folderName || '选择包含视频与字幕的文件夹';
  $('preview-count').textContent = subtitleCount;
  $('preview-button').disabled = store.busy || Boolean(store.error) || !subtitleCount;
  $('scan-button').disabled = store.busy || !folder.folderId; $('dataset-button').disabled = store.busy;
  for (const control of document.querySelectorAll('.collection-tools input,.collection-tools button,.collection-tools select,.list-heading button,.list-heading select')) control.disabled = store.busy;
  $('inspector').inert = store.busy;
  $('file-list').setAttribute('aria-busy',String(store.busy));
  for (const control of document.querySelectorAll('#inspector button')) control.disabled = store.busy;
  $('list-count').textContent = `${store.view.total.toLocaleString()} / ${(counts.all || 0).toLocaleString()} 个视频`;
  $('footer-status').textContent = store.error ? '读取失败，请检查目录后重新扫描' : store.loading ? '正在处理本地任务…' : !folder.folderId ? '选择文件夹，开始扫描' : folder.needsScan ? folder.finished ? '本批整理已结束，重新扫描可核对文件' : '选项已更新，请重新扫描' : `${counts['需确认'] || 0} 项待确认 · ${counts['存在冲突'] || 0} 项冲突`;
  if (!store.error && !store.loading && !folder.needsScan && folder.embeddedSatisfiedCount) $('footer-status').textContent = `${folder.embeddedSatisfiedCount} 个视频内嵌字幕已满足 · ${counts['需确认'] || 0} 项待确认`;
  if (!store.error && !store.busy && store.detailsError) $('footer-status').textContent = '扫描结果已保留 · 当前详情未载入，可重试或选择其他视频';
  $('search-input').value = store.filters.search;
  $('file-type').value = store.filters.fileType;
  document.querySelectorAll('[data-filter]').forEach(button => {const chosen = button.dataset.filter === store.filters.status; button.classList.toggle('selected', chosen); button.setAttribute('aria-pressed', chosen);});
  effects.syncFilter(store.filters.status);
  $('extra-filter').value = ['存在冲突','已跳过','已符合'].includes(store.filters.status) ? store.filters.status : '';
  const notice = $('scan-warnings'),warnings = folder.scanWarnings || [],signature = JSON.stringify([folder.scanWarningCount,warnings]);
  notice.hidden = !folder.scanWarningCount;
  if (notice.dataset.signature !== signature) {
    notice.dataset.signature = signature;notice.firstChild.textContent = `扫描与导入提示 · ${folder.scanWarningCount || 0} 项`;
    const items = $('scan-warning-items');items.replaceChildren();for (const message of warnings) items.append(el('li','',message));
    if (folder.scanWarningCount > warnings.length) items.append(el('li','',`另有 ${folder.scanWarningCount-warnings.length} 项；请核对目录权限和文件来源后重扫。`));
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
  $('empty-action').textContent = store.error ? '重新扫描' : filtered ? '清除搜索与筛选' : '选择文件夹';
  if (!filtered) {
    const summary = adapter.state?.summary || store.summary;
    $('empty-title').textContent = store.error ? '暂时无法读取这个目录' : summary.finished ? '本批整理已结束' : summary.needsScan ? '扫描文件，建立匹配关系' : summary.folderId ? '这个目录还没有视频' : '从一个文件夹开始';
    $('empty-message').textContent = store.error || (summary.finished ? '实际结果已保存在操作记录中。重新扫描可核对当前文件。' : summary.needsScan ? '扫描只读取文件；核对预览并确认后才会整理字幕。' : adapter.state?.prototype ? '选择包含视频与字幕的目录。对比原型仅扫描与预览，文件保持原样。' : '选择或拖入包含视频与字幕的目录。所有文件均在本机处理。');
    $('empty-action').textContent = summary.folderId ? '重新扫描' : '选择文件夹';
  }
  $('empty-action').disabled = store.busy;
  $('empty-state').dataset.state = store.error ? 'error' : filtered ? 'filtered' : 'empty';
  $('empty-icon').innerHTML = '';
  const symbol = document.createElement('span'); symbol.dataset.icon = store.error ? 'alert' : filtered ? 'search' : 'folder'; $('empty-icon').append(symbol);icons($('empty-icon'));
}
store.addEventListener('change', async event => {
  updateSummary(); emptyState(); renderDetails(); await list.update(event.detail?.reset);
  if (store.busy) return;
  document.documentElement.dataset.ready = 'true'; document.documentElement.dataset.loading = 'false';
  if (!store.busy) {feedback.endLoading();feedback.workflow(2);}
});
store.addEventListener('selection', () => {updateSummary();renderDetails(); list.draw(true);});
store.addEventListener('error',event => toast(event.detail,{tone:'error'}));
store.addEventListener('busy', () => {clearTimeout(searchTimer);updateSummary();feedback.startLoading();feedback.workflow(1);$('file-list').setAttribute('aria-busy','true');document.documentElement.dataset.loading = 'true';});
store.addEventListener('loading', event => {$('footer-status').textContent = event.detail.message;feedback.setLoading(event.detail);});
async function load(scenario = lastScenario) {
  try {
    await store.load(scenario);localWorkspace?.restoreOptions();
    if (store.error) toast(store.error,{tone:'error'});
    else if (!store.cancelled) {if (scenario !== 'restore') effects.burst(document.querySelector('.folder-symbol'));if (['scan','choose'].includes(scenario)) toast(`扫描完成 · ${store.view.total.toLocaleString()} 个视频`,{tone:'success'});}
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
$('dataset-button').addEventListener('click', () => load('choose'));
$('appearance-button').addEventListener('click', event => dialogs.open('appearance',event.currentTarget));
$('history-button').addEventListener('click', () => dialogs.history().catch(error => toast(error.message)));
$('preview-button').addEventListener('click', () => dialogs.preview().catch(error => toast(error.message)));
$('scan-button').addEventListener('click', () => load());
$('empty-action').addEventListener('click', () => {if (store.error) load(!store.summary.folderId ? 'choose' : undefined);else if (store.summary.counts.all) filter({search:'',status:'all',fileType:''});else load(store.summary.folderId ? 'scan' : 'choose');});
function toggleDetails(show) {drawer.toggle(show);}
$('detail-toggle').addEventListener('click', () => toggleDetails());
$('close-details').addEventListener('click', () => {drawer.toggle(false);if(innerWidth>1120) $('file-list').focus();});
$('list-items').addEventListener('dblclick', () => toggleDetails(true));
document.addEventListener('keydown', event => {
  if (event.isComposing || composing) return;
  const activeDialog = document.querySelector('dialog[open]');
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
localWorkspace = new LocalWorkspace({adapter,store,dialogs,feedback,load,toast,update:updateSummary});
window.addEventListener('pagehide', () => {feedback.destroy();drawer.destroy();}, {once:true});
await load('restore');
if (!store.error && store.summary.lastResultId) await dialogs.showResult(store.summary.lastResultId).catch(error => toast(error.message,{tone:'error'}));
// Reveal one coherent frame: resolved theme, offline font, controls and glass.
effects.buttons.refresh();
await document.fonts.ready;
document.documentElement.dataset.desktopBoot = 'painting';
// An occluded native view can suspend rAF while its loading cover waits for
// this signal. Fonts, channel and DOM are already ready; bound only paint wait.
await new Promise(resolve => {
  const finish = () => {clearTimeout(deadline);resolve();};
  const deadline = setTimeout(finish,200);
  requestAnimationFrame(() => requestAnimationFrame(finish));
});
document.documentElement.dataset.desktopBoot = 'ready';
if (globalThis.yingxuHost?.kind === 'electron') {
  const {startHdrLayer} = await import('./hdr-layer.js');
  startHdrLayer();
}
