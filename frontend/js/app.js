import {BridgeClient} from './bridge-client.js';

const $ = id => document.getElementById(id);
const client = new BridgeClient();
let ready = false;
let sampleBusy = false;

function error(message) { $('error').textContent = message; $('error').hidden = false; }
function clearError() { $('error').hidden = true; }
function updateButtons() {
  $('ping-button').disabled = !ready;
  $('sample-button').disabled = !ready || sampleBusy;
  $('sample-button').textContent = sampleBusy ? '正在检查…' : '运行只读样本';
}

function showRows(result) {
  const fragment = document.createDocumentFragment();
  for (const row of result.rows) {
    for (const subtitle of row.subtitles) {
      const tr = document.createElement('tr');
      const source = document.createElement('td');
      const video = document.createElement('span'); video.className = 'video-name'; video.textContent = row.videoName;
      const name = document.createElement('span'); name.className = 'subtitle-name'; name.textContent = subtitle.name;
      source.append(video, name);
      const target = document.createElement('td'); target.textContent = subtitle.targetName;
      const status = document.createElement('td'); status.className = 'status-text'; status.textContent = `${row.state} · ${Math.round(subtitle.score * 100)}%`;
      tr.append(source, target, status); fragment.append(tr);
    }
  }
  $('sample-rows').replaceChildren(fragment);
  $('sample-empty').hidden = true; $('sample-table').hidden = false;
  $('sample-count').textContent = `${result.videoCount} 个视频 / ${result.subtitleCount} 份字幕 · 样本未改动`;
}

function render(state) {
  const runtime = state.runtime;
  $('runtime').textContent = `Python ${runtime.python} · Qt ${runtime.qt} · Chromium ${runtime.chromium}`;
  sampleBusy = state.status === 'running';
  if (state.job) {
    $('sample-status').textContent = state.job.message;
    $('sample-status').dataset.status = state.job.status;
    if (state.job.result) showRows(state.job.result);
  }
  updateButtons();
}

client.addEventListener('state', event => {
  render(event.detail.payload);
  $('connection').dataset.sequence = String(event.detail.sequence);
});

$('ping-button').addEventListener('click', async () => {
  clearError(); $('ping-button').disabled = true;
  try {
    const reply = await client.call('app.ping', {message: $('ping-input').value});
    $('echo-output').textContent = `${reply.source} 已收到：${reply.message}`;
    $('echo-output').dataset.received = 'true';
  } catch (failure) { error(failure.message); $('reconnect').hidden = false; }
  finally { updateButtons(); }
});
$('ping-input').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.isComposing && !$('ping-button').disabled) $('ping-button').click();
});
$('sample-button').addEventListener('click', async () => {
  clearError(); sampleBusy = true; updateButtons();
  $('sample-status').textContent = '正在准备临时样本…';
  try { await client.call('diagnostics.runSample'); }
  catch (failure) {
    error(failure.message);
    try { render(await client.call('app.state')); }
    catch {
      ready = false; sampleBusy = false;
      $('connection-label').textContent = '连接中断，请重新连接';
      $('connection-dot').className = 'dot error';
      $('reconnect').hidden = false; updateButtons();
    }
  }
});
$('reconnect').addEventListener('click', () => location.reload());

try {
  const state = await client.connect();
  ready = true;
  $('connection-label').textContent = '已连接本地 Python';
  $('connection-dot').className = 'dot ready';
  $('connection').dataset.ready = 'true';
  render(state);
} catch (failure) {
  $('connection-label').textContent = '连接未完成';
  $('connection-dot').className = 'dot error';
  $('reconnect').hidden = false;
  error(failure.message);
}
