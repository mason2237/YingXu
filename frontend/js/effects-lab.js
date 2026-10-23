import {createComponent, componentCatalog} from '../vendor/design-systems/lens/index.js';
import {modal} from '../vendor/design-systems/modal.js';
import {LensRuntime, ENHANCED_MATERIAL, drawWorkbenchArtwork, LENS_ORIGIN} from './components/lens-runtime.js';
import {Effects as LegacyEffects} from './components/effects.js';
import {el} from './components/icons.js';
import {appearance, bindThemeControls} from './appearance.js';

const $ = id => document.getElementById(id);
bindThemeControls();
const runtimes = [], handles = [], abort = new AbortController();
const demos = new Map();
const legacy = new LegacyEffects($('legacy-surface'), $('legacy-particles'));
let current = null, galleryRuntime = null, dialogRuntime = null, dialogPanel = null;
let pressCount = 0, variant = false, timers = [], destroyed = false;
const usage = {
  button: '操作按钮 · 按压、拖动回弹', 'icon-button': '图标动作 · 状态反光', switch: '设置开关 · 滑动吸附',
  'toggle-tile': '可选设置 · 选中光学反馈', choices: '目录策略 · 胶囊选中', tabs: '审阅模式 · 流体指示层',
  dock: '导航示例 · 连续选中层', slider: '材质强度 · 光学滑钮', stepper: '数值选项 · 边界反馈',
  notification: '通知示例 · 拖动与关闭', menu: '就地操作 · 开合与键盘', search: '名称搜索 · 原生输入',
  panel: '浮层材质 · 弹性按压', lens: '光学验证 · 自由拖动', 'card-list': '候选卡片 · 原生滚动/吸附',
  progress: '示例进度 · 波动与完成流光', 'drop-select': '候选选项 · 凹槽吸附/汇入', 'xy-slider': '光学验证 · 二维放大透镜',
};

function report(value) {$('component-value').textContent = typeof value === 'string' ? value : JSON.stringify(value);}
function feedback(label) {$('comparison-feedback').textContent = `${label} · 界面反馈 ${++pressCount} 次`;}
function samplePanel(label) {
  const action = createComponent('button', {label: '试按反馈', onPress: () => feedback(label)});
  const row = el('div', 'sample-actions'); row.append(action.element, el('span', '', '96% · 已匹配'));
  const panel = createComponent('panel', {label, motion: 'press', children: [el('strong', '', '山海之间 · 第一季'), el('p', '', '12 个视频 · 字幕审阅'), row]});
  panel.element.classList.add('sample-panel');
  return {element: panel.element, destroy() {action.destroy(); panel.destroy();}};
}

for (const [id, material, title] of [['original-stage', 'thick', '原版材质'], ['enhanced-stage', ENHANCED_MATERIAL, '增强适配']]) {
  const panel = samplePanel(title); handles.push(panel); $(id).append(panel.element);
  runtimes.push(new LensRuntime($(id), {material}));
}
$('legacy-press').addEventListener('click', () => feedback('原简化版'), {signal: abort.signal});

function stopDemo() {
  timers.forEach(clearTimeout); timers = [];
  if (current?.name === 'progress') current.handle.setMotion('off');
}

function makeComponent(name) {
  const change = value => report(value);
  const options = [{value: 'review', label: '审阅匹配', icon: 'layers'}, {value: 'preview', label: '预览变更', icon: 'focus'}, {value: 'history', label: '操作记录', icon: 'home'}];
  const configs = {
    button: {label: '确认此示例', onPress: () => report(`界面反馈 ${++pressCount} 次 · 未执行文件操作`)},
    'icon-button': {label: '标记此示例', icon: 'heart', pressed: false, onChange: change},
    switch: {label: '启用此示例', checked: false, onChange: change},
    'toggle-tile': {label: '英语字幕', icon: 'layers', checked: true, onLabel: '已启用', offLabel: '已关闭', onChange: change},
    choices: {label: '字幕位置示例', options: [{value: 'source', label: '保留原目录'}, {value: 'video', label: '视频同目录'}], onChange: change},
    tabs: {label: '审阅视图', options: [{value: 'a', label: '匹配关系', content: '原文件名、匹配字幕与评分'}, {value: 'b', label: '变更预览', content: '原名称 → 最终名称 · 仅示例'}], onChange: change},
    dock: {label: '导航示例', options, onChange: change},
    slider: {label: '折射强度示例', min: 0, max: 100, value: 65, onChange: change},
    stepper: {label: '每页数量示例', min: 5, max: 30, step: 5, value: 15, unit: '项', decreaseLabel: '减少数量', increaseLabel: '增加数量', onChange: change},
    notification: {title: '示例预览已就绪', description: '可查看原名与目标名；未执行文件操作。', dismissLabel: '关闭示例通知', onDismiss: () => report('通知已关闭，点击重置可恢复')},
    menu: {label: '查看示例名称', options: [{value: 'source', label: '查看原名称', icon: 'layers'}, {value: 'target', label: '查看目标名称', icon: 'focus'}], onAction: value => report(value === 'source' ? '山海之间.第01集.chs.srt' : '山海之间.S01E01.chs.srt')},
    search: {label: '搜索示例名称', placeholder: '输入山海、S01E01 或不存在的名称', onChange: value => report(value && !'山海之间.S01E01.chs.srt'.toLowerCase().includes(value.toLowerCase()) ? '0 条符合条件的示例' : '1 条符合条件的示例')},
    panel: {label: '弹性面板示例', motion: 'tether', children: [el('h3', '', '按住边缘，轻轻拖动'), el('p', '', '原版弹性与材质共同变化，松手后回到原位。')]},
    lens: {label: '自由光学透镜', caption: '拖动透镜 · 方向键微调'},
    'card-list': {label: '候选示例卡片', previousLabel: '上一个候选', nextLabel: '下一个候选', autoScroll: false, items: [1, 2, 3, 4, 5, 6].map(i => ({id: `candidate-${i}`, label: `字幕候选 ${i}`, title: `S01E0${i}`, description: '保留原名，人工核对片源版本'}))},
    progress: {label: '示例进度', value: 35, motion: 'off', wave: true, completeLabel: '示例完成', completionColor: 'green', onChange: change, onComplete: () => report('示例进度完成 · 未执行文件操作')},
    'drop-select': {label: '候选语言', variant: variant ? 'capsule' : 'lens', dragLabel: '拖动或使用方向键，体验凹槽吸附', options: [{value: 'chs', label: '简体中文', icon: 'leaf'}, {value: 'eng', label: '英语', icon: 'sun'}, {value: 'both', label: '双语', icon: 'layers'}], onChange: change},
    'xy-slider': {label: '二维材质示例', xLabel: '水平', yLabel: '垂直', variant: variant ? 'point' : 'lens', instruction: '拖动透镜或使用方向键；Home 恢复中心。', onChange: change, onCommit: change},
  };
  return createComponent(name, configs[name]);
}

function selectComponent(name, keepVariant = false) {
  stopDemo();
  if (!keepVariant) variant = false;
  const entry = componentCatalog.find(item => item.name === name);
  if (!demos.size) {
    for (const item of componentCatalog) {
      const handle = makeComponent(item.name), holder = el('div', 'demo-holder');
      holder.hidden = item.name !== name; holder.append(handle.element); $('gallery-stage').append(holder);
      demos.set(item.name, {name: item.name, handle, holder});
    }
    galleryRuntime = new LensRuntime($('gallery-stage'), {reduced: $('lab-reduced').checked, audio: $('lab-audio').checked});
  }
  for (const item of demos.values()) item.holder.hidden = item.name !== name;
  current = demos.get(name); const {handle} = current;
  const defaults = {'icon-button': false, switch: false, 'toggle-tile': true, choices: 'source', tabs: 'a', dock: 'review', slider: 65, stepper: 15, search: '', progress: 35, 'drop-select': 'chs', 'xy-slider': {x: 0, y: 0}};
  if (Object.hasOwn(defaults, name)) handle.setValue(defaults[name], {animate: false});
  if (name === 'notification') handle.show();
  if (name === 'menu') handle.close();
  if (name === 'drop-select') handle.setVariant(variant ? 'capsule' : 'lens');
  if (name === 'xy-slider') handle.setVariant(variant ? 'point' : 'lens');
  if (name === 'lens' || name === 'panel') galleryRuntime.system?.jelly.target(handle.element, 0);
  $('gallery-stage').dataset.component = name;
  galleryRuntime.system?.renderer?.invalidate(300);
  if (!$('lab-enabled').checked) galleryRuntime.stop();
  $('component-title').textContent = entry.zh; $('component-name').textContent = name;
  $('component-use').textContent = usage[name];
  $('demo-variant').hidden = !['drop-select', 'xy-slider'].includes(name);
  $('demo-run').disabled = false;
  document.querySelectorAll('[data-component]').forEach(button => {if (button.tagName === 'BUTTON') button.setAttribute('aria-current', String(button.dataset.component === name));});
  report(handle.value ?? '可直接操作原版控件');
}

for (const [index, entry] of componentCatalog.entries()) {
  const button = el('button'); button.type = 'button'; button.dataset.component = entry.name;
  button.append(document.createTextNode(entry.zh), el('span', '', String(index + 1).padStart(2, '0')));
  button.addEventListener('click', () => selectComponent(entry.name), {signal: abort.signal});
  $('component-nav').append(button);
}

function runDemo() {
  if (!current) return;
  const {name, handle} = current;
  if (name === 'progress') {
    stopDemo(); handle.setMotion($('lab-reduced').checked ? 'off' : 'system'); handle.setValue(0);
    for (let i = 1; i <= 5; i++) timers.push(setTimeout(() => handle.setValue(i * 20, {emit: true}), i * 280));
    timers.push(setTimeout(() => handle.setMotion('off'), 2400));
  } else if (['switch', 'toggle-tile', 'icon-button'].includes(name)) handle.setValue(!handle.value, {emit: true});
  else if (name === 'choices') handle.setValue(handle.value === 'source' ? 'video' : 'source', {emit: true});
  else if (name === 'tabs') handle.setValue(handle.value === 'a' ? 'b' : 'a', {emit: true});
  else if (name === 'dock') handle.setValue(handle.value === 'review' ? 'preview' : 'review', {emit: true});
  else if (name === 'slider') handle.setValue(handle.value === 65 ? 90 : 65, {emit: true});
  else if (name === 'stepper') handle.setValue(handle.value === 15 ? 25 : 15, {emit: true});
  else if (name === 'drop-select') handle.setValue(handle.value === 'chs' ? 'eng' : 'chs', {emit: true});
  else if (name === 'xy-slider') handle.setValue({x: 45, y: -25}, {emit: true});
  else if (name === 'card-list') {handle.scrollTo('candidate-4'); report('已滚动到候选 4');}
  else if (name === 'notification') {handle.show(); report('通知已显示，可点击关闭');}
  else if (name === 'menu') {handle.open(); report('菜单已展开，支持方向键与 Escape');}
  else if (name === 'search') {handle.setValue('S01E01'); report('1 条符合条件的示例');}
  else if (name === 'button') handle.element.click();
  else {galleryRuntime.system?.jelly.pulse(handle.element); report('已触发原版弹性反馈');}
}
$('demo-run').addEventListener('click', runDemo, {signal: abort.signal});
$('demo-reset').addEventListener('click', () => selectComponent(current.name), {signal: abort.signal});
$('demo-variant').addEventListener('click', () => {variant = !variant; selectComponent(current.name, true);}, {signal: abort.signal});

function configure() {
  const enabled = $('lab-enabled').checked, reduced = $('lab-reduced').checked;
  document.documentElement.dataset.reduced = String(reduced);
  legacy.glassEnabled = enabled; legacy.manualReduced = reduced; legacy.configure();
  for (const runtime of [...runtimes, galleryRuntime, dialogRuntime].filter(Boolean)) {
    runtime.setReduced(reduced);
    if (enabled) runtime.start(); else runtime.stop();
    runtime.setAudio($('lab-audio').checked);
  }
  if (reduced && current?.name === 'progress') stopDemo();
}
for (const id of ['lab-enabled', 'lab-reduced', 'lab-audio']) $(id).addEventListener('change', configure, {signal: abort.signal});
appearance.addEventListener('change', () => {
  [...runtimes, galleryRuntime, dialogRuntime].filter(Boolean).forEach(runtime => runtime.setTheme(appearance.state.resolvedTheme));
}, {signal: abort.signal});
$('lab-scene').addEventListener('change', event => {
  [...runtimes, galleryRuntime, dialogRuntime].filter(Boolean).forEach(runtime => runtime.setBackdrop(event.target.value));
}, {signal: abort.signal});
const dialog = modal($('lens-dialog'), {reduced: () => $('lab-reduced').checked || matchMedia('(prefers-reduced-motion: reduce)').matches, onClose: () => {
  dialogRuntime?.destroy(); dialogPanel?.destroy(); dialogRuntime = dialogPanel = null; $('dialog-stage').replaceChildren();
}});
$('open-lens-dialog').addEventListener('click', () => {
  dialog.open(); dialogPanel = samplePanel('弹窗内材质'); $('dialog-stage').append(dialogPanel.element);
  dialogRuntime = new LensRuntime($('dialog-stage'), {reduced: $('lab-reduced').checked});
  dialogRuntime.setBackdrop($('lab-scene').value);
  if (!$('lab-enabled').checked) dialogRuntime.stop();
}, {signal: abort.signal});

function dispose() {
  if (destroyed) return; destroyed = true; stopDemo(); abort.abort();
  [...runtimes, galleryRuntime, dialogRuntime].filter(Boolean).forEach(runtime => runtime.destroy());
  handles.forEach(handle => handle.destroy()); demos.forEach(item => item.handle.destroy()); dialogPanel?.destroy();
  legacy.stop(); legacy.glass.resize.disconnect();
}
document.addEventListener('visibilitychange', () => {if (document.hidden) stopDemo();}, {signal: abort.signal});
window.addEventListener('pagehide', dispose, {once: true});
selectComponent('drop-select');
// Diagnostics on an explicit development page; no file/OS capabilities.
globalThis.yingxuEffectsLab = Object.freeze({stats: () => ({
  origin: LENS_ORIGIN, componentCount: componentCatalog.length, active: current?.name,
  value: current?.handle.value, comparisons: runtimes.map(runtime => runtime.stats()),
  gallery: galleryRuntime?.stats(), dialog: dialogRuntime?.stats() || null,
  legacy: legacy.stats(), destroyed,
})});
document.documentElement.dataset.ready = 'true';
