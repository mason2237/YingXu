import {modal} from '../../vendor/design-systems/modal.js';
import {el, iconNode, button, language, badge} from './icons.js';
import {appearance} from '../appearance.js';
import {commandList} from '../../vendor/design-systems/workspace-overlays.js';

const $ = id => document.getElementById(id);
export class WorkspaceDialogs {
  constructor(store, effects, {load, toast, mutate, feedback}) {
    Object.assign(this, {store, effects, load, toast, mutate, feedback}); this.page = 0;
    this.modals = {};
    for (const name of ['dataset', 'appearance', 'candidate', 'preview', 'history', 'command', 'scan-options'].filter(name => $(`${name}-dialog`))) {
      this.modals[name] = modal($(`${name}-dialog`), {reduced: () => effects.reduced, focusFallback: () => $('file-list').focus(), onClose: () => {
        if (name === 'preview') {store.adapter.request('preview.discard',this.plan?.snapshotId ? {snapshotId:this.plan.snapshotId} : {}).catch(error => toast(error.message,{tone:'error'}));if (this.plan) this.plan.canExecute = false;this.syncExecution?.();feedback.workflow(store.busy ? 1 : 2);}
        if (name === 'command') $('command-search').setAttribute('aria-expanded','false');
      }});
    }
    this.command = commandList($('command-search'),$('command-list'), {actions:() => this.commandActions?.() || [],run:async action => {await this.modals.command.close();await action.run();},onError:error => toast(error.message,{tone:'error'}),render:action => {
      const option = button('', 'command-option', null, action.symbol); option.append(el('span','command-label',action.label));if (action.shortcut) option.append(el('kbd','',action.shortcut));else option.append(iconNode('arrow','command-arrow'));return option;
    }});
    const scenarios = [
      ['matched', '匹配审阅', '多语言、待确认、未匹配与目标冲突', 'folder'],
      ['large', '大列表 · 10,000 条', '检查搜索、键盘和虚拟滚动', 'video'],
      ['empty', '空文件夹', '没有视频时的引导', 'folder'],
      ['no-subs', '没有字幕', '保留视频，人工选择入口清楚可见', 'preview'],
      ['error', '目录读取失败', '显示异常与重新加载入口', 'alert'],
    ];
    for (const [id, title, text, symbol] of this.modals.dataset ? scenarios : []) {
      const option = button('', 'dataset-option', async () => {await this.modals.dataset.close(); await load(id);});
      option.dataset.scenario = id; const copy = el('div'); copy.append(el('strong', '', title), el('small', '', text)); option.append(iconNode(symbol), copy); $('datasets').append(option);
    }
    for (const [id, key] of [['mist-setting', 'mistEnabled'], ['glass-setting', 'glassEnabled'], ['glass-strength', 'strength'], ['particle-setting', 'particlesEnabled'], ['motion-setting', 'reducedMotion']]) {
      $(id).addEventListener('change', event => appearance.update({[key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value}, event.target));
    }
    $('particle-preview').addEventListener('click', () => {effects.burst($('particle-preview')); if (effects.reduced || !effects.particlesEnabled) toast('当前已减少动态或关闭粒子反馈');});
    effects.onChange = () => {this.effectStatus();feedback.notice.refreshMotion();feedback.refreshMotion();}; this.effectStatus();
    appearance.addEventListener('error', () => this.effectStatus());
    $('preview-prev').addEventListener('click', () => {this.page--;Promise.resolve(this.renderPlan()).catch(error => toast(error.message,{tone:'error'}));});
    $('preview-next').addEventListener('click', () => {this.page++;Promise.resolve(this.renderPlan()).catch(error => toast(error.message,{tone:'error'}));});
  }
  effectStatus() {
    const stats = this.effects.stats();
    $('glass-setting').checked = stats.glassEnabled; $('glass-strength').value = stats.strength;
    $('particle-setting').checked = this.effects.particlesEnabled; $('motion-setting').checked = this.effects.manualReduced;
    $('mist-setting').checked = this.effects.mistEnabled;
    const mist = !stats.mist.enabled ? '气态列表已关闭' : stats.mist.mode === 'webgl2' ? stats.reduced ? '静态雾气' : '气态列表已启用' : '列表使用兼容材质';
    $('effect-status').textContent = `${stats.glassEnabled ? stats.glassMode === 'webgl2' ? '全按钮玻璃 · 主操作透镜折射' : '全按钮兼容玻璃材质' : '玻璃效果已关闭'} · ${mist} · ${stats.reduced ? '已关闭拖动与波纹' : '果冻拖动 / 光学任务进度 · 空闲停帧'}`;
    $('glass-strength').disabled = !stats.glassEnabled;
    $('particle-preview').disabled = this.effects.reduced || !this.effects.particlesEnabled;
    $('motion-description').textContent = this.effects.motion.matches ? '系统已开启减少动画，当前自动简化' : '手动简化；同时始终遵循系统设置';
  }
  open(name) {if (name === 'appearance') this.effectStatus();if (name === 'command') this.command.reset();this.modals[name].open();}
  async candidates() {
    const row = this.store.details; if (!row) return;
    const response = await this.store.adapter.request('review.candidates', this.store.params({rowId: row.rowId}));
    $('candidate-video').textContent = row.video.name;
    $('candidate-list').replaceChildren();
    response.rows.forEach((candidate, index) => {
      const card = el('article', `candidate-card${index === 0 ? ' recommended' : ''}`); card.dataset.candidateId = candidate.subtitleId;
      const header = el('header'); header.append(language(candidate.language), el('span', '', index === 0 ? '优先核对' : `候选 ${index + 1}`));
      card.append(header, el('h3', '', candidate.name), el('div', 'candidate-score', `${Math.round(candidate.score*100)}%`), el('p', '', candidate.reason), el('p', '', `集数标识 · ${candidate.episode}`));
      if (candidate.conflict) {const warning = el('div', 'notice warning'); warning.append(iconNode('alert'), document.createTextNode('集数冲突。建议选择其他候选。')); card.append(warning);}
      const assign = button(row.subtitles.some(sub => sub.language === candidate.language) ? '替换此语言字幕' : '使用这份字幕', index === 0 ? 'primary' : 'secondary', async () => {
        try {
          const replace = this.store.details.subtitles.find(sub => sub.language === candidate.language);
          await this.mutate('review.assign', {subtitleId: candidate.subtitleId, replaceId: replace?.subtitleId});
          await this.modals.candidate.close();
        } catch (error) {this.toast(error.message,{tone:'error'});}
      });
      card.append(assign); $('candidate-list').append(card);
    });
    if (!response.rows.length) $('candidate-list').append(el('p','command-empty','暂时没有可用候选。请返回审阅并检查字幕来源。'));
    this.modals.candidate.open();
  }
  async preview() {
    this.plan = await this.store.adapter.request('preview.create', this.store.params()); this.page = 0;
    $('preview-ack').checked = false; this.renderPlan(); this.modals.preview.open();this.feedback.workflow(3);
  }
  renderPlan() {
    const plan = this.plan;
    $('preview-summary').textContent = `${plan.changeCount} 份字幕可整理 · ${plan.unmatchedCount} 个视频未匹配 · 示例变更预览`;
    const warning = $('preview-warning'); warning.hidden = !plan.pendingCount && !plan.conflictCount;
    warning.textContent = `还有 ${plan.pendingCount} 项匹配待确认、${plan.conflictCount} 项目标冲突。请返回审阅后重新生成预览。`;
    const items = plan.items.slice(this.page*20, this.page*20+20); const fragment = document.createDocumentFragment();
    const labels = {rename: ['待整理', '待整理'], skipped: ['已跳过', '已跳过'], unchanged: ['已符合', '无需变更'], pending: ['需确认', '待确认'], blocked: ['存在冲突', '冲突阻止']};
    for (const item of items) {
      const row = el('div', 'preview-item');
      const source = el('div'); source.append(el('strong', '', item.sourceName), el('small', '', item.sourcePath));
      const target = el('div', 'preview-target'); target.append(el('strong', '', item.targetName), el('small', '', item.targetPath));
      const status = badge(labels[item.action][0]); status.lastChild.textContent = labels[item.action][1];
      row.append(source, iconNode('arrow'), target, status); fragment.append(row);
    }
    $('preview-items').replaceChildren(fragment); $('preview-items').scrollTop = 0;
    const pages = Math.max(1, Math.ceil(plan.items.length/20));
    $('preview-page-label').textContent = `${plan.items.length} 份字幕 · 第 ${this.page+1} / ${pages} 页`;
    $('preview-prev').disabled = this.page === 0; $('preview-next').disabled = this.page+1 >= pages;
  }
  async history() {
    const record = (await this.store.adapter.request('history.list'))[0];
    const root = $('history-content'); root.replaceChildren();
    if (!record) {root.append(el('p','command-empty','还没有整理记录。完成整理后，结果会显示在这里。'));this.modals.history.open();return;}
    const summary = el('section', 'history-summary'); summary.append(el('h3', '', record.title), el('p', '', record.time));
    const counts = el('div', 'result-counts');
    for (const [value, label] of [[record.success,'成功'], [record.skipped,'跳过'], [record.errors,'异常']]) {const cell = el('span'); cell.append(el('strong', '', String(value)), document.createTextNode(label)); counts.append(cell);}
    summary.append(counts);
    const distribution = el('div','result-distribution');distribution.setAttribute('aria-hidden','true');
    const total = record.success+record.skipped+record.errors;
    for (const [value,tone] of [[record.success,'success'],[record.skipped,'skipped'],[record.errors,'error']]) {const segment = el('span');segment.dataset.tone = tone;segment.style.width = `${total ? value/total*100 : 0}%`;distribution.append(segment);}
    summary.append(distribution);root.append(summary);
    const items = el('ol','history-list');
    for (const item of record.items) {const row = el('li','history-item');const names = el('div');const tone = item.state === '成功' ? 'success' : item.state.includes('跳过') ? 'skipped' : 'error';row.dataset.tone = tone;names.append(el('p','',item.source),el('small','',`→ ${item.target}`));row.append(iconNode(tone === 'error' ? 'alert' : tone === 'success' ? 'check' : 'minus'),names,el('span','history-state',item.state));items.append(row);}
    root.append(items);
    this.modals.history.open();
  }
}
