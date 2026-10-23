import {transientNotice, tooltips} from '../../vendor/design-systems/workspace-overlays.js';
import {createOpticalProgress} from '../../vendor/design-systems/lens/optical-components.js';
import {modal} from '../../vendor/design-systems/modal.js';
import {iconNode} from './icons.js';
import {LensRuntime} from './lens-runtime.js';

const $ = id => document.getElementById(id);
function progressArtwork(ctx,{width,height,dpr}) {
  const dark = document.documentElement.dataset.theme === 'dark';
  ctx.fillStyle = dark ? '#203146' : '#e9eff7';ctx.fillRect(0,0,width,height);
  ctx.strokeStyle = dark ? '#96b5dd40' : '#ffffffb3';ctx.lineWidth = dpr;
  ctx.beginPath();ctx.moveTo(0,height*.5);ctx.lineTo(width,height*.5);ctx.stroke();
}

export class WorkspaceFeedback {
  constructor(effects) {
    this.effects = effects;
    this.notice = transientNotice($('toast'), {reduced:() => effects.reduced, paint:(message,tone) => {
      $('toast-message').textContent = message; $('toast').dataset.tone = tone;
      $('toast-symbol').replaceChildren(iconNode(tone === 'error' ? 'alert' : tone === 'success' ? 'check' : 'spark'));
    }});
    this.tips = tooltips({reduced:() => effects.reduced});
    this.local = globalThis.__yingxuWorkspaceMode === 'local';
    this.progress = createOpticalProgress({label:this.local ? '本地任务进度' : '准备示例数据',completeLabel:'任务已完成',wave:true,motion:effects.reduced ? 'off' : 'system'});
    $('loading-progress').append(this.progress.element);
    this.progressHost = $('loading-progress');this.progressHost.classList.add('task-optical-stage');
    this.progressRuntime = new LensRuntime(this.progressHost,{material:'thick',artwork:progressArtwork,elasticity:0,reduced:effects.reduced});
    effects.progressRuntime = this.progressRuntime;this.progressVisible = false;
    const renderer = this.progressRuntime.system?.renderer;
    if (renderer) {
      const render = renderer.render.bind(renderer);
      renderer.render = now => {
        const host = this.progressHost.getBoundingClientRect(),track = this.progress.element.querySelector('.lg-progress-track').getBoundingClientRect();
        renderer.canvas.style.clipPath = `inset(${Math.max(0,track.top-host.top)}px ${Math.max(0,host.right-track.right)}px ${Math.max(0,host.bottom-track.bottom)}px ${Math.max(0,track.left-host.left)}px round ${track.height/2}px)`;
        render(now);
      };
    }
    this.progressRuntime.stop();
  }
  toast(message, options) {this.notice.show(message, options);}
  startLoading() {this.notice.hide({immediate:true});this.tips.hide();this.effects.setTaskBusy(true);$('loading-state').hidden = false;this.setLoading({message:this.local ? '正在处理本地任务…' : '正在准备示例数据…'});}
  setLoading({message,done,total}) {
    $('loading-label').textContent = message;
    const known = Number.isFinite(total) && total > 0 && Number.isFinite(done) && done >= 0;
    $('loading-progress').hidden = !known; $('loading-indeterminate').hidden = known;
    this.progressVisible = known;this.refreshMotion();
    if (known) {this.progress.setValue(Math.min(100,done/total*100),{animate:!this.effects.reduced});$('loading-detail').textContent = `${Math.min(done,total).toLocaleString()} / ${total.toLocaleString()} 条`;}
    else $('loading-detail').textContent = '正在读取，请稍候';
  }
  refreshMotion() {
    const motion = this.progressVisible && !this.effects.reduced && this.effects.glassEnabled ? 'system' : 'off';
    if (motion !== this.progressMotion) {this.progress.setMotion(motion);this.progressMotion = motion;}
    this.progressRuntime.setReduced(this.effects.reduced);
    const enabled = this.progressVisible && this.effects.glassEnabled;
    if (enabled !== this.progressRuntime.enabled) {if (enabled) this.progressRuntime.start();else this.progressRuntime.stop();}
  }
  endLoading() {this.progressVisible = false;this.refreshMotion();$('loading-state').hidden = true;this.effects.setTaskBusy(false);}
  workflow(step) {document.querySelectorAll('[data-workflow]').forEach(node => {const current = Number(node.dataset.workflow) === step;node.classList.toggle('current',current);if (current) node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');});}
  destroy() {this.progressRuntime.destroy();this.progress.destroy();this.notice.destroy();this.tips.destroy();}
}

export class InspectorDrawer {
  constructor(effects) {
    this.inspector = $('inspector'); this.anchor = document.createComment('inspector home'); this.inspector.before(this.anchor);
    this.dialog = $('inspector-dialog'); this.media = matchMedia('(max-width:1120px)');
    this.modal = modal(this.dialog,{drawer:true,reduced:() => effects.reduced,focusFallback:() => $('file-list').focus(),onClose:() => {
      this.anchor.after(this.inspector);$('review-body').classList.remove('details-open');this.sync();
    }});
    this.onResize = () => {if (!this.media.matches && this.dialog.open) this.modal.close({immediate:true});this.sync();};
    this.media.addEventListener('change',this.onResize); this.sync();
  }
  sync() {$('detail-toggle').setAttribute('aria-controls',this.media.matches ? 'inspector-dialog' : 'inspector');$('detail-toggle').setAttribute('aria-expanded',String(this.media.matches ? this.dialog.open : !$('review-body').classList.contains('details-hidden')));}
  toggle(show) {
    if (this.media.matches) {
      const next = show ?? !this.dialog.open;
      if (next) {this.dialog.append(this.inspector);$('review-body').classList.add('details-open');this.modal.open();this.inspector.querySelector('button')?.focus({preventScroll:true});}
      else this.modal.close();
    } else $('review-body').classList.toggle('details-hidden',show === undefined ? !$('review-body').classList.contains('details-hidden') : !show);
    this.sync();
  }
  destroy() {this.media.removeEventListener('change',this.onResize);if (this.dialog.open) this.dialog.close();this.anchor.after(this.inspector);}
}
