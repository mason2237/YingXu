import {modal} from '../../vendor/design-systems/modal.js';
import {appearance} from '../appearance.js';

const $ = id => document.getElementById(id);
export class WorkspaceDialogs {
  constructor(store, effects, {load, toast, mutate, feedback}) {
    Object.assign(this, {store, effects, load, toast, mutate, feedback}); this.page = 0;
    this.modals = {};
    for (const name of ['appearance', 'candidate', 'preview', 'history', 'scan-options'].filter(name => $(`${name}-dialog`))) {
      this.modals[name] = modal($(`${name}-dialog`), {reduced: () => effects.reduced, fadeClose: name === 'appearance', focusFallback: () => $('file-list').focus({preventScroll:true}), onClose: () => {
        if (name === 'preview') {store.adapter.request('preview.discard',this.plan?.snapshotId ? {snapshotId:this.plan.snapshotId} : {}).catch(error => toast(error.message,{tone:'error'}));if (this.plan) this.plan.canExecute = false;this.syncExecution?.();feedback.workflow(store.busy ? 1 : 2);}
      }});
    }
    for (const [id, key] of [['mist-setting', 'mistEnabled'], ['glass-setting', 'glassEnabled'], ['glass-strength', 'strength'], ['particle-setting', 'particlesEnabled'], ['motion-setting', 'reducedMotion'], ['lighting-setting','lighting'], ['native-hdr-setting','nativeHdr']]) {
      $(id)?.addEventListener('change', event => appearance.update({[key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value}, event.target));
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
    $('effect-status').textContent = `${stats.glassEnabled ? stats.glassMode === 'webgl2' ? '操作按钮玻璃 · 主操作透镜折射' : '操作按钮兼容玻璃材质' : '玻璃效果已关闭'} · ${mist} · ${stats.reduced ? '已关闭拖动与波纹' : '果冻拖动 / 光学任务进度 · 空闲停帧'}`;
    $('glass-strength').disabled = !stats.glassEnabled;
    if ($('lighting-setting')) $('lighting-setting').value = appearance.state.lighting;
    if ($('native-hdr-setting')) $('native-hdr-setting').checked = appearance.state.nativeHdr;
    if ($('native-hdr-status')) {
      const output = appearance.state.displayOutput || {};
      $('native-hdr-status').textContent = output.host === 'electron'
        ? output.hdrConfigured ? 'WebGPU HDR 已配置 · 实际输出待验证；文字保持普通白点' : `Electron HDR：${output.hdrReason || (output.systemHdrEnabled ? '正在验证浮点输出' : '当前系统未启用 HDR')}`
        : output.nativeHdrActive
        ? `系统 HDR 输出中 · scRGB 16 位浮点 · SDR 白电平 ${output.sdrWhiteNits} nit · 高光与局部泛光随光影档位调整`
        : output.host === 'qt-quick' ? '当前为 SDR 输出；HDR 需要显示器及 Windows HDR 同时启用。' : '兼容容器：SDR 输出；系统 HDR 请使用原生入口。';
    }
    $('particle-preview').disabled = this.effects.reduced || !this.effects.particlesEnabled;
    $('motion-description').textContent = this.effects.motion.matches ? '系统已开启减少动画，当前自动简化' : '手动简化；同时始终遵循系统设置';
  }
  open(name, origin) {if (name === 'appearance') this.effectStatus();this.modals[name].open(origin);}
}
