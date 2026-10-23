const paths = {
  brand: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M7 8h10M7 12h7M7 16h10"/>',
  folder: '<path d="M3 7V5h7l2 3h9v11H3Z"/><path d="m3 11 3-3h15"/>',
  search: '<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5 5"/>',
  refresh: '<path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5M4 14a8 8 0 0 0 14 5l3-3m0 5v-5h-5"/>',
  history: '<path d="M3 11a9 9 0 1 1 2 7M3 5v6h6M12 7v5l3 2"/>',
  settings: '<path d="m10 3-1 3-3 1-3-1-1 4 2 2-1 3 3 3 3-1 2 2 4-1 1-3 3-1 1-4-2-2V6l-3-2-3 1Z"/><circle cx="11" cy="11" r="3"/>',
  chevron: '<path d="m7 9 5 5 5-5"/>', arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  left: '<path d="M20 12H5m6-6-6 6 6 6"/>', check: '<path d="m5 12 4 4L19 6"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  video: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="m10 9 5 3-5 3Z"/>',
  preview: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16M13 9h4m-4 6h4"/>',
  sort: '<path d="M9 5v14m-3-3 3 3 3-3M15 5v14m-3-11 3-3 3 3"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M15 4v16"/>',
  compare: '<rect x="3" y="5" width="7" height="14" rx="2"/><rect x="14" y="5" width="7" height="14" rx="2"/>',
  alert: '<path d="m12 3 10 18H2Z"/><path d="M12 9v4m0 4v.1"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  spark: '<path d="m12 3 2 7 7 2-7 2-2 7-2-7-7-2 7-2Z"/>',
  minus: '<path d="M5 12h14"/>',
};
export function icon(name) {return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.video}</svg>`;}
export function icons(root = document) {root.querySelectorAll('[data-icon]').forEach(el => {el.innerHTML = icon(el.dataset.icon);});}
export function el(tag, className = '', text) {const node = document.createElement(tag); node.className = className; if (text !== undefined) node.textContent = text; return node;}
export function iconNode(name, className = '') {const node = el('span', className); node.innerHTML = icon(name); return node;}
export function button(text, className, click, iconName) {const node = el('button', className); node.type = 'button'; if (iconName) node.append(iconNode(iconName)); node.append(document.createTextNode(text)); if (click) node.addEventListener('click', click); return node;}
export function badge(state) {const classes = {'待整理': 'ready', '需确认': 'review', '存在冲突': 'conflict', '已符合': 'unchanged', '已跳过': 'skipped'}; const labels = {'待整理': '已匹配', '需确认': '待确认', '已符合': '无需变更'}; return el('span', `badge ${classes[state] || ''}`, labels[state] || state);}
export function language(value) {return el('span', 'language', value === '英语' ? 'EN' : value === '简体中文' ? '简' : value);}
