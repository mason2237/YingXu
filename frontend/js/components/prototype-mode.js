// Capability presentation only; the Python adapter independently denies writes.
export function applyPrototypeMode(state) {
  if(state?.runtime==='python-stdlib'&&state?.executionAvailable) {
    const mode=document.querySelector('.footer-mode');if(mode&&mode.textContent!=='本机整理 · 可恢复与撤销')mode.textContent='本机整理 · 可恢复与撤销';
    const control=document.querySelector('#export-record');if(control){control.hidden=state.stage==='R3';if(control.hidden)control.disabled=true;}
    return;
  }
  if(state?.stage==='R2') {
    const mode=document.querySelector('.footer-mode');if(mode&&mode.textContent!=='预览模式 · 文件保持原样')mode.textContent='预览模式 · 文件保持原样';
    for(const control of document.querySelectorAll('#execute-button,#preview-ack,#export-record')){control.disabled=true;control.title='此版本暂不执行文件变更或导出';}
    return;
  }
  if (!state?.prototype) return;
  const root = document.documentElement;
  if (root.dataset.prototype !== 'true') root.dataset.prototype = 'true';
  const mode = document.querySelector('.footer-mode');
  if (mode && mode.textContent !== 'Electron 对比原型 · 仅扫描预览') mode.textContent = 'Electron 对比原型 · 仅扫描预览';
  for (const control of document.querySelectorAll('#online-subtitles-button,#inspector-actions button,.online-current,#inspector .subtitle-detail button,#inspector .detail-section-title button,#inspector .embedded-details button,#execute-button,#preview-ack,#export-record')) {
    if (!control.disabled) control.disabled = true;
    if (control.title !== '对比原型：此功能暂未开放') control.title = '对比原型：此功能暂未开放';
  }
}
