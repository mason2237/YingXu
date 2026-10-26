// Capability presentation only; the Python adapter independently denies writes.
export function applyPrototypeMode(state) {
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
