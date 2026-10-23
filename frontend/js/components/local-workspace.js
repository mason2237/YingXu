import {el,button,iconNode} from './icons.js';

const $ = id => document.getElementById(id);
const pageControls = prefix => {
  const root = el('div','page-nav');root.id = `${prefix}-paging`;
  const previous = button('','icon-button small',null,'left');previous.id = `${prefix}-previous`;previous.setAttribute('aria-label','上一页');
  const next = button('','icon-button small',null,'arrow');next.id = `${prefix}-next`;next.setAttribute('aria-label','下一页');
  const label = el('span');label.id = `${prefix}-page`;root.append(previous,label,next);return root;
};

export function prepareLocalWorkspace() {
  document.title = '映序 · 字幕工作台';
  document.documentElement.dataset.workspaceMode = 'local';document.querySelector('.preview-badge').hidden = true;
  $('dataset-dialog').remove();$('dataset-button').replaceChildren(iconNode('folder'),document.createTextNode('选择文件夹'));
  $('scan-button').replaceChildren(iconNode('refresh'),document.createTextNode('扫描文件'));
  const options = button('扫描选项','subtle-button',null,'settings');options.id = 'scan-options-button';$('scan-button').before(options);
  const reveal = button('','icon-button',null,'folder');reveal.id = 'open-folder-button';reveal.setAttribute('aria-label','打开所选文件夹');reveal.disabled = true;$('dataset-button').before(reveal);
  document.querySelector('.footer-mode').textContent = '仅在本地处理 · 不上传文件';
  const warnings = el('details','scan-notice');warnings.id = 'scan-warnings';warnings.hidden = true;
  const messages = el('ul');messages.id = 'scan-warning-items';warnings.append(el('summary'),messages);document.querySelector('.collection').prepend(warnings);
  const actions = el('div','footer-actions');$('preview-button').before(actions);
  const stop = button('取消扫描','stop-task',null,'x');stop.id = 'stop-task';stop.hidden = true;actions.append(stop,$('preview-button'));
  $('preview-dialog').querySelector('.confirmation-strip > span').textContent = '只执行本次核对的固定计划；文件发生变化时会阻止操作，已有文件不会被覆盖。';
  $('execute-button').replaceChildren(iconNode('check'),document.createTextNode('确认整理'));
  $('execute-button').title = '请先核对目标并勾选确认';
  $('history-dialog').querySelector('.eyebrow').textContent = '保存在本机';
  $('history-dialog').querySelector('.dialog-footer .subtle-text').textContent = '已完成的变更会保留，可导出完整记录。';
  const chooser = el('select','history-chooser');chooser.id = 'history-record';chooser.setAttribute('aria-label','选择本地整理记录');$('history-title').after(chooser);
  const warning = el('div','notice error');warning.id = 'history-warning';warning.hidden = true;$('history-content').before(warning);
  const exportButton = button('导出记录','secondary');exportButton.id = 'export-record';
  $('history-dialog').querySelector('.dialog-footer').prepend(pageControls('history'),exportButton);
  $('candidate-dialog').querySelector('.dialog-footer').prepend(pageControls('candidate'));
  const dialog = el('dialog','compact-dialog');dialog.id = 'scan-options-dialog';dialog.setAttribute('aria-labelledby','scan-options-title');
  const heading = el('div','dialog-heading'), title = el('h2','','扫描选项');title.id = 'scan-options-title';title.tabIndex = -1;title.setAttribute('data-initial-focus','');
  const close = button('','icon-button',null,'x');close.dataset.close = '';close.setAttribute('aria-label','关闭扫描选项');heading.append(title,close);dialog.append(heading);
  for (const [id,label,description,checked] of [
    ['recursive-setting','包含子文件夹','读取所选目录中的视频与字幕',true],
    ['move-setting','字幕移至视频所在目录','关闭时保留字幕原来的文件夹',false],
  ]) {
    const row = el('label','setting-row'),copy = el('span'),input = el('input');input.type = 'checkbox';input.id = id;input.checked = checked;input.role = 'switch';
    copy.append(el('strong','',label),el('small','',description));row.append(copy,input);dialog.append(row);
  }
  dialog.append(el('p','dialog-note','更改选项后需要重新扫描；之前的匹配计划和预览会失效。'));
  const scan = button('开始扫描','primary',null,'refresh');scan.id = 'scan-options-start';dialog.append(scan);document.body.append(dialog);
}

export class LocalWorkspace {
  constructor({adapter,store,dialogs,feedback,load,toast,update}) {
    Object.assign(this,{adapter,store,dialogs,feedback,load,toast,update});this.lastJob = null;
    adapter.readOptions = () => ({recursive:$('recursive-setting').checked,move:$('move-setting').checked});
    $('scan-options-button').addEventListener('click',() => dialogs.open('scan-options'));
    $('scan-options-start').addEventListener('click',async () => {await dialogs.modals['scan-options'].close();load('scan').catch(error => toast(error.message,{tone:'error'}));});
    $('open-folder-button').addEventListener('click',() => adapter.request('file.reveal',{fileId:store.summary.folderId}).catch(error => toast(error.message,{tone:'error'})));
    $('stop-task').addEventListener('click',async () => {
      const job = adapter.state?.job;if (!job) return;$('stop-task').disabled = true;
      try {await adapter.request(job.kind === 'scan' ? 'scan.cancel' : 'job.stop',{jobId:job.jobId});}
      catch (error) {toast(error.message,{tone:'error'});this.sync();}
    });
    for (const id of ['recursive-setting','move-setting']) $(id).addEventListener('change',async () => {
      const options = adapter.readOptions();$('recursive-setting').disabled = $('move-setting').disabled = true;
      try {await adapter.request('scan.configure',options);await load('restore');toast('扫描选项已更新，请重新扫描');}
      catch (error) {toast(error.message,{tone:'error'});this.restoreOptions();}
      finally {$('recursive-setting').disabled = $('move-setting').disabled = false;this.sync();}
    });
    adapter.addEventListener('folderdrop',() => {if (!store.loading) load('scan').catch(error => toast(error.message,{tone:'error'}));});
    adapter.addEventListener('error',event => toast(event.detail,{tone:'error'}));
    adapter.addEventListener('backend',event => {
      const {job,busy} = event.detail;
      if (busy && job?.status === 'running') {
        if (job.jobId !== this.lastJob) {feedback.startLoading();this.lastJob = job.jobId;}
        feedback.setLoading(job);feedback.workflow(job.kind === 'scan' ? 1 : job.kind === 'apply' ? 3 : 2);
      } else if (!store.loading) feedback.endLoading();
      update();this.sync();dialogs.syncExecution();
    });
    window.addEventListener('keydown',event => {
      if (event.isComposing || document.querySelector('dialog[open]')) return;
      if (event.ctrlKey && event.key.toLowerCase() === 'o') {event.preventDefault();if (!store.busy) load('choose');}
      if (event.key === 'F5') {event.preventDefault();if (!store.busy && store.summary.folderId) load('scan');}
    });
  }
  restoreOptions() {const options = this.adapter.state?.summary.options;if (options) {$('recursive-setting').checked = options.recursive;$('move-setting').checked = options.move;}}
  sync() {
    const {adapter,store} = this,job = adapter.state?.job;
    $('scan-options-button').disabled = store.busy;$('scan-options-start').disabled = store.busy || !store.summary.folderId;
    $('open-folder-button').disabled = store.busy || !store.summary.folderId;
    const stopping = adapter.state?.busy && job?.status === 'running' && ['scan','apply'].includes(job.kind);
    $('stop-task').hidden = !stopping;$('stop-task').disabled = Boolean(job?.stopRequested);
    $('stop-task').lastChild.textContent = job?.stopRequested ? '正在停止…' : job?.kind === 'apply' ? '停止整理' : '取消扫描';
    $('history-button').disabled = store.busy;
    if (stopping || (job && ['failed','cancelled'].includes(job.status))) $('footer-status').textContent = job.message;
  }
}
